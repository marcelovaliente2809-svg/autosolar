"""Módulo 7 · Análisis de sensibilidad.

Contrato:
    tornado(cfg, kwp, kwh_bat, variacion=0.2, g=None, c=None) -> pd.DataFrame
        Columnas (variable, vpn_bajo, vpn_base, vpn_alto), VPN en COP. Varía de a una
        variable en ±variacion (relativo: valor·(1 ∓ variacion)) con el sistema fijo en
        (kwp, kwh_bat): cu (escala cu, g y Cv juntos), capex_fv, capex_bateria,
        tasa_descuento, escalamiento_tarifa, degradacion y precio_exc2. Ordenado por
        amplitud |vpn_alto − vpn_bajo| descendente. vpn_bajo/vpn_alto = VPN con la
        variable en su valor bajo/alto (no el peor/mejor caso).
    escenarios(cfg, casos_base=None, g=None) -> pd.DataFrame
        Re-optimiza en: base, exc2_a_mc (valoracion_exc2 = "mc" y Exc2 a
        tarifa.precio_mc_cop_kwh), sin_ley1715, jornada_2_turnos y jornada_continua.
        Columnas: escenario, kwp, kwh_bat, vpn, tir, payback, autoconsumo_pct (mejor fila).
        casos_base (opcional): simular_casos_base(cfg) ya calculado; base, exc2_a_mc y sin_ley1715 no cambian el balance, así
        que se re-evalúan sin volver a simular (sólo las jornadas re-simulan).
        Sin casos_base, o si no traen la liquidación a Mc, escenarios() los calcula. g
        (opcional): generación por kWp ya calculada.
    breakeven_bateria(cfg, casos=None) -> float
        capex_cop_kwh de batería por debajo del cual la mejor solución de optimizar()
        incluye batería (bisección geométrica, tolerancia relativa 1 %). 0.0 si nunca
        conviene batería; inf si conviene aun a 64 veces el CAPEX del YAML.
        casos (opcional): optimizacion.simular_casos(cfg) ya calculado.

Supuestos de modelado:
    - Nunca se modifica el cfg recibido: cada caso trabaja con model_copy(deep=True).
    - Se asume que la inclusión de batería es monótona en su CAPEX (más barata → más
      probable); la bisección no verifica esa monotonía.
    - g y c se calculan una vez en tornado(). En escenarios g se calcula una vez y c una por
      jornada. El breakeven simula la grilla una sola vez: el CAPEX de batería no cambia el
      balance ni la liquidación, así que cada paso de la bisección sólo rehace el flujo de
      caja (exacto, sin aproximar la grilla); las filas sin batería no dependen de ese CAPEX.
"""

from __future__ import annotations

import math

import pandas as pd

from autosolar import optimizacion
from autosolar.config import Config
from autosolar.finanzas import vpn_flujo

COLUMNAS_TORNADO = ("variable", "vpn_bajo", "vpn_base", "vpn_alto")
COLUMNAS_ESCENARIOS = (
    "escenario",
    "kwp",
    "kwh_bat",
    "vpn",
    "tir",
    "payback",
    "autoconsumo_pct",
)
TOLERANCIA_BREAKEVEN = 0.01  # relativa al CAPEX
MAX_DUPLICACIONES = 6  # busca hasta 2^6 = 64 veces el CAPEX del YAML
MAX_REDUCCIONES = 10  # y hasta 2^-10 veces


def _escalar(cfg: Config, variable: str, factor: float) -> Config:
    """Copia profunda de cfg con `variable` multiplicada por `factor`."""
    c = cfg.model_copy(deep=True)
    if variable == "cu":
        t = c.tarifa
        t.cu_cop_kwh *= factor
        t.g_cop_kwh *= factor
        t.componente_comercializacion_cop_kwh *= factor
    elif variable == "capex_fv":
        c.sistema_fv.capex_cop_wp *= factor
    elif variable == "capex_bateria":
        c.bateria.capex_cop_kwh *= factor
    elif variable == "tasa_descuento":
        c.finanzas.tasa_descuento *= factor
    elif variable == "escalamiento_tarifa":
        c.tarifa.escalamiento_anual *= factor
    elif variable == "degradacion":
        c.sistema_fv.degradacion_anual *= factor
    elif variable == "precio_exc2":
        c.tarifa.precio_exc2_cop_kwh *= factor
    else:
        raise ValueError(f"variable desconocida: {variable}")
    return c


VARIABLES_TORNADO = (
    "cu",
    "capex_fv",
    "capex_bateria",
    "tasa_descuento",
    "escalamiento_tarifa",
    "degradacion",
    "precio_exc2",
)


def tornado(
    cfg: Config,
    kwp: float,
    kwh_bat: float,
    variacion: float = 0.2,
    g: pd.Series | None = None,
    c: pd.Series | None = None,
) -> pd.DataFrame:
    """VPN [COP] al variar ±variacion (fracción, relativa) cada variable, con (kwp, kwh_bat) fijo."""
    if g is None:
        g = optimizacion.generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema)
    if c is None:
        c = optimizacion.perfil_carga(cfg.consumo)

    def vpn(cfg_i: Config) -> float:
        return optimizacion.evaluar(cfg_i, kwp, kwh_bat, g, c)["vpn"]

    base = vpn(cfg)
    filas = [
        {
            "variable": v,
            "vpn_bajo": vpn(_escalar(cfg, v, 1 - variacion)),
            "vpn_base": base,
            "vpn_alto": vpn(_escalar(cfg, v, 1 + variacion)),
        }
        for v in VARIABLES_TORNADO
    ]
    tabla = pd.DataFrame(filas, columns=list(COLUMNAS_TORNADO))
    amplitud = (tabla["vpn_alto"] - tabla["vpn_bajo"]).abs()
    return tabla.loc[amplitud.sort_values(ascending=False, kind="stable").index].reset_index(
        drop=True
    )


def _casos_escenarios(cfg: Config) -> dict[str, Config]:
    base = cfg.model_copy(deep=True)

    mc = cfg.model_copy(deep=True)
    if cfg.tarifa.precio_mc_cop_kwh is None:
        raise ValueError("el escenario Exc2 a Mc requiere tarifa.precio_mc_cop_kwh en el YAML")
    mc.tarifa.valoracion_exc2 = "mc"
    mc.tarifa.precio_exc2_cop_kwh = cfg.tarifa.precio_mc_cop_kwh

    sin_ley = cfg.model_copy(deep=True)
    sin_ley.finanzas.incentivos_ley1715 = False

    dos = cfg.model_copy(deep=True)
    dos.consumo.jornada = "2_turnos"
    continua = cfg.model_copy(deep=True)
    continua.consumo.jornada = "continua"

    return {
        "base": base,
        "exc2_a_mc": mc,
        "sin_ley1715": sin_ley,
        "jornada_2_turnos": dos,
        "jornada_continua": continua,
    }


def simular_casos_base(
    cfg: Config, g: pd.Series | None = None, c: pd.Series | None = None
) -> list[dict]:
    """optimizacion.simular_casos(cfg) con la liquidación del escenario Exc2 a Mc incluida."""
    mc = _casos_escenarios(cfg)["exc2_a_mc"].tarifa
    return optimizacion.simular_casos(cfg, g, c, tarifas_alt={"exc2_a_mc": mc})


def _fila_mejor(nombre: str, mejor: dict) -> dict:
    return {
        "escenario": nombre,
        "kwp": float(mejor["kwp"]),
        "kwh_bat": float(mejor["kwh_bat"]),
        "vpn": float(mejor["vpn"]),
        "tir": float(mejor["tir"]),
        "payback": float(mejor["payback"]),
        "autoconsumo_pct": float(mejor["autoconsumo_pct"]),
    }


def escenarios(
    cfg: Config, casos_base: list[dict] | None = None, g: pd.Series | None = None
) -> pd.DataFrame:
    """Mejor solución (por VPN) de cada escenario regulatorio / operativo."""
    if g is None:
        g = optimizacion.generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema)
    casos = _casos_escenarios(cfg)
    if casos_base is None or "exc2_a_mc" not in (casos_base[0]["liq_alt"] if casos_base else {}):
        casos_base = simular_casos_base(cfg, g)

    filas = []
    for nombre, cfg_i in casos.items():
        if nombre in ("base", "sin_ley1715"):  # sólo cambian las finanzas
            mejor = optimizacion.mejor_caso(cfg_i, casos_base)
        elif nombre == "exc2_a_mc":  # mismo balance, otra liquidación
            mejor = optimizacion.mejor_caso(cfg_i, casos_base, alt=nombre)
        else:
            mejor = optimizacion.mejor_caso(cfg_i, optimizacion.simular_casos(cfg_i, g))
        filas.append(_fila_mejor(nombre, mejor))
    return pd.DataFrame(filas, columns=list(COLUMNAS_ESCENARIOS))


def _mejor_vpn(cfg: Config, casos: list[dict]) -> float:
    """Mayor VPN entre los casos simulados (el breakeven no necesita TIR ni LCOE)."""
    return max(
        vpn_flujo(k["kwp"], k["kwh_bat"], k["liq"]["ahorro_cop"], k["gen_kwh"], k["ciclos"], cfg)
        for k in casos
    )


def breakeven_bateria(cfg: Config, casos: list[dict] | None = None) -> float:
    """CAPEX de batería [COP/kWh] bajo el cual la mejor solución incluye batería."""
    if casos is None:
        casos = optimizacion.simular_casos(cfg)
    sin_bat = [k for k in casos if k["kwh_bat"] == 0]
    con_bat = [k for k in casos if k["kwh_bat"] > 0]
    if not con_bat:
        return 0.0
    vpn_sin = _mejor_vpn(cfg, sin_bat)

    def incluye(capex: float) -> bool:
        c = cfg.model_copy(deep=True)
        c.bateria.capex_cop_kwh = capex
        return _mejor_vpn(c, con_bat) > vpn_sin

    base = cfg.bateria.capex_cop_kwh
    if incluye(base):
        lo, hi = base, base * 2
        for _ in range(MAX_DUPLICACIONES):
            if not incluye(hi):
                break
            lo, hi = hi, hi * 2
        else:
            return math.inf
    else:
        lo, hi = base / 2, base
        for _ in range(MAX_REDUCCIONES):
            if incluye(lo):
                break
            hi, lo = lo, lo / 2
        else:
            return 0.0

    while hi / lo - 1 > TOLERANCIA_BREAKEVEN:
        mid = math.sqrt(lo * hi)
        if incluye(mid):
            lo = mid
        else:
            hi = mid
    return lo
