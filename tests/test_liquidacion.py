"""Pruebas de liquidación: casos de 24 h a mano, regla ≤/> 100 kW, conservación y límites."""

import pandas as pd
import pytest

from autosolar import balance, liquidacion
from autosolar.config import Bateria, Tarifa

TOL = 1e-9


def _tarifa() -> Tarifa:
    return Tarifa(
        operador_red="X",
        nivel_tension=2,
        cu_cop_kwh=900.0,
        componente_comercializacion_cop_kwh=80.0,
        g_cop_kwh=330.0,
        precio_exc2_cop_kwh=350.0,
    )


def _balance(autoconsumo, exportado, importado, descarga_bat=None, inicio="2023-01-02"):
    """DataFrame con las columnas que usa liquidar; una fila por hora."""
    n = len(autoconsumo)
    indice = pd.date_range(inicio, periods=n, freq="h")
    return pd.DataFrame(
        {
            "autoconsumo": autoconsumo,
            "descarga_bat": descarga_bat if descarga_bat is not None else [0.0] * n,
            "exportado": exportado,
            "importado": importado,
        },
        index=indice,
    )


def _dia_exc2():
    """24 h: autoconsumo 20, importado 10, exportado 30 → carga 30, Exc1 = 10, Exc2 = 20."""
    ac, exp, imp = [0.0] * 24, [0.0] * 24, [0.0] * 24
    ac[12], exp[12], imp[0] = 20.0, 30.0, 10.0
    return _balance(ac, exp, imp)


def test_dia_a_mano_hasta_100_kw():
    r = liquidacion.liquidar(_dia_exc2(), _tarifa(), kwp=90)
    # crédito = 900 − 80 = 820
    assert r["valor_credito_cop_kwh"] == pytest.approx(820)
    assert r["exc1_kwh"] == pytest.approx(10)
    assert r["exc2_kwh"] == pytest.approx(20)
    assert r["factura_base_cop"] == pytest.approx(30 * 900)  # 27 000
    assert r["factura_con_sistema_cop"] == pytest.approx(10 * 900 - 10 * 820 - 20 * 350)  # −6 200
    assert r["ahorro_autoconsumo_cop"] == pytest.approx(20 * 900)  # 18 000
    assert r["ahorro_exc1_cop"] == pytest.approx(10 * 820)  # 8 200
    assert r["ahorro_exc2_cop"] == pytest.approx(20 * 350)  # 7 000
    assert r["ahorro_cop"] == pytest.approx(33_200)


def test_misma_energia_90_vs_150_kwp_ahorra_menos_el_segundo():
    bal = _dia_exc2()
    r90 = liquidacion.liquidar(bal, _tarifa(), kwp=90)
    r150 = liquidacion.liquidar(bal, _tarifa(), kwp=150)
    assert r150["valor_credito_cop_kwh"] == pytest.approx(330)  # solo G
    assert r150["ahorro_cop"] < r90["ahorro_cop"]
    # La diferencia es solo Exc1 · (CU − Cv − G) = 10 · 490
    assert r90["ahorro_cop"] - r150["ahorro_cop"] == pytest.approx(10 * 490)
    assert r150["ahorro_cop"] == pytest.approx(28_300)


def test_limite_exacto_100_kw_usa_cu_menos_cv():
    r = liquidacion.liquidar(_dia_exc2(), _tarifa(), kwp=100)
    assert r["valor_credito_cop_kwh"] == pytest.approx(820)
    r = liquidacion.liquidar(_dia_exc2(), _tarifa(), kwp=100.01)
    assert r["valor_credito_cop_kwh"] == pytest.approx(330)


def test_compensacion_es_mensual_no_anual():
    # Enero: Imp 10, Exp 4 → Exc1 4, Exc2 0. Febrero: Imp 2, Exp 8 → Exc1 2, Exc2 6.
    # Neteo anual daría Exc1 = 12 y Exc2 = 0; el mensual da Exc1 = 6 y Exc2 = 6.
    ene = _balance([0.0] * 24, [0.0] * 23 + [4.0], [10.0] + [0.0] * 23, inicio="2023-01-02")
    feb = _balance([0.0] * 24, [0.0] * 23 + [8.0], [2.0] + [0.0] * 23, inicio="2023-02-01")
    bal = pd.concat([ene, feb])
    r = liquidacion.liquidar(bal, _tarifa(), kwp=50)
    assert list(r["mensual"].index) == [1, 2]
    assert r["mensual"].loc[1, "exc2_kwh"] == pytest.approx(0)
    assert r["mensual"].loc[2, "exc1_kwh"] == pytest.approx(2)
    assert r["exc1_kwh"] == pytest.approx(6)
    assert r["exc2_kwh"] == pytest.approx(6)


def test_conservacion_y_limites():
    bal = _balance(
        [1.0, 2.0, 0.0] * 8,
        [0.0, 3.0, 5.0] * 8,
        [4.0, 0.0, 1.0] * 8,
        descarga_bat=[0.5, 0.0, 0.0] * 8,
    )
    r = liquidacion.liquidar(bal, _tarifa(), kwp=150)
    exp, imp = bal["exportado"].sum(), bal["importado"].sum()
    assert r["exc1_kwh"] + r["exc2_kwh"] == pytest.approx(exp)  # todo lo exportado se liquida
    assert r["exc1_kwh"] <= imp + TOL
    assert r["exc2_kwh"] >= 0
    partes = r["ahorro_autoconsumo_cop"] + r["ahorro_exc1_cop"] + r["ahorro_exc2_cop"]
    assert r["ahorro_cop"] == pytest.approx(partes)
    assert r["ahorro_cop"] == pytest.approx(r["mensual"]["ahorro_cop"].sum())
    # la descarga de batería también es energía que no se compra a la red
    carga = (bal["autoconsumo"] + bal["descarga_bat"] + bal["importado"]).sum()
    assert r["factura_base_cop"] == pytest.approx(carga * 900)


def test_sin_sistema_no_hay_ahorro():
    n = 24
    bal = _balance([0.0] * n, [0.0] * n, [5.0] * n)
    r = liquidacion.liquidar(bal, _tarifa(), kwp=0)
    assert r["ahorro_cop"] == pytest.approx(0)
    assert r["factura_con_sistema_cop"] == pytest.approx(r["factura_base_cop"])


def test_con_salida_de_balance_simular():
    bateria = Bateria(
        capex_cop_kwh=1.0, eficiencia_ciclo=0.81, dod=0.5, c_rate=0.5,
        vida_ciclos=1000, kwh_min=0, kwh_max=100, paso_kwh=1,
    )  # fmt: skip
    indice = pd.date_range("2023-03-01", periods=24, freq="h")
    carga = pd.Series([10.0] * 24, index=indice)
    sol = pd.Series([0.0] * 6 + [1.0] * 12 + [0.0] * 6, index=indice)  # 1 kWh/h por kWp
    bal = balance.simular(carga, sol, kwp=20, kwh_bat=0, bateria=bateria)
    r = liquidacion.liquidar(bal, _tarifa(), kwp=20)
    # 12 h · min(20, 10) = 120 kWh autoconsumo; exporta 12 · 10 = 120; importa 12 · 10 = 120
    assert r["exc1_kwh"] == pytest.approx(120)
    assert r["exc2_kwh"] == pytest.approx(0)
    assert r["ahorro_cop"] == pytest.approx(120 * 900 + 120 * 820)


def test_exige_indice_de_fechas():
    bal = _dia_exc2().reset_index(drop=True)
    with pytest.raises(TypeError):
        liquidacion.liquidar(bal, _tarifa(), kwp=50)
