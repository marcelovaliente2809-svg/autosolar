import math
from pathlib import Path

import pandas as pd
import pytest

from autosolar import optimizacion
from autosolar.config import cargar_config
from autosolar.optimizacion import evaluar, optimizar
from autosolar.sensibilidad import (
    COLUMNAS_ESCENARIOS,
    COLUMNAS_TORNADO,
    breakeven_bateria,
    escenarios,
    tornado,
)

EJEMPLO = Path(__file__).parents[1] / "config" / "empresa_ejemplo.yaml"
INDICE = pd.date_range("2023-01-01", periods=24, freq="h")


def _g() -> pd.Series:
    return pd.Series([0.5 if 6 <= h < 18 else 0.0 for h in range(24)], index=INDICE)


def _c() -> pd.Series:
    return pd.Series(1.0, index=INDICE)


def _cfg():
    """Grilla corta: kWp ∈ {0, 5, 10, 15}, kWh ∈ {0, 5, 10}; batería ideal."""
    cfg = cargar_config(EJEMPLO)
    cfg.sistema_fv.kwp_min, cfg.sistema_fv.paso_kwp = 0, 5
    cfg.ubicacion.area_techo_m2 = 100  # 100 / 5.5 = 18 kWp
    cfg.bateria.kwh_min, cfg.bateria.kwh_max, cfg.bateria.paso_kwh = 0, 10, 5
    cfg.bateria.eficiencia_ciclo, cfg.bateria.dod, cfg.bateria.c_rate = 1.0, 1.0, 1.0
    # El "año" de 24 h ahorra poco: tarifas ×1000 para que los flujos sean positivos
    t = cfg.tarifa
    t.cu_cop_kwh *= 1000
    t.g_cop_kwh *= 1000
    t.componente_comercializacion_cop_kwh *= 1000
    t.precio_exc2_cop_kwh *= 1000
    t.precio_mc_cop_kwh *= 1000
    return cfg


@pytest.fixture
def jornadas(monkeypatch):
    """Datos de 24 h; registra la jornada con que se pidió cada perfil de carga."""
    vistas = []

    def perfil(consumo):
        vistas.append(consumo.jornada)
        return _c()

    monkeypatch.setattr(optimizacion, "generacion_por_kwp", lambda *_: _g())
    monkeypatch.setattr(optimizacion, "perfil_carga", perfil)
    return vistas


def test_config_trae_precio_mc():
    assert cargar_config(EJEMPLO).tarifa.precio_mc_cop_kwh == 300.0


def test_tornado_estructura_orden_y_base(jornadas):
    cfg = _cfg()
    t = tornado(cfg, 10, 0)
    assert list(t.columns) == list(COLUMNAS_TORNADO)
    assert len(t) == 7
    base = evaluar(cfg, 10, 0, _g(), _c())["vpn"]
    assert t["vpn_base"].to_numpy() == pytest.approx(base)
    amplitud = (t["vpn_alto"] - t["vpn_bajo"]).abs()
    assert amplitud.is_monotonic_decreasing


def test_tornado_sentido_de_los_efectos(jornadas):
    t = tornado(_cfg(), 10, 5).set_index("variable")
    # Más CAPEX o más tasa de descuento → menor VPN; más CU, escalamiento o Exc2 → mayor.
    for v in ("capex_fv", "capex_bateria", "tasa_descuento", "degradacion"):
        assert t.loc[v, "vpn_bajo"] > t.loc[v, "vpn_base"] > t.loc[v, "vpn_alto"], v
    for v in ("cu", "escalamiento_tarifa", "precio_exc2"):
        assert t.loc[v, "vpn_bajo"] < t.loc[v, "vpn_base"] < t.loc[v, "vpn_alto"], v


def test_tornado_no_modifica_cfg(jornadas):
    cfg = _cfg()
    antes = cfg.model_dump()
    tornado(cfg, 10, 5)
    assert cfg.model_dump() == antes


def test_escenarios_estructura_y_limites(jornadas):
    cfg = _cfg()
    cfg.tarifa.precio_mc_cop_kwh = 0.0  # Exc2 sin valor: nunca puede mejorar al base
    antes = cfg.model_dump()
    e = escenarios(cfg)
    assert list(e.columns) == list(COLUMNAS_ESCENARIOS)
    assert list(e["escenario"]) == [
        "base",
        "exc2_a_mc",
        "sin_ley1715",
        "jornada_2_turnos",
        "jornada_continua",
    ]
    v = e.set_index("escenario")["vpn"]
    assert v["exc2_a_mc"] <= v["base"] + 1e-6
    assert v["sin_ley1715"] <= v["base"] + 1e-6
    assert e["autoconsumo_pct"].between(0, 1 + 1e-9).all()
    assert set(jornadas) == {"1_turno", "2_turnos", "continua"}
    assert cfg.model_dump() == antes


def test_escenarios_exige_precio_mc(jornadas):
    cfg = _cfg()
    cfg.tarifa.precio_mc_cop_kwh = None
    with pytest.raises(ValueError, match="precio_mc_cop_kwh"):
        escenarios(cfg)


def test_breakeven_bateria_separa_con_y_sin_bateria(jornadas):
    cfg = _cfg()
    antes = cfg.model_dump()
    be = breakeven_bateria(cfg)
    assert 0 < be < cfg.bateria.capex_cop_kwh  # a 1.8 M COP/kWh no conviene en 24 h

    def kwh_mejor(capex):
        c = cfg.model_copy(deep=True)
        c.bateria.capex_cop_kwh = capex
        return optimizar(c).iloc[0]["kwh_bat"]

    assert kwh_mejor(be) > 0
    assert kwh_mejor(be * 1.05) == 0  # tolerancia 1 %: 5 % arriba ya no entra
    assert cfg.model_dump() == antes


def test_breakeven_cero_si_no_hay_bateria_posible(jornadas):
    cfg = _cfg()
    cfg.bateria.kwh_max = 0
    assert breakeven_bateria(cfg) == 0.0
    assert not math.isnan(breakeven_bateria(cfg))
