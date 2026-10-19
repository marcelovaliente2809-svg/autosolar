from pathlib import Path

import holidays
import pandas as pd
import pytest
from matplotlib.figure import Figure

from autosolar import graficas
from autosolar.balance import simular
from autosolar.config import cargar_config
from autosolar.finanzas import flujo_caja
from autosolar.liquidacion import liquidar

EJEMPLO = Path(__file__).parents[1] / "config" / "empresa_ejemplo.yaml"
# 3 días (lun–mié 2023-01-02..04) + sábado 2023-01-07: cubre día hábil y fin de semana
FECHAS = [*pd.date_range("2023-01-02", periods=72, freq="h"),
          *pd.date_range("2023-01-07", periods=24, freq="h")]
INDICE = pd.DatetimeIndex(FECHAS)


@pytest.fixture(scope="module")
def cfg():
    return cargar_config(EJEMPLO)


@pytest.fixture(scope="module")
def balance(cfg):
    g = pd.Series([0.5 if 6 <= h.hour < 18 else 0.0 for h in INDICE], index=INDICE)
    c = pd.Series(1.0, index=INDICE)
    return simular(c, g, 10, 5, cfg.bateria)


@pytest.fixture(scope="module")
def mensual(cfg, balance):
    return liquidar(balance, cfg.tarifa, 10)["mensual"]


def _verificar(fig):
    assert isinstance(fig, Figure)
    assert fig.dpi == graficas.DPI == 300
    assert fig._suptitle is None
    assert all(ax.get_title() == "" for ax in fig.axes)


def test_dia_tipico(cfg, balance):
    fig = graficas.dia_tipico(cfg, balance)
    _verificar(fig)
    assert len(fig.axes) == 2


def test_dias_tipicos_miercoles_de_julio_no_festivo_y_domingo():
    # Julio 2023: 5, 12, 19, 26 son miércoles; el 5 es hábil y el lunes 3 festivo (San Pedro)
    idx = pd.date_range("2023-06-01", "2023-08-31 23:00", freq="h")
    bal = pd.DataFrame(0.0, index=idx, columns=["generacion"])
    habil, finde = graficas._dias_tipicos(bal)
    assert habil.month == 7 and habil.weekday() == 2
    assert habil not in holidays.Colombia(years=2023)
    assert finde.month == 7 and finde.weekday() == 6


def test_dias_tipicos_salta_miercoles_festivo():
    # Semana 18–24 jul 2022: el único miércoles (20, Independencia) es festivo → no se elige
    idx = pd.date_range("2022-07-18", "2022-07-24 23:00", freq="h")
    bal = pd.DataFrame(0.0, index=idx, columns=["generacion"])
    habil, finde = graficas._dias_tipicos(bal)
    assert habil != pd.Timestamp("2022-07-20")
    assert habil not in holidays.Colombia(years=2022)
    assert finde.weekday() == 6


def test_dia_tipico_con_dias_explicitos(cfg, balance):
    _verificar(graficas.dia_tipico(cfg, balance, "2023-01-03", "2023-01-07"))


def test_vpn_vs_kwp_y_lineas_verticales(cfg):
    tabla = pd.DataFrame(
        {
            "kwp": [0, 25, 50, 25, 50],
            "kwh_bat": [0, 0, 0, 100, 100],
            "vpn": [0.0, 1e6, 2e6, 0.5e6, 1.5e6],
        }
    )
    fig = graficas.vpn_vs_kwp(cfg, tabla)
    _verificar(fig)
    ax = fig.axes[0]
    verticales = sorted(
        float(ln.get_xdata()[0]) for ln in ax.lines if len(set(ln.get_xdata())) == 1
    )
    techo = min(cfg.sistema_fv.kwp_max, cfg.ubicacion.area_techo_m2 / cfg.sistema_fv.m2_por_kwp)
    assert 100.0 in verticales and techo in verticales
    # kwh_bat 200 y 500 no están en la tabla: solo 2 curvas con datos
    curvas = [ln.get_label() for ln in ax.lines if not ln.get_label().startswith("_")]
    assert curvas == ["Sin batería", "100 kWh"]


def test_lcoe_vs_valores(cfg):
    fig = graficas.lcoe_vs_valores(cfg, 420.0)
    _verificar(fig)
    assert len(fig.axes[0].patches) == 5


def test_tornado(cfg):
    tabla = pd.DataFrame(
        {
            "variable": ["cu", "capex_fv"],
            "vpn_bajo": [1e6, 3e6],
            "vpn_base": [2e6, 2e6],
            "vpn_alto": [3e6, 1e6],
        }
    )
    _verificar(graficas.tornado(cfg, tabla))


def test_escenarios(cfg):
    tabla = pd.DataFrame(
        {
            "escenario": ["base", "sin_ley1715"],
            "kwp": [100.0, 75.0],
            "kwh_bat": [0.0, 0.0],
            "vpn": [2e6, -1e6],
            "tir": [0.2, 0.1],
            "payback": [4.0, 7.0],
            "autoconsumo_pct": [0.8, 0.9],
        }
    )
    _verificar(graficas.escenarios(cfg, tabla))


def test_flujo_acumulado_marca_payback(cfg):
    args = (10.0, 0.0, 5e7, 15000.0, 0.0)
    sin_ley = cfg.model_copy(deep=True)
    sin_ley.finanzas.incentivos_ley1715 = False
    fig = graficas.flujo_acumulado(cfg, flujo_caja(*args, cfg), flujo_caja(*args, sin_ley))
    _verificar(fig)
    marcadores = [ln for ln in fig.axes[0].lines if ln.get_marker() == "o"]
    assert len(marcadores) == 2


def test_flujo_acumulado_sin_payback(cfg):
    args = (10.0, 0.0, 1.0, 15000.0, 0.0)  # ahorro ínfimo: nunca se recupera
    flujo = flujo_caja(*args, cfg)
    fig = graficas.flujo_acumulado(cfg, flujo, flujo)
    _verificar(fig)
    assert not [ln for ln in fig.axes[0].lines if ln.get_marker() == "o"]


def test_balance_mensual(cfg, mensual):
    fig = graficas.balance_mensual(cfg, mensual)
    _verificar(fig)
    c = fig.axes[0].containers
    assert len(c) == 5  # Generación: autoconsumo, Exc1, Exc2 · Consumo: autoconsumo, importación
    assert c[0].patches[0].get_facecolor() == c[3].patches[0].get_facecolor()  # mismo color
    auto = c[0].datavalues
    # Consumo = autoconsumo + importación = carga
    assert (c[3].datavalues + c[4].datavalues) * 1e3 == pytest.approx(
        mensual["carga_kwh"].to_numpy()
    )
    # Generación = autoconsumo + Exc1 + Exc2
    esperado = auto + c[1].datavalues + c[2].datavalues
    assert esperado * 1e3 == pytest.approx(
        (mensual["carga_kwh"] - mensual["importado_kwh"]
         + mensual["exc1_kwh"] + mensual["exc2_kwh"]).to_numpy()
    )


def test_guardar_png(cfg, mensual, tmp_path):
    destino = tmp_path / "f.png"
    graficas.balance_mensual(cfg, mensual).savefig(destino, dpi=graficas.DPI)
    assert destino.stat().st_size > 0
