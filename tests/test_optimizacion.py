import math
from pathlib import Path

import pandas as pd
import pytest

from autosolar import optimizacion
from autosolar.config import cargar_config
from autosolar.optimizacion import COLUMNAS, evaluar, optimizar

EJEMPLO = Path(__file__).parents[1] / "config" / "empresa_ejemplo.yaml"
INDICE = pd.date_range("2023-01-01", periods=24, freq="h")


def _g() -> pd.Series:
    """0.5 kWh/kWp de 6 a 17 h (12 h), 0 en el resto."""
    return pd.Series([0.5 if 6 <= h < 18 else 0.0 for h in range(24)], index=INDICE)


def _c() -> pd.Series:
    return pd.Series(1.0, index=INDICE)  # 1 kWh/h plano


# Valores fijos de las cuentas a mano; no dependen de lo que diga el YAML de ejemplo.
TARIFA = {
    "cu_cop_kwh": 900.0,
    "componente_comercializacion_cop_kwh": 80.0,
    "g_cop_kwh": 330.0,
    "precio_exc2_cop_kwh": 350.0,
    "valoracion_exc2": "precio_bolsa",
}
SISTEMA_FV = {"capex_cop_wp": 3200.0}
BATERIA = {"capex_cop_kwh": 1_800_000.0}


def _cfg(sistema_fv=None, bateria=None, ubicacion=None):
    base = cargar_config(EJEMPLO)
    return base.model_copy(
        update={
            "tarifa": base.tarifa.model_copy(update=TARIFA),
            "sistema_fv": base.sistema_fv.model_copy(update={**SISTEMA_FV, **(sistema_fv or {})}),
            "bateria": base.bateria.model_copy(update={**BATERIA, **(bateria or {})}),
            "ubicacion": base.ubicacion.model_copy(update=ubicacion or {}),
        }
    )


@pytest.fixture
def datos_24h(monkeypatch):
    monkeypatch.setattr(optimizacion, "generacion_por_kwp", lambda *_: _g())
    monkeypatch.setattr(optimizacion, "perfil_carga", lambda *_: _c())


def test_config_tiene_m2_por_kwp():
    assert cargar_config(EJEMPLO).sistema_fv.m2_por_kwp == 5.5


def test_evaluar_sin_bateria_a_mano():
    # 10 kWp → 5 kWh/h de 6 a 17 h: gen 60; autoconsumo 12 (1 kWh/h); exporta 48; importa 12.
    # Exc1 = min(48, 12) = 12 a CU − Cv = 820; Exc2 = 36 a 350.
    # ahorro = 12·900 + 12·820 + 36·350 = 33 240; CAPEX = 10 · 1000 · 3200 = 32 M.
    f = evaluar(_cfg(), 10, 0, _g(), _c())
    assert list(f) == list(COLUMNAS)
    assert f["gen_kwh"] == pytest.approx(60)
    assert f["autoconsumo_pct"] == pytest.approx(12 / 60)
    assert f["exc1_kwh"] == pytest.approx(12)
    assert f["exc2_kwh"] == pytest.approx(36)
    assert f["ciclos"] == 0
    assert f["ahorro_anio1"] == pytest.approx(33_240)
    assert f["capex"] == pytest.approx(32_000_000)


def test_evaluar_con_bateria_a_mano():
    # Batería ideal (η = 1, DoD = 1), 10 kWh, c_rate 1. Arranca vacía: importa 6 kWh de 0 a 5 h,
    # carga 10 kWh de día (exporta 48 − 10 = 38) y descarga 6 kWh de 18 a 23 h.
    # Exc1 = min(38, 6) = 6 a 820; Exc2 = 32 a 350; autoconsumo = (24 − 6)·900.
    cfg = _cfg(bateria={"eficiencia_ciclo": 1.0, "dod": 1.0, "c_rate": 1.0})
    f = evaluar(cfg, 10, 10, _g(), _c())
    assert f["ciclos"] == pytest.approx(0.6)  # 6 kWh descargados / (10 kWh · DoD 1)
    assert f["autoconsumo_pct"] == pytest.approx((12 + 6) / 60)
    assert f["exc1_kwh"] == pytest.approx(6)
    assert f["exc2_kwh"] == pytest.approx(32)
    assert f["ahorro_anio1"] == pytest.approx(18 * 900 + 6 * 820 + 32 * 350)
    assert f["capex"] == pytest.approx(10 * 1000 * 3200 + 10 * 1_800_000)


def test_evaluar_sin_fv_no_genera():
    f = evaluar(_cfg(), 0, 0, _g(), _c())
    assert f["gen_kwh"] == 0
    assert f["autoconsumo_pct"] == 0
    assert f["capex"] == 0
    assert f["vpn"] == pytest.approx(0)
    assert math.isnan(f["lcoe"])


def test_optimizar_grilla_y_orden(datos_24h):
    # Techo 100 m² / 5.5 = 18.18 kWp → kWp ∈ {0, 5, 10, 15}; kWh ∈ {0, 100, 200}.
    # kWp = 0 solo sin batería → 1 + 3·3 = 10 combinaciones.
    cfg = _cfg(
        sistema_fv={"kwp_min": 0, "kwp_max": 1000, "paso_kwp": 5},
        bateria={"kwh_min": 100, "kwh_max": 200, "paso_kwh": 100},
        ubicacion={"area_techo_m2": 100},
    )
    t = optimizar(cfg)
    assert len(t) == 10
    assert list(t.columns) == list(COLUMNAS)
    assert t["vpn"].is_monotonic_decreasing
    assert set(t["kwp"]) == {0, 5, 10, 15}
    assert set(t["kwh_bat"]) == {0, 100, 200}  # kwh_min = 100 pero siempre entra el 0
    assert not ((t["kwp"] == 0) & (t["kwh_bat"] > 0)).any()


def test_optimizar_respeta_techo_y_tope_agpe(datos_24h):
    # Techo manda: 60 / 5.5 = 10.9 kWp → máximo 10
    cfg = _cfg(
        sistema_fv={"kwp_min": 0, "kwp_max": 1000, "paso_kwp": 5},
        bateria={"kwh_min": 0, "kwh_max": 0, "paso_kwh": 100},
        ubicacion={"area_techo_m2": 60},
    )
    assert optimizar(cfg)["kwp"].max() == 10
    # kwp_max manda: techo holgado pero tope 7 kWp → máximo 5 (grilla de 5 en 5)
    cfg = _cfg(
        sistema_fv={"kwp_min": 0, "kwp_max": 7, "paso_kwp": 5},
        bateria={"kwh_min": 0, "kwh_max": 0, "paso_kwh": 100},
        ubicacion={"area_techo_m2": 10_000},
    )
    assert optimizar(cfg)["kwp"].max() == 5


def test_optimizar_conservacion_de_energia(datos_24h):
    cfg = _cfg(
        sistema_fv={"kwp_min": 0, "kwp_max": 1000, "paso_kwp": 10},
        bateria={"kwh_min": 0, "kwh_max": 20, "paso_kwh": 10},
        ubicacion={"area_techo_m2": 100},
    )
    t = optimizar(cfg)
    # Lo exportado (Exc1 + Exc2) no puede superar lo generado y el autoconsumo es fracción.
    assert (t["exc1_kwh"] + t["exc2_kwh"] <= t["gen_kwh"] + 1e-9).all()
    assert t["autoconsumo_pct"].between(0, 1 + 1e-9).all()
    # kWh generados = kWp · 6 kWh/kWp·día (12 h · 0.5)
    assert t["gen_kwh"].to_numpy() == pytest.approx((t["kwp"] * 6).to_numpy())
