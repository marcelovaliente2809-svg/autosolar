"""Módulo 6 · Dimensionamiento óptimo.

Contrato:
    optimizar(cfg) -> pd.DataFrame
        Barrido de la grilla (kwp, kwh_bat) dentro de los límites del YAML, el área de
        techo y el tope AGPE de 1 MW. Devuelve todas las combinaciones con sus KPIs,
        ordenadas por VPN. La mejor fila es la recomendación.
        g y c son opcionales (kWh/h por kWp y carga kWh/h): si se dan, no se vuelven a
        calcular (la sensibilidad y la API los reutilizan).
    evaluar(cfg, kwp, kwh_bat, g, c) -> dict
        Una combinación: balance → liquidación → flujo de caja → KPIs. g = kWh/h por kWp,
        c = carga kWh/h. Devuelve una fila con las columnas de COLUMNAS.
    simular_casos(cfg, g=None, c=None, tarifas_alt=None) -> list[dict]
    tabla_kpis(cfg, casos, alt=None) -> pd.DataFrame
        optimizar() partido en sus dos etapas: simular_casos hace balance + liquidación de
        cada combinación de la grilla (lo caro: no depende de CAPEX, tasa ni incentivos);
        tabla_kpis les aplica flujo de caja y KPIs con el cfg dado. Permite re-evaluar los
        mismos casos con otro CAPEX o sin Ley 1715 sin volver a simular. tarifas_alt
        ({nombre: Tarifa}) liquida además cada caso con esas tarifas (el balance es el mismo);
        tabla_kpis(..., alt=nombre) usa esa liquidación (p. ej. Exc2 valorado a Mc).
    mejor_caso(cfg, casos, alt=None) -> dict
        La primera fila de tabla_kpis(cfg, casos, alt) sin armar la tabla (KPIs completos
        sólo de la mejor; el resto sólo VPN).
    series_solucion(cfg, kwp, kwh_bat, g=None, c=None) -> dict
        Series para graficar la solución (días típicos, balance mensual, flujos acumulados,
        LCOE vs valores de la factura). Ver su docstring.

Supuestos de modelado:
    - Grilla de kWp: kwp_min, kwp_min + paso_kwp, … hasta
      min(kwp_max, area_techo_m2 / m2_por_kwp). Grilla de kWh: kwh_min … kwh_max con
      paso_kwh, y siempre incluye 0 (caso sin batería).
    - kwp = 0 solo se evalúa sin batería (una batería sin generación no tiene sentido).
    - ciclos = Σ descarga_bat / (kwh_bat · dod): ciclos equivalentes a profundidad útil/año.
    - autoconsumo_pct (fracción 0–1) = (autoconsumo + descarga_bat) / generación: parte de
      lo generado que se consume en sitio, directo o vía batería.
    - payback = payback simple (años; nan si no se recupera en el horizonte).
    - g y c se calculan una sola vez en optimizar(); evaluar() no hace E/S.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from autosolar.balance import dias_tipicos, resumen_lote, simular
from autosolar.carga import perfil_carga
from autosolar.config import LIMITE_AGPE_MENOR_KWP, Config, Tarifa
from autosolar.finanzas import flujo_caja, kpis, vpn_flujo
from autosolar.liquidacion import liquidar, liquidar_sumas, valor_credito_cop_kwh
from autosolar.solar import generacion_por_kwp

COLUMNAS = (
    "kwp",
    "kwh_bat",
    "gen_kwh",
    "autoconsumo_pct",
    "exc1_kwh",
    "exc2_kwh",
    "ciclos",
    "ahorro_anio1",
    "capex",
    "vpn",
    "tir",
    "payback",
    "lcoe",
)


def _grilla(minimo: float, maximo: float, paso: float) -> list[float]:
    """minimo, minimo+paso, … ≤ maximo (con tolerancia numérica)."""
    n = int(np.floor((maximo - minimo) / paso + 1e-9))
    return [round(minimo + i * paso, 9) for i in range(n + 1)] if n >= 0 else []


def _liquidar(bal: pd.DataFrame, tarifa: Tarifa, kwp: float) -> dict:
    liq = liquidar(bal, tarifa, kwp)
    liq.pop("mensual")
    return liq


def _simular_caso(
    cfg: Config,
    kwp: float,
    kwh_bat: float,
    g: pd.Series,
    c: pd.Series,
    tarifas_alt: dict[str, Tarifa] | None = None,
) -> dict:
    """Balance + liquidación de una combinación (la parte que no depende de CAPEX ni tasas)."""
    bal = simular(c, g, kwp, kwh_bat, cfg.bateria)
    liq = _liquidar(bal, cfg.tarifa, kwp)

    gen = float(bal["generacion"].sum())
    return {
        "kwp": kwp,
        "kwh_bat": kwh_bat,
        "gen_kwh": gen,
        "autoconsumido": float(bal["autoconsumo"].sum() + bal["descarga_bat"].sum()),
        "ciclos": (
            float(bal["descarga_bat"].sum()) / (kwh_bat * cfg.bateria.dod) if kwh_bat > 0 else 0.0
        ),
        "liq": liq,
        "liq_alt": {n: _liquidar(bal, t, kwp) for n, t in (tarifas_alt or {}).items()},
    }


def _caso_resumen(
    cfg: Config,
    kwp: float,
    kwh_bat: float,
    r: dict,
    tarifas_alt: dict[str, Tarifa] | None = None,
) -> dict:
    """Lo mismo que _caso, desde un agregado de balance.resumen_lote (sin balance horario)."""

    def liq(tarifa: Tarifa) -> dict:
        return liquidar_sumas(r["carga_kwh"], r["importado_kwh"], r["exportado_kwh"], tarifa, kwp)

    return {
        "kwp": kwp,
        "kwh_bat": kwh_bat,
        "gen_kwh": r["generacion"],
        "autoconsumido": r["autoconsumo"] + r["descarga_bat"],
        "ciclos": r["descarga_bat"] / (kwh_bat * cfg.bateria.dod),
        "liq": liq(cfg.tarifa),
        "liq_alt": {n: liq(t) for n, t in (tarifas_alt or {}).items()},
    }


def _fila(cfg: Config, caso: dict, alt: str | None = None) -> dict:
    """Flujo de caja y KPIs de un caso simulado, con las finanzas de `cfg`."""
    kwp, kwh_bat, gen = caso["kwp"], caso["kwh_bat"], caso["gen_kwh"]
    liq = caso["liq"] if alt is None else caso["liq_alt"][alt]
    flujo = flujo_caja(kwp, kwh_bat, liq["ahorro_cop"], gen, caso["ciclos"], cfg)
    k = kpis(flujo, cfg)

    return {
        "kwp": kwp,
        "kwh_bat": kwh_bat,
        "gen_kwh": gen,
        "autoconsumo_pct": caso["autoconsumido"] / gen if gen > 0 else 0.0,
        "exc1_kwh": liq["exc1_kwh"],
        "exc2_kwh": liq["exc2_kwh"],
        "ciclos": caso["ciclos"],
        "ahorro_anio1": liq["ahorro_cop"],
        "capex": float(flujo["capex"].iloc[0]),
        "vpn": k["vpn"],
        "tir": k["tir"],
        "payback": k["payback_simple"],
        "lcoe": k["lcoe"],
    }


def evaluar(cfg: Config, kwp: float, kwh_bat: float, g: pd.Series, c: pd.Series) -> dict:
    """Evalúa una combinación. kwp en kW pico, kwh_bat en kWh, g en kWh/h·kWp, c en kWh/h."""
    return _fila(cfg, _simular_caso(cfg, kwp, kwh_bat, g, c))


def _insumos(cfg: Config, g: pd.Series | None, c: pd.Series | None) -> tuple[pd.Series, pd.Series]:
    if g is None:
        g = generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema)
    if c is None:
        c = perfil_carga(cfg.consumo)
    return g, c


def simular_casos(
    cfg: Config,
    g: pd.Series | None = None,
    c: pd.Series | None = None,
    tarifas_alt: dict[str, Tarifa] | None = None,
) -> list[dict]:
    """Simula (balance + liquidación) toda la grilla (kwp, kwh_bat). Ver módulo."""
    g, c = _insumos(cfg, g, c)
    fv, bat = cfg.sistema_fv, cfg.bateria
    kwp_tope = min(fv.kwp_max, cfg.ubicacion.area_techo_m2 / fv.m2_por_kwp)
    kwps = _grilla(fv.kwp_min, kwp_tope, fv.paso_kwp)
    kwhs = sorted({0.0, *_grilla(bat.kwh_min, bat.kwh_max, bat.paso_kwh)})
    combos = [(kwp, kwh) for kwp in kwps for kwh in kwhs if kwp > 0 or kwh == 0]
    con_bat = [(kwp, kwh) for kwp, kwh in combos if kwh > 0]
    # Con batería, el despacho de toda la grilla se simula en lote (ver balance.resumen_lote)
    resumenes = resumen_lote(c, g, [k for k, _ in con_bat], [h for _, h in con_bat], bat)
    con_bateria = {
        combo: _caso_resumen(cfg, *combo, r, tarifas_alt)
        for combo, r in zip(con_bat, resumenes, strict=True)
    }
    return [
        con_bateria[combo]
        if combo in con_bateria
        else _simular_caso(cfg, *combo, g, c, tarifas_alt)
        for combo in combos
    ]


def tabla_kpis(cfg: Config, casos: list[dict], alt: str | None = None) -> pd.DataFrame:
    """KPIs de los casos simulados, ordenados por VPN (desc), con las finanzas/CAPEX de cfg."""
    tabla = pd.DataFrame([_fila(cfg, caso, alt) for caso in casos], columns=list(COLUMNAS))
    return tabla.sort_values("vpn", ascending=False, kind="stable").reset_index(drop=True)


def mejor_caso(cfg: Config, casos: list[dict], alt: str | None = None) -> dict:
    """La fila de tabla_kpis(cfg, casos, alt) con mayor VPN, calculando KPIs sólo de esa fila."""

    def vpn(caso: dict) -> float:
        liq = caso["liq"] if alt is None else caso["liq_alt"][alt]
        v = vpn_flujo(
            caso["kwp"], caso["kwh_bat"], liq["ahorro_cop"], caso["gen_kwh"], caso["ciclos"], cfg
        )
        return -math.inf if math.isnan(v) else v

    # max() devuelve el primero en empate, igual que el orden estable de tabla_kpis
    return _fila(cfg, max(casos, key=vpn), alt)


def optimizar(
    cfg: Config, g: pd.Series | None = None, c: pd.Series | None = None
) -> pd.DataFrame:
    """Barre la grilla (kwp, kwh_bat) y devuelve la tabla de KPIs ordenada por VPN (desc)."""
    return tabla_kpis(cfg, simular_casos(cfg, g, c))


def series_solucion(
    cfg: Config,
    kwp: float,
    kwh_bat: float,
    g: pd.Series | None = None,
    c: pd.Series | None = None,
) -> dict:
    """Series de la solución (kwp, kwh_bat) para graficar.

    dia_habil, dia_domingo: (fecha, DataFrame de 24 filas con `carga` y las columnas de
        balance.COLUMNAS); miércoles hábil y domingo típicos de julio (balance.dias_tipicos).
    mensual: liquidar(...)["mensual"] más autoconsumo_kwh (= carga − importado, incluye la
        descarga de batería) y generacion_kwh (= autoconsumo + Exc1 + Exc2).
    flujo_base, flujo_sin_ley1715: finanzas.flujo_caja con y sin incentivos de la Ley 1715.
    valores: lcoe, cu, cu_menos_cv, g, precio_exc2 [COP/kWh] (frente a la factura).
    """
    g, c = _insumos(cfg, g, c)
    bal = simular(c, g, kwp, kwh_bat, cfg.bateria)
    liq = liquidar(bal, cfg.tarifa, kwp)
    gen = float(bal["generacion"].sum())
    ciclos = float(bal["descarga_bat"].sum()) / (kwh_bat * cfg.bateria.dod) if kwh_bat > 0 else 0.0

    args = (kwp, kwh_bat, liq["ahorro_cop"], gen, ciclos)
    sin_ley = cfg.model_copy(deep=True)
    sin_ley.finanzas.incentivos_ley1715 = False
    flujo_base = flujo_caja(*args, cfg)

    def dia(fecha: pd.Timestamp) -> tuple[pd.Timestamp, pd.DataFrame]:
        tramo = bal[bal.index.normalize() == fecha].copy()
        tramo.insert(0, "carga", tramo["autoconsumo"] + tramo["descarga_bat"] + tramo["importado"])
        return fecha, tramo

    habil, domingo = dias_tipicos(bal)
    mensual = liq["mensual"].copy()
    mensual["autoconsumo_kwh"] = mensual["carga_kwh"] - mensual["importado_kwh"]
    mensual["generacion_kwh"] = (
        mensual["autoconsumo_kwh"] + mensual["exc1_kwh"] + mensual["exc2_kwh"]
    )
    t = cfg.tarifa
    return {
        "dia_habil": dia(habil),
        "dia_domingo": dia(domingo),
        "mensual": mensual,
        "flujo_base": flujo_base,
        "flujo_sin_ley1715": flujo_caja(*args, sin_ley),
        "valores": {
            "lcoe": kpis(flujo_base, cfg)["lcoe"],
            "cu": t.cu_cop_kwh,
            "cu_menos_cv": valor_credito_cop_kwh(t, LIMITE_AGPE_MENOR_KWP),
            "g": t.g_cop_kwh,
            "precio_exc2": t.precio_exc2_cop_kwh,
        },
    }
