"""Módulo 6 · Dimensionamiento óptimo.

Contrato:
    optimizar(cfg) -> pd.DataFrame
        Barrido de la grilla (kwp, kwh_bat) dentro de los límites del YAML, el área de
        techo y el tope AGPE de 1 MW. Devuelve todas las combinaciones con sus KPIs,
        ordenadas por VPN. La mejor fila es la recomendación.
    evaluar(cfg, kwp, kwh_bat, g, c) -> dict
        Una combinación: balance → liquidación → flujo de caja → KPIs. g = kWh/h por kWp,
        c = carga kWh/h. Devuelve una fila con las columnas de COLUMNAS.

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

import numpy as np
import pandas as pd

from autosolar.balance import simular
from autosolar.carga import perfil_carga
from autosolar.config import Config
from autosolar.finanzas import flujo_caja, kpis
from autosolar.liquidacion import liquidar
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


def evaluar(cfg: Config, kwp: float, kwh_bat: float, g: pd.Series, c: pd.Series) -> dict:
    """Evalúa una combinación. kwp en kW pico, kwh_bat en kWh, g en kWh/h·kWp, c en kWh/h."""
    bal = simular(c, g, kwp, kwh_bat, cfg.bateria)
    liq = liquidar(bal, cfg.tarifa, kwp)

    gen = float(bal["generacion"].sum())
    autoconsumido = float(bal["autoconsumo"].sum() + bal["descarga_bat"].sum())
    ciclos = (
        float(bal["descarga_bat"].sum()) / (kwh_bat * cfg.bateria.dod) if kwh_bat > 0 else 0.0
    )

    flujo = flujo_caja(kwp, kwh_bat, liq["ahorro_cop"], gen, ciclos, cfg)
    k = kpis(flujo, cfg)

    return {
        "kwp": kwp,
        "kwh_bat": kwh_bat,
        "gen_kwh": gen,
        "autoconsumo_pct": autoconsumido / gen if gen > 0 else 0.0,
        "exc1_kwh": liq["exc1_kwh"],
        "exc2_kwh": liq["exc2_kwh"],
        "ciclos": ciclos,
        "ahorro_anio1": liq["ahorro_cop"],
        "capex": float(flujo["capex"].iloc[0]),
        "vpn": k["vpn"],
        "tir": k["tir"],
        "payback": k["payback_simple"],
        "lcoe": k["lcoe"],
    }


def optimizar(cfg: Config) -> pd.DataFrame:
    """Barre la grilla (kwp, kwh_bat) y devuelve la tabla de KPIs ordenada por VPN (desc)."""
    g = generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema)
    c = perfil_carga(cfg.consumo)

    fv, bat = cfg.sistema_fv, cfg.bateria
    kwp_tope = min(fv.kwp_max, cfg.ubicacion.area_techo_m2 / fv.m2_por_kwp)
    kwps = _grilla(fv.kwp_min, kwp_tope, fv.paso_kwp)
    kwhs = sorted({0.0, *_grilla(bat.kwh_min, bat.kwh_max, bat.paso_kwh)})

    filas = [
        evaluar(cfg, kwp, kwh, g, c) for kwp in kwps for kwh in kwhs if kwp > 0 or kwh == 0
    ]
    tabla = pd.DataFrame(filas, columns=list(COLUMNAS))
    return tabla.sort_values("vpn", ascending=False, kind="stable").reset_index(drop=True)
