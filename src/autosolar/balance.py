"""Módulo 3 · Balance energético hora a hora con batería.

Contrato:
    simular(carga, gen_kwp, kwp, kwh_bat, bateria) -> pd.DataFrame
        Columnas por hora: generacion, autoconsumo, carga_bat, descarga_bat, soc,
        exportado, importado. Estrategia de despacho: autoconsumo primero, luego cargar
        batería, luego exportar; el déficit se cubre con batería y luego con la red.
        Debe cumplir el balance: carga = autoconsumo + descarga_bat + importado.
    resumen_lote(carga, gen_kwp, kwps, kwhs, bateria) -> Iterator[dict]
        Para muchas combinaciones (kwp, kwh_bat > 0) a la vez, entrega por combinación los
        agregados que necesita la optimización: sumas anuales (generacion, autoconsumo,
        descarga_bat) y mensuales (carga_kwh, importado_kwh, exportado_kwh, con `meses`).
        Son los mismos valores que daría simular() + groupby por mes: el bucle horario se
        vectoriza sobre las combinaciones (uno por combinación era lo más lento del motor) y
        no se arma un DataFrame horario por combinación.
    dias_tipicos(balance) -> (Timestamp, Timestamp)
        Miércoles hábil y domingo típicos de julio del balance (los usan las gráficas y la API).

Supuestos de modelado:
    - carga: kWh/h de la planta. gen_kwp: kWh/h de 1 kWp. generacion = gen_kwp · kwp.
      Ambas series de igual longitud (8760 en producción); el índice de salida es el de carga.
    - Despacho por hora: autoconsumo = min(generacion, carga). El excedente carga la batería
      hasta su límite de energía y de potencia; el resto se exporta. El déficit se cubre con
      la batería (hasta su energía y potencia disponibles) y luego con la red.
    - La batería NO carga desde la red.
    - Eficiencia: raíz cuadrada de eficiencia_ciclo en carga y en descarga (η_c = η_d = √η).
      carga_bat y descarga_bat son flujos del lado de la planta (antes de pérdidas en carga,
      después de pérdidas en descarga), así que
          ΔSOC = carga_bat·√η − descarga_bat/√η.
    - soc: kWh almacenados al FINAL de cada hora, entre (1 − dod)·kwh_bat y kwh_bat.
      Inicia en el mínimo (1 − dod)·kwh_bat.
    - Potencia máxima de carga y de descarga = c_rate·kwh_bat (kW = kWh/h), aplicada al
      flujo del lado de la planta.
    - kwh_bat = 0 → camino vectorizado sin bucle (la optimización lo llama cientos de veces).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import holidays
import numpy as np
import pandas as pd

from autosolar.config import Bateria

TAMANO_LOTE = 64  # combinaciones por trozo en simular_lote (≈ 60 MB de matrices a 8760 h)

COLUMNAS = (
    "generacion",
    "autoconsumo",
    "carga_bat",
    "descarga_bat",
    "soc",
    "exportado",
    "importado",
)


def _sin_bateria(carga: np.ndarray, generacion: np.ndarray) -> dict[str, np.ndarray]:
    """Camino vectorizado: sin batería no hay estado que arrastrar entre horas."""
    autoconsumo = np.minimum(generacion, carga)
    ceros = np.zeros_like(carga)
    return {
        "generacion": generacion,
        "autoconsumo": autoconsumo,
        "carga_bat": ceros,
        "descarga_bat": ceros,
        "soc": ceros,
        "exportado": generacion - autoconsumo,
        "importado": carga - autoconsumo,
    }


def _con_bateria(
    carga: np.ndarray, generacion: np.ndarray, kwh_bat: float, bateria: Bateria
) -> dict[str, np.ndarray]:
    """Despacho secuencial (el SOC depende de la hora anterior). Bucle sobre floats nativos."""
    n = len(carga)
    r = bateria.eficiencia_ciclo**0.5  # rendimiento de un sentido (carga o descarga)
    soc_min = (1.0 - bateria.dod) * kwh_bat
    pmax = bateria.c_rate * kwh_bat

    autoconsumo = np.minimum(generacion, carga)
    saldo = (generacion - carga).tolist()  # >0 excedente, <0 déficit

    carga_bat = [0.0] * n
    descarga_bat = [0.0] * n
    soc_h = [0.0] * n
    exportado = [0.0] * n
    importado = [0.0] * n

    soc = soc_min
    for h in range(n):
        s = saldo[h]
        if s > 0.0:
            # kWh de planta que aún caben: (espacio libre) / r
            cb = min(s, pmax, (kwh_bat - soc) / r)
            if cb > 0.0:
                soc += cb * r
                carga_bat[h] = cb
            exportado[h] = s - cb
        elif s < 0.0:
            d = -s
            # kWh que entrega la batería a la planta: (energía sobre el mínimo) · r
            db = min(d, pmax, (soc - soc_min) * r)
            if db > 0.0:
                soc -= db / r
                descarga_bat[h] = db
            importado[h] = d - db
        soc_h[h] = soc

    return {
        "generacion": generacion,
        "autoconsumo": autoconsumo,
        "carga_bat": np.array(carga_bat),
        "descarga_bat": np.array(descarga_bat),
        "soc": np.array(soc_h),
        "exportado": np.array(exportado),
        "importado": np.array(importado),
    }


def _lote(
    carga: np.ndarray, gen_kwp: np.ndarray, kwps: np.ndarray, kwhs: np.ndarray, bateria: Bateria
) -> dict[str, np.ndarray]:
    """Mismo despacho que _con_bateria, con el bucle horario vectorizado sobre las combinaciones.

    Devuelve matrices (horas × combinaciones). Cada hora sólo uno de cb/db es distinto de cero
    (según el signo del saldo), de modo que `soc + cb·r − db/r` reproduce las dos ramas.
    """
    r = bateria.eficiencia_ciclo**0.5
    soc_min = (1.0 - bateria.dod) * kwhs
    pmax = bateria.c_rate * kwhs

    generacion = np.outer(gen_kwp, kwps)
    saldo = generacion - carga[:, None]
    excedente = np.maximum(saldo, 0.0)
    deficit = np.maximum(-saldo, 0.0)

    n, m = saldo.shape
    carga_bat = np.empty((n, m))
    descarga_bat = np.empty((n, m))
    soc_h = np.empty((n, m))
    soc = soc_min.copy()
    for h in range(n):
        cb = np.maximum(np.minimum(np.minimum(excedente[h], pmax), (kwhs - soc) / r), 0.0)
        db = np.maximum(np.minimum(np.minimum(deficit[h], pmax), (soc - soc_min) * r), 0.0)
        soc = soc + cb * r - db / r
        carga_bat[h], descarga_bat[h], soc_h[h] = cb, db, soc

    return {
        "generacion": generacion,
        "autoconsumo": np.minimum(generacion, carga[:, None]),
        "carga_bat": carga_bat,
        "descarga_bat": descarga_bat,
        "soc": soc_h,
        "exportado": excedente - carga_bat,
        "importado": deficit - descarga_bat,
    }


def resumen_lote(
    carga: pd.Series,
    gen_kwp: pd.Series,
    kwps: Sequence[float],
    kwhs: Sequence[float],
    bateria: Bateria,
) -> Iterator[dict]:
    """Agregados de simular() para cada par (kwps[i], kwhs[i]) con kwh > 0. Ver el módulo."""
    if len(carga) != len(gen_kwp):
        raise ValueError(f"carga ({len(carga)}) y gen_kwp ({len(gen_kwp)}) deben tener igual largo")
    kwp_v, kwh_v = np.asarray(kwps, dtype=float), np.asarray(kwhs, dtype=float)
    if kwp_v.shape != kwh_v.shape:
        raise ValueError("kwps y kwhs deben tener igual largo")
    if (kwp_v < 0).any() or (kwh_v <= 0).any():
        raise ValueError("kwp no puede ser negativo y kwh_bat debe ser > 0")

    c, g = carga.to_numpy(dtype=float), gen_kwp.to_numpy(dtype=float)
    mes = pd.DatetimeIndex(carga.index).month.to_numpy()
    meses = np.unique(mes)
    por_mes = (mes[None, :] == meses[:, None]).astype(float)  # (meses × horas)

    for ini in range(0, len(kwp_v), TAMANO_LOTE):  # por trozos: las matrices son horas × lote
        fin = ini + TAMANO_LOTE
        cols = _lote(c, g, kwp_v[ini:fin], kwh_v[ini:fin], bateria)
        # carga = autoconsumo + descarga_bat + importado (igual que liquidacion.liquidar)
        carga_real = cols["autoconsumo"] + cols["descarga_bat"] + cols["importado"]
        mensual_carga = por_mes @ carga_real
        mensual_imp = por_mes @ cols["importado"]
        mensual_exp = por_mes @ cols["exportado"]
        for i in range(cols["soc"].shape[1]):
            yield {
                "meses": meses,
                "carga_kwh": mensual_carga[:, i],
                "importado_kwh": mensual_imp[:, i],
                "exportado_kwh": mensual_exp[:, i],
                "generacion": float(cols["generacion"][:, i].sum()),
                "autoconsumo": float(cols["autoconsumo"][:, i].sum()),
                "descarga_bat": float(cols["descarga_bat"][:, i].sum()),
            }


def simular(
    carga: pd.Series,
    gen_kwp: pd.Series,
    kwp: float,
    kwh_bat: float,
    bateria: Bateria,
) -> pd.DataFrame:
    """Balance horario FV + batería. Todas las columnas en kWh por hora (soc en kWh).

    carga: kWh/h de la planta. gen_kwp: kWh/h por kWp. kwp: kW pico instalados.
    kwh_bat: capacidad nominal de la batería en kWh (0 = sin batería).
    bateria: config.bateria (eficiencia_ciclo, dod, c_rate).
    """
    if len(carga) != len(gen_kwp):
        raise ValueError(f"carga ({len(carga)}) y gen_kwp ({len(gen_kwp)}) deben tener igual largo")
    if kwp < 0 or kwh_bat < 0:
        raise ValueError("kwp y kwh_bat no pueden ser negativos")

    c = carga.to_numpy(dtype=float)
    g = gen_kwp.to_numpy(dtype=float) * kwp

    if kwh_bat == 0:
        columnas = _sin_bateria(c, g)
    else:
        columnas = _con_bateria(c, g, float(kwh_bat), bateria)

    return pd.DataFrame(columnas, index=carga.index, columns=list(COLUMNAS))


MES_DIA_TIPICO = 7  # julio


def _elegir_dia(dias: list[pd.Timestamp], criterios, ref: pd.Timestamp) -> pd.Timestamp:
    """Día más cercano a `ref` que cumple el primer criterio con candidatos.

    criterios: funciones día → bool de la más a la menos exigente; si ninguna tiene
    candidatos (datos cortos de prueba) cae al primer día disponible.
    """
    for criterio in criterios:
        candidatos = [d for d in dias if criterio(d)]
        if candidatos:
            return min(candidatos, key=lambda d: abs(d - ref))
    return dias[0]


def dias_tipicos(balance: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Miércoles no festivo de julio y domingo de julio más cercano a ese miércoles."""
    dias = list(pd.DatetimeIndex(balance.index.normalize().unique()))
    festivos = holidays.Colombia(years=sorted({d.year for d in dias}))
    laboral = lambda d: d.weekday() < 5 and d not in festivos
    julio = lambda d: d.month == MES_DIA_TIPICO
    ref = pd.Timestamp(year=dias[len(dias) // 2].year, month=MES_DIA_TIPICO, day=15)

    habil = _elegir_dia(
        dias,
        (
            lambda d: julio(d) and d.weekday() == 2 and d not in festivos,
            lambda d: julio(d) and laboral(d),
            laboral,
        ),
        ref,
    )
    finde = _elegir_dia(
        dias,
        (
            lambda d: d.month == habil.month and d.weekday() == 6,
            lambda d: d.weekday() >= 5,
        ),
        habil,
    )
    return habil, finde
