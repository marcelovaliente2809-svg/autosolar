"""Pruebas de balance: día de 24 h a mano, conservación, límites y velocidad."""

import time

import numpy as np
import pandas as pd
import pytest

from autosolar import balance
from autosolar.config import Bateria

TOL = 1e-9


def _bateria(eficiencia_ciclo=0.81, dod=0.5, c_rate=0.5) -> Bateria:
    # eficiencia_ciclo = 0.81 → √η = 0.9 exacto para cuentas a mano
    return Bateria(
        capex_cop_kwh=1.0,
        eficiencia_ciclo=eficiencia_ciclo,
        dod=dod,
        c_rate=c_rate,
        vida_ciclos=1000,
        kwh_min=0,
        kwh_max=100,
        paso_kwh=1,
    )


def _serie(valores, inicio="2023-01-02") -> pd.Series:
    return pd.Series(
        np.asarray(valores, dtype=float),
        index=pd.date_range(inicio, periods=len(valores), freq="h"),
    )


def _dia_a_mano():
    """h0-5: gen 0, carga 2 · h6-9: gen 6, carga 2 · h10-11: gen 0, carga 8 · h12-23: gen 0, carga 1."""
    carga = [2] * 6 + [2] * 4 + [8] * 2 + [1] * 12
    gen = [0] * 6 + [6] * 4 + [0] * 14
    return _serie(carga), _serie(gen)


def test_dia_24_horas_a_mano():
    # Batería 10 kWh, dod 0.5 → SOC en [5, 10]; pmax = 0.5·10 = 5 kW; √η = 0.9. kwp = 1.
    carga, gen = _dia_a_mano()
    df = balance.simular(carga, gen, kwp=1.0, kwh_bat=10.0, bateria=_bateria())

    # h0-5: batería en mínimo y sin sol → todo importado
    assert df["importado"].iloc[:6].tolist() == [2.0] * 6
    assert df["soc"].iloc[:6].tolist() == [5.0] * 6
    # h6: excedente 4 ≤ pmax y cabe (espacio 5/0.9=5.56) → carga 4, SOC 5 + 3.6
    assert df["carga_bat"].iloc[6] == pytest.approx(4.0)
    assert df["soc"].iloc[6] == pytest.approx(8.6)
    assert df["exportado"].iloc[6] == pytest.approx(0.0)
    # h7: solo caben (10 − 8.6)/0.9 = 14/9 kWh → SOC 10, el resto se exporta
    assert df["carga_bat"].iloc[7] == pytest.approx(14 / 9)
    assert df["soc"].iloc[7] == pytest.approx(10.0)
    assert df["exportado"].iloc[7] == pytest.approx(4 - 14 / 9)
    # h8-9: batería llena → exporta los 4
    assert df["exportado"].iloc[8:10].tolist() == pytest.approx([4.0, 4.0])
    # h10: déficit 8; energía útil (10−5)·0.9 = 4.5 < pmax 5 → descarga 4.5, importa 3.5
    assert df["descarga_bat"].iloc[10] == pytest.approx(4.5)
    assert df["importado"].iloc[10] == pytest.approx(3.5)
    assert df["soc"].iloc[10] == pytest.approx(5.0)
    # h11: batería vacía → importa 8
    assert df["importado"].iloc[11] == pytest.approx(8.0)
    # Totales del día
    assert df["autoconsumo"].sum() == pytest.approx(8.0)
    assert df["carga_bat"].sum() == pytest.approx(4 + 14 / 9)
    assert df["descarga_bat"].sum() == pytest.approx(4.5)
    assert df["exportado"].sum() == pytest.approx(8 + 4 - 14 / 9 + 0.0)
    assert df["importado"].sum() == pytest.approx(35.5)


def test_sin_bateria_camino_vectorizado():
    carga, gen = _dia_a_mano()
    df = balance.simular(carga, gen, kwp=1.0, kwh_bat=0.0, bateria=_bateria())
    assert list(df.columns) == list(balance.COLUMNAS)
    assert (df["carga_bat"] == 0).all() and (df["descarga_bat"] == 0).all()
    assert (df["soc"] == 0).all()
    # h6: gen 6, carga 2 → autoconsumo 2, exporta 4. h10: déficit 8 todo importado.
    assert df["autoconsumo"].iloc[6] == 2.0 and df["exportado"].iloc[6] == 4.0
    assert df["importado"].iloc[10] == 8.0
    assert df["exportado"].sum() == pytest.approx(16.0)


def _escenario_aleatorio(n=8760, semilla=7):
    rng = np.random.default_rng(semilla)
    horas = np.arange(n) % 24
    sol = np.clip(np.sin((horas - 6) / 12 * np.pi), 0, None) * rng.uniform(0.3, 1.0, n)
    carga = _serie(rng.uniform(20, 120, n), inicio="2023-01-01")
    gen = pd.Series(sol, index=carga.index)
    return carga, gen


@pytest.mark.parametrize("kwh_bat", [0.0, 50.0, 400.0])
def test_conservacion_y_limites(kwh_bat):
    carga, gen = _escenario_aleatorio()
    bat = _bateria(eficiencia_ciclo=0.88, dod=0.9, c_rate=0.4)
    kwp = 150.0
    df = balance.simular(carga, gen, kwp, kwh_bat, bat)
    r = bat.eficiencia_ciclo**0.5

    # Conservación de energía por el lado de la generación y de la carga
    np.testing.assert_allclose(
        df["generacion"], df["autoconsumo"] + df["carga_bat"] + df["exportado"], atol=TOL
    )
    np.testing.assert_allclose(
        carga, df["autoconsumo"] + df["descarga_bat"] + df["importado"], atol=TOL
    )
    # Balance de la batería: carga·√η − descarga/√η = ΔSOC (SOC inicial = mínimo)
    soc = df["soc"].to_numpy()
    soc_ini = (1 - bat.dod) * kwh_bat
    d_soc = np.diff(np.concatenate([[soc_ini], soc]))
    np.testing.assert_allclose(
        df["carga_bat"] * r - df["descarga_bat"] / r, d_soc, atol=TOL
    )
    # Límites de SOC y de potencia
    assert soc.min() >= soc_ini - TOL and soc.max() <= kwh_bat + TOL
    pmax = bat.c_rate * kwh_bat
    assert df["carga_bat"].max() <= pmax + TOL
    assert df["descarga_bat"].max() <= pmax + TOL
    # Sin flujos negativos
    assert (df[list(balance.COLUMNAS)] >= -TOL).all().all()
    # Nunca carga y descarga en la misma hora, ni exporta e importa en la misma hora
    assert ((df["carga_bat"] > 0) & (df["descarga_bat"] > 0)).sum() == 0
    assert ((df["exportado"] > 0) & (df["importado"] > 0)).sum() == 0


def test_bateria_no_carga_desde_la_red():
    # Sin generación nunca hay carga de batería, aunque la batería esté vacía.
    carga = _serie([5.0] * 24)
    gen = _serie([0.0] * 24)
    df = balance.simular(carga, gen, kwp=10.0, kwh_bat=20.0, bateria=_bateria())
    assert (df["carga_bat"] == 0).all()
    assert (df["soc"] == 10.0).all()  # (1 − 0.5)·20 = mínimo, sin cambio
    assert (df["importado"] == 5.0).all()


def test_largos_distintos_y_negativos():
    carga, gen = _dia_a_mano()
    with pytest.raises(ValueError):
        balance.simular(carga, gen.iloc[:-1], 1.0, 10.0, _bateria())
    with pytest.raises(ValueError):
        balance.simular(carga, gen, 1.0, -1.0, _bateria())


def test_8760_horas_menos_de_50_ms():
    carga, gen = _escenario_aleatorio()
    bat = _bateria(eficiencia_ciclo=0.9, dod=0.9, c_rate=0.5)
    balance.simular(carga, gen, 150.0, 300.0, bat)  # calentamiento
    mejor = min(
        _tiempo(lambda: balance.simular(carga, gen, 150.0, 300.0, bat)) for _ in range(5)
    )
    assert mejor < 0.050, f"simulación de 8760 h tardó {mejor * 1000:.1f} ms"


def _tiempo(f) -> float:
    t0 = time.perf_counter()
    f()
    return time.perf_counter() - t0
