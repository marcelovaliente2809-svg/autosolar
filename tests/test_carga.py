"""Pruebas de carga: casos pequeños calculables a mano y conservación mensual."""

import numpy as np
import pandas as pd
import pytest

from autosolar import carga
from autosolar.config import Consumo


def _consumo(jornada="1_turno", kwh=30000.0) -> Consumo:
    return Consumo(modo="sintetico", consumo_mensual_kwh=kwh, jornada=jornada)


def test_perfiles_1_turno_forma_horaria():
    habil = carga.PERFILES["1_turno"]["habil"]
    assert len(habil) == 24
    assert habil[6] == 0.20 and habil[7] == 1.0 and habil[16] == 1.0 and habil[17] == 0.20
    sabado = carga.PERFILES["1_turno"]["sabado"]
    assert sabado[11] == 1.0 and sabado[12] == 0.20
    assert set(carga.PERFILES["1_turno"]["domingo_festivo"]) == {0.20}


def test_perfiles_2_turnos_y_continua():
    p2 = carga.PERFILES["2_turnos"]["habil"]
    assert p2[5] == 0.25 and p2[6] == 1.0 and p2[21] == 1.0 and p2[22] == 0.25
    pc = carga.PERFILES["continua"]["habil"]
    assert pc[12] == 1.0 and pc[23] == 0.90 and pc[3] == 0.90 and pc[6] == 1.0


def test_escalar_por_mes_24_horas_a_mano():
    # Dos "meses" de 24 h cada uno: ene (todo 1.0) y feb (todo 2.0) → ambos deben sumar 100.
    indice = pd.date_range("2023-01-31 00:00", periods=48, freq="h")  # 31-ene y 1-feb
    forma = pd.Series([1.0] * 24 + [2.0] * 24, index=indice)
    esc = carga._escalar_por_mes(forma, 100.0)
    assert esc[esc.index.month == 1].sum() == pytest.approx(100.0)
    assert esc[esc.index.month == 2].sum() == pytest.approx(100.0)
    assert esc.iloc[0] == pytest.approx(100.0 / 24)


@pytest.mark.parametrize("jornada", ["1_turno", "2_turnos", "continua"])
def test_conservacion_mensual_y_longitud(jornada):
    serie = carga.perfil_carga(_consumo(jornada, 30000.0))
    assert len(serie) == 8760
    assert serie.index[0] == pd.Timestamp("2023-01-01 00:00")
    assert serie.index[-1] == pd.Timestamp("2023-12-31 23:00")
    mensual = serie.groupby(serie.index.month).sum()
    assert np.allclose(mensual, 30000.0)
    assert (serie > 0).all()


def test_domingo_y_festivo_solo_base_1_turno():
    serie = carga.perfil_carga(_consumo("1_turno"))
    # 2023-01-09 (lunes festivo, Reyes observado) y 2023-01-08 (domingo): sin pico de día.
    festivo = serie["2023-01-09"]
    domingo = serie["2023-01-08"]
    habil = serie["2023-01-10"]
    assert festivo.nunique() == 1 and domingo.nunique() == 1
    assert festivo.iloc[0] == pytest.approx(domingo.iloc[0])
    # Relación base/pico = 0.20 en un día hábil (mismo mes → mismo factor de escala).
    assert habil.min() / habil.max() == pytest.approx(0.20)
    assert festivo.iloc[0] == pytest.approx(habil.min())


def test_archivo_horario_8760(tmp_path):
    ruta = tmp_path / "h.csv"
    pd.DataFrame({"kwh": np.arange(8760, dtype=float)}).to_csv(ruta, index=False)
    c = Consumo(modo="archivo", archivo=ruta)
    serie = carga.perfil_carga(c)
    assert len(serie) == 8760
    assert serie.iloc[10] == 10.0
    assert serie.sum() == pytest.approx(np.arange(8760).sum())


def test_archivo_15min_se_remuestrea_a_hora(tmp_path):
    ruta = tmp_path / "q.csv"
    pd.DataFrame({"kwh": np.full(35040, 0.25)}).to_csv(ruta, index=False)
    serie = carga.perfil_carga(Consumo(modo="archivo", archivo=ruta))
    assert len(serie) == 8760
    assert np.allclose(serie, 1.0)  # 4 × 0.25 kWh = 1 kWh por hora


def test_archivo_bisiesto_quita_29_feb(tmp_path):
    # 2024: el 29-feb ocupa las horas 1416–1439 (0-based). Se marcan con 100 para detectarlas.
    horas = np.ones(8784)
    horas[1416:1440] = 100.0
    ruta = tmp_path / "bis.csv"
    pd.DataFrame({"kwh": horas}).to_csv(ruta, index=False)
    serie = carga.perfil_carga(Consumo(modo="archivo", archivo=ruta))
    assert len(serie) == 8760
    assert serie.max() == 1.0 and serie.sum() == pytest.approx(8760.0)

    # Mismo caso de 15 min: 35136 filas, el 29-feb ocupa los cuartos 5664–5759.
    cuartos = np.full(35136, 0.25)
    cuartos[5664:5760] = 25.0
    ruta15 = tmp_path / "bis15.csv"
    pd.DataFrame({"kwh": cuartos}).to_csv(ruta15, index=False)
    serie15 = carga.perfil_carga(Consumo(modo="archivo", archivo=ruta15))
    assert len(serie15) == 8760
    assert np.allclose(serie15, 1.0)


@pytest.mark.parametrize("filas", [8759, 8761, 20000])
def test_archivo_longitud_invalida(tmp_path, filas):
    ruta = tmp_path / "x.csv"
    pd.DataFrame({"kwh": np.ones(filas)}).to_csv(ruta, index=False)
    with pytest.raises(ValueError, match="filas"):
        carga.perfil_carga(Consumo(modo="archivo", archivo=ruta))


def test_archivo_con_huecos_o_sin_columna(tmp_path):
    valores = np.ones(8760)
    valores[5] = np.nan
    ruta = tmp_path / "n.csv"
    pd.DataFrame({"kwh": valores}).to_csv(ruta, index=False)
    with pytest.raises(ValueError, match="huecos"):
        carga.perfil_carga(Consumo(modo="archivo", archivo=ruta))
    ruta2 = tmp_path / "s.csv"
    pd.DataFrame({"consumo": np.ones(8760)}).to_csv(ruta2, index=False)
    with pytest.raises(ValueError, match="columna"):
        carga.perfil_carga(Consumo(modo="archivo", archivo=ruta2))
