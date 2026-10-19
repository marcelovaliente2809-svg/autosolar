"""Módulo 3 · Balance energético hora a hora con batería.

Contrato:
    simular(carga, gen_kwp, kwp, kwh_bat, bateria) -> pd.DataFrame
        Columnas por hora: generacion, autoconsumo, carga_bat, descarga_bat, soc,
        exportado, importado. Estrategia de despacho: autoconsumo primero, luego cargar
        batería, luego exportar; el déficit se cubre con batería y luego con la red.
        Debe cumplir el balance: carga = autoconsumo + descarga_bat + importado.

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

import numpy as np
import pandas as pd

from autosolar.config import Bateria

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
