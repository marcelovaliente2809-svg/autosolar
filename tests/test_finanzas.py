import math
from pathlib import Path

import numpy as np
import pytest

from autosolar.config import cargar_config
from autosolar.finanzas import flujo_caja, kpis

EJEMPLO = Path(__file__).parents[1] / "config" / "empresa_ejemplo.yaml"


def _cfg(declara_renta=True, **cambios):
    """Config de ejemplo con números redondos; `cambios` pisa campos por sección."""
    base = cargar_config(EJEMPLO)
    por_seccion = {
        "sistema_fv": {"capex_cop_wp": 1000.0, "opex_pct_capex": 0.01, "degradacion_anual": 0.0},
        "tarifa": {"escalamiento_anual": 0.0},
        "bateria": {"capex_cop_kwh": 1_000_000.0},
        "finanzas": {
            "horizonte_anios": 3,
            "tasa_descuento": 0.10,
            "tasa_renta": 0.35,
            "inflacion": 0.0,
            "anios_depreciacion": 3,
            "anios_depreciacion_normal": 3,  # igual que la acelerada: aísla cada prueba
            "incentivos_ley1715": False,
            "renta_liquida_anual_cop": 2e9,
        },
    }
    for seccion, campos in cambios.items():
        por_seccion[seccion].update(campos)
    actualiza = {
        nombre: getattr(base, nombre).model_copy(update=campos)
        for nombre, campos in por_seccion.items()
    }
    actualiza["empresa"] = base.empresa.model_copy(update={"declara_renta": declara_renta})
    return base.model_copy(update=actualiza)


def _flujo(cfg, kwp=10, kwh_bat=0, ahorro=4e6, gen=15_000, ciclos=0):
    return flujo_caja(kwp, kwh_bat, ahorro, gen, ciclos, cfg)


def test_flujo_3_anios_a_mano_sin_incentivos():
    # CAPEX = 10 kWp · 1000 · 1000 COP/Wp = 10 000 000; OPEX = 1 % = 100 000/año
    # FC_t = (4 000 000 − 100 000)·0.65 + 0.35·(10 000 000/3) = 3 701 666.67
    fc = 3_900_000 * 0.65 + 0.35 * 10_000_000 / 3
    fl = _flujo(_cfg())
    assert list(fl.index) == [0, 1, 2, 3]
    assert fl["flujo"].tolist() == pytest.approx([-10_000_000, fc, fc, fc])

    k = kpis(fl, _cfg())
    anualidad = 1 / 1.1 + 1 / 1.1**2 + 1 / 1.1**3
    assert k["vpn"] == pytest.approx(-10_000_000 + fc * anualidad)
    assert -10_000_000 + sum(fc / (1 + k["tir"]) ** t for t in (1, 2, 3)) == pytest.approx(
        0, abs=1e-3
    )
    assert k["payback_simple"] == pytest.approx(2 + (10_000_000 - 2 * fc) / fc)
    assert math.isnan(k["payback_descontado"])  # VP de 3 años (9.2 M) < CAPEX (10 M)
    assert k["lcoe"] == pytest.approx((10_000_000 + 100_000 * anualidad) / (15_000 * anualidad))


def test_escalamiento_degradacion_e_inflacion():
    cfg = _cfg(
        declara_renta=False,
        tarifa={"escalamiento_anual": 0.04},
        sistema_fv={"degradacion_anual": 0.005},
        finanzas={"inflacion": 0.03},
    )
    fl = _flujo(cfg)
    ahorro = [4e6, 4e6 * 1.04 * 0.995, 4e6 * (1.04 * 0.995) ** 2]
    opex = [100_000, 100_000 * 1.03, 100_000 * 1.03**2]
    assert fl["ahorro"].tolist()[1:] == pytest.approx(ahorro)
    assert fl["opex"].tolist()[1:] == pytest.approx(opex)
    assert fl["gen_kwh"].tolist()[1:] == pytest.approx([15_000 * 0.995**k for k in range(3)])
    assert fl["flujo"].tolist()[1:] == pytest.approx([a - o for a, o in zip(ahorro, opex)])


def test_con_incentivos_vpn_mayor():
    sin = _cfg()
    con = _cfg(finanzas={"incentivos_ley1715": True})
    fl_sin, fl_con = _flujo(sin), _flujo(con)
    # deducción = 50 % · 10 M = 5 M, cabe en el año 1 (tope = 1 000 M)
    assert fl_con["deduccion"].tolist() == pytest.approx([0, 5e6, 0, 0])
    assert fl_con["flujo"][1] - fl_sin["flujo"][1] == pytest.approx(0.35 * 5e6)
    assert kpis(fl_con, con)["vpn"] > kpis(fl_sin, sin)["vpn"]
    assert kpis(fl_con, con)["vpn"] - kpis(fl_sin, sin)["vpn"] == pytest.approx(0.35 * 5e6 / 1.1)


def test_depreciacion_normal_sin_incentivos_y_acelerada_con_incentivos():
    # CAPEX 10 M: 10 años → 1 M/año; 3 años → 3.33 M/año
    base = {"anios_depreciacion_normal": 10, "horizonte_anios": 12}
    sin = _flujo(_cfg(finanzas=base))
    con = _flujo(_cfg(finanzas={**base, "incentivos_ley1715": True}))
    assert sin["depreciacion"].tolist() == pytest.approx([0] + [1e6] * 10 + [0, 0])
    assert con["depreciacion"].tolist() == pytest.approx([0] + [10e6 / 3] * 3 + [0] * 9)
    assert sin["depreciacion"].sum() == pytest.approx(10_000_000)  # conservación del CAPEX


def test_deduccion_limitada_por_renta_liquida():
    # tope anual = 50 % · 4 M = 2 M → 2 M, 2 M, 1 M (lo más rápido posible)
    cfg = _cfg(finanzas={"incentivos_ley1715": True, "renta_liquida_anual_cop": 4e6})
    assert _flujo(cfg)["deduccion"].tolist() == pytest.approx([0, 2e6, 2e6, 1e6])


def test_deduccion_maximo_15_anios():
    cfg = _cfg(
        finanzas={
            "incentivos_ley1715": True,
            "renta_liquida_anual_cop": 1e5,  # tope 50 000/año → no alcanza en 15 años
            "horizonte_anios": 20,
        }
    )
    ded = _flujo(cfg)["deduccion"].to_numpy()
    assert ded[1:16] == pytest.approx(5e4)
    assert not ded[16:].any()
    assert ded.sum() <= 0.5 * 10_000_000


def test_sin_declarar_renta_no_hay_impuestos_ni_incentivos():
    cfg = _cfg(declara_renta=False, finanzas={"incentivos_ley1715": True})
    fl = _flujo(cfg)
    assert not fl[["impuestos", "escudo_fiscal", "deduccion", "depreciacion"]].to_numpy().any()
    assert fl["flujo"].tolist() == pytest.approx([-10_000_000] + [3_900_000] * 3)


def test_capex_incluye_bateria_y_se_deprecia():
    cfg = _cfg()
    fl = _flujo(cfg, kwp=10, kwh_bat=5)  # 10 M + 5 kWh · 1 M = 15 M
    assert fl["capex"][0] == pytest.approx(15_000_000)
    assert fl["depreciacion"].tolist() == pytest.approx([0, 5e6, 5e6, 5e6])
    assert fl["opex"][1] == pytest.approx(150_000)


@pytest.mark.parametrize(
    ("ciclos", "vida_cal", "esperado"),
    [
        (600, 12, [10, 20]),  # 6000/600 = 10 años < 12 → manda el ciclado
        (300, 12, [12, 24]),  # 6000/300 = 20 años > 12 → manda el calendario
        (550, 12, [11, 22]),  # 6000/550 = 10.9 → se cumple durante el año 11
        (0, 12, [12, 24]),  # sin ciclos: solo calendario
        (240, 30, []),  # 6000/240 = 25 = N → no se repone en el último año
    ],
)
def test_reposicion_en_el_anio_correcto(ciclos, vida_cal, esperado):
    cfg = _cfg(
        declara_renta=False,
        finanzas={"horizonte_anios": 25},
        bateria={"vida_ciclos": 6000, "vida_calendario_anios": vida_cal},
    )
    fl = _flujo(cfg, kwh_bat=100, ciclos=ciclos)
    anios = fl.index[fl["reposicion"] > 0].tolist()
    assert anios == esperado
    assert fl["reposicion"][anios].tolist() == pytest.approx([100e6] * len(anios))  # costo original
    for a in anios:
        assert fl["flujo"][a] == pytest.approx(fl["ahorro"][a] - fl["opex"][a] - 100e6)


def test_sin_bateria_no_hay_reposicion():
    cfg = _cfg(finanzas={"horizonte_anios": 25})
    assert not _flujo(cfg, kwh_bat=0, ciclos=600)["reposicion"].any()


def test_lcoe_incluye_reposiciones():
    cfg = _cfg(
        declara_renta=False,
        finanzas={"horizonte_anios": 4},
        bateria={"vida_calendario_anios": 2},
    )
    fl = _flujo(cfg, kwp=0, kwh_bat=1, gen=1000)  # CAPEX 1 M, OPEX 10 000, repone en año 2
    r = 0.10
    costos = 1e6 + sum(1e4 / (1 + r) ** t for t in range(1, 5)) + 1e6 / (1 + r) ** 2
    gen = sum(1000 / (1 + r) ** t for t in range(1, 5))
    assert kpis(fl, cfg)["lcoe"] == pytest.approx(costos / gen)


def test_tir_nan_si_no_hay_cambio_de_signo():
    cfg = _cfg(declara_renta=False)  # sin ahorro todos los flujos son negativos
    fl = _flujo(cfg, ahorro=0.0)
    assert np.isnan(kpis(fl, cfg)["tir"])
