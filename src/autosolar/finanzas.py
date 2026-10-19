"""Módulo 5 · Flujo de caja y KPIs.

Contrato:
    flujo_caja(kwp, kwh_bat, ahorro_anio1, gen_kwh_anio1, ciclos_anio1, cfg) -> pd.DataFrame
        Índice `anio` 0..N (N = finanzas.horizonte_anios). Columnas, en COP salvo gen_kwh:
        capex, ahorro, opex, reposicion, depreciacion, deduccion, impuestos, escudo_fiscal,
        gen_kwh (kWh), flujo, flujo_acumulado.
        Año 0: flujo = −CAPEX (sin IVA: exclusión de IVA, Ley 1715). Años 1..N:
          ahorro = ahorro_anio1·(1+tarifa.escalamiento_anual)^(t−1)·(1−degradacion)^(t−1)
          opex   = opex_pct·CAPEX·(1+inflacion)^(t−1)
          reposición de batería (costo original) cada vez que se cumple
          bateria.vida_ciclos (ciclos acumulados, a ciclos_anio1 por año) o
          bateria.vida_calendario_anios, lo que ocurra primero; no se repone en el año N.
          Si empresa.declara_renta:
            flujo = (ahorro − opex)·(1−t) + t·depreciacion + t·deduccion − reposicion
          si no: flujo = ahorro − opex − reposicion.
        Depreciación lineal del CAPEX en finanzas.anios_depreciacion años si
        incentivos_ley1715; si no, en finanzas.anios_depreciacion_normal (ET art. 137).
        Deducción especial (finanzas.incentivos_ley1715 y declara_renta): 50 % del CAPEX,
        cada año ≤ 50 % de renta_liquida_anual_cop, máximo 15 años, lo más rápido posible.
    vpn_flujo(kwp, kwh_bat, ahorro_anio1, gen_kwh_anio1, ciclos_anio1, cfg) -> float
        El vpn de kpis(flujo_caja(...)) sin armar el DataFrame ni calcular TIR/LCOE (la
        optimización y la sensibilidad lo usan para comparar muchas combinaciones).
    kpis(flujo, cfg) -> dict
        vpn (COP), tir (fracción; nan si no existe), payback_simple y payback_descontado
        (años, interpolado; nan si no se recupera), lcoe (COP/kWh, antes de impuestos).
"""

from __future__ import annotations

import math

import numpy as np
import numpy_financial as npf
import pandas as pd

from autosolar.config import Config

FRACCION_DEDUCCION = 0.5  # Ley 1715 art. 11 (mod. Ley 2099): 50 % de la inversión
TOPE_DEDUCCION_RENTA = 0.5  # cada año ≤ 50 % de la renta líquida
MAX_ANIOS_DEDUCCION = 15  # repartible en hasta 15 años


def _anios_reposicion(kwh_bat: float, ciclos_anio1: float, cfg: Config) -> list[int]:
    """Años (< N) en que se repone la batería: lo primero entre ciclos y calendario."""
    if kwh_bat <= 0:
        return []
    vida = cfg.bateria.vida_calendario_anios
    if ciclos_anio1 > 0:
        vida_por_ciclos = max(1, math.ceil(round(cfg.bateria.vida_ciclos / ciclos_anio1, 9)))
        vida = min(vida, vida_por_ciclos)
    return list(range(vida, cfg.finanzas.horizonte_anios, vida))


def _deducciones(capex: float, cfg: Config) -> np.ndarray:
    """Deducción especial por año (índice 0..N), lo más rápido que permite el tope."""
    n = cfg.finanzas.horizonte_anios
    ded = np.zeros(n + 1)
    resto = FRACCION_DEDUCCION * capex
    tope = TOPE_DEDUCCION_RENTA * cfg.finanzas.renta_liquida_anual_cop
    for t in range(1, min(MAX_ANIOS_DEDUCCION, n) + 1):
        ded[t] = min(resto, tope)
        resto -= ded[t]
    return ded


def _flujo(
    kwp: float,
    kwh_bat: float,
    ahorro_anio1: float,
    gen_kwh_anio1: float,
    ciclos_anio1: float,
    cfg: Config,
) -> dict[str, np.ndarray]:
    """Columnas de flujo_caja como arrays (sin DataFrame: la optimización lo llama a miles)."""
    n = cfg.finanzas.horizonte_anios
    fin = cfg.finanzas
    t = np.arange(n + 1)
    expo = np.maximum(t - 1, 0)

    capex_bat = kwh_bat * cfg.bateria.capex_cop_kwh
    capex = kwp * 1000 * cfg.sistema_fv.capex_cop_wp + capex_bat

    activo = t >= 1
    esc = (1 + cfg.tarifa.escalamiento_anual) ** expo
    deg = (1 - cfg.sistema_fv.degradacion_anual) ** expo
    ahorro = np.where(activo, ahorro_anio1 * esc * deg, 0.0)
    gen = np.where(activo, gen_kwh_anio1 * deg, 0.0)
    opex = np.where(activo, cfg.sistema_fv.opex_pct_capex * capex * (1 + fin.inflacion) ** expo, 0.0)

    reposicion = np.zeros(n + 1)
    for anio in _anios_reposicion(kwh_bat, ciclos_anio1, cfg):
        reposicion[anio] = capex_bat

    depreciacion = np.zeros(n + 1)
    anios_dep = fin.anios_depreciacion if fin.incentivos_ley1715 else fin.anios_depreciacion_normal
    depreciacion[1 : min(anios_dep, n) + 1] = capex / anios_dep

    if cfg.empresa.declara_renta:
        tasa = fin.tasa_renta
        deduccion = _deducciones(capex, cfg) if fin.incentivos_ley1715 else np.zeros(n + 1)
        impuestos = tasa * (ahorro - opex)
        escudo = tasa * (depreciacion + deduccion)
    else:
        depreciacion = np.zeros(n + 1)
        deduccion = np.zeros(n + 1)
        impuestos = np.zeros(n + 1)
        escudo = np.zeros(n + 1)

    capex_col = np.zeros(n + 1)
    capex_col[0] = capex
    flujo = ahorro - opex - impuestos + escudo - reposicion - capex_col

    return {
        "capex": capex_col,
        "ahorro": ahorro,
        "opex": opex,
        "reposicion": reposicion,
        "depreciacion": depreciacion,
        "deduccion": deduccion,
        "impuestos": impuestos,
        "escudo_fiscal": escudo,
        "gen_kwh": gen,
        "flujo": flujo,
        "flujo_acumulado": np.cumsum(flujo),
    }


def flujo_caja(
    kwp: float,
    kwh_bat: float,
    ahorro_anio1: float,
    gen_kwh_anio1: float,
    ciclos_anio1: float,
    cfg: Config,
) -> pd.DataFrame:
    """Flujo de caja del proyecto, años 0..N (COP). Ver contrato del módulo."""
    columnas = _flujo(kwp, kwh_bat, ahorro_anio1, gen_kwh_anio1, ciclos_anio1, cfg)
    anios = pd.Index(np.arange(cfg.finanzas.horizonte_anios + 1), name="anio")
    return pd.DataFrame(columnas, index=anios)


def vpn_flujo(
    kwp: float,
    kwh_bat: float,
    ahorro_anio1: float,
    gen_kwh_anio1: float,
    ciclos_anio1: float,
    cfg: Config,
) -> float:
    """VPN [COP] del flujo de caja: igual a kpis(flujo_caja(...), cfg)["vpn"], pero rápido."""
    fc = _flujo(kwp, kwh_bat, ahorro_anio1, gen_kwh_anio1, ciclos_anio1, cfg)["flujo"]
    factor = (1 + cfg.finanzas.tasa_descuento) ** -np.arange(len(fc), dtype=float)
    return float((fc * factor).sum())


def _payback(flujos: np.ndarray) -> float:
    """Primer cruce a cero del acumulado, interpolado linealmente dentro del año."""
    acum = np.cumsum(flujos)
    if acum[0] >= 0:
        return 0.0
    for t in range(1, len(acum)):
        if acum[t] >= 0:
            return t - 1 + float(-acum[t - 1] / flujos[t])
    return math.nan


def kpis(flujo: pd.DataFrame, cfg: Config) -> dict:
    """VPN [COP], TIR [fracción], paybacks [años] y LCOE [COP/kWh] de un flujo de caja."""
    r = cfg.finanzas.tasa_descuento
    t = flujo.index.to_numpy()
    fd = (1 + r) ** -t.astype(float)
    fc = flujo["flujo"].to_numpy()

    tir = float(npf.irr(fc))
    costos_vp = float((flujo["capex"] * fd).sum() + ((flujo["opex"] + flujo["reposicion"]) * fd).sum())
    gen_vp = float((flujo["gen_kwh"] * fd).sum())

    return {
        "vpn": float((fc * fd).sum()),
        "tir": tir,
        "payback_simple": _payback(fc),
        "payback_descontado": _payback(fc * fd),
        "lcoe": costos_vp / gen_vp if gen_vp > 0 else math.nan,
    }
