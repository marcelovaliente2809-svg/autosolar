"""Pruebas de solar: sin red, con un DataFrame falso en lugar de PVGIS."""

import numpy as np
import pandas as pd
import pytest

from autosolar import solar
from autosolar.config import Ubicacion

UBICACION = Ubicacion(latitud=4.7, longitud=-74.1, area_techo_m2=1000)


def _falso_pvgis(anios=(2019, 2020), potencia_w=500.0) -> pd.DataFrame:
    """Potencia constante (W) en UTC, con años 2019 y 2020 (2020 es bisiesto)."""
    indice = pd.date_range(f"{anios[0]}-01-01", f"{anios[-1]}-12-31 23:00", freq="h", tz="UTC")
    return pd.DataFrame({"P": potencia_w}, index=indice)


def test_tipico_tiene_8760_y_convierte_w_a_kwh():
    serie = solar._tipico_8760(_falso_pvgis(potencia_w=500.0), longitud=-74.1)
    assert len(serie) == 8760
    assert serie.index[0] == pd.Timestamp("2023-01-01 00:00")
    assert serie.index[-1] == pd.Timestamp("2023-12-31 23:00")
    assert np.allclose(serie, 0.5)  # 500 W durante 1 h = 0.5 kWh


def test_elige_el_anio_mas_cercano_a_la_mediana():
    # Energías anuales: 2018 → 876 kWh, 2019 → 2628, 2020 → 3066 (kWp). Mediana = 2628.
    datos = pd.concat(
        [_falso_pvgis(anios=(a, a), potencia_w=w) for a, w in [(2018, 100), (2019, 300), (2020, 350)]]
    )
    serie = solar._tipico_8760(datos, longitud=-74.1)
    assert np.allclose(serie, 0.3)


def test_con_mediana_entre_dos_anios_elige_el_mas_cercano():
    # Dos años: la mediana es el punto medio, empate → el más antiguo.
    datos = pd.concat(
        [_falso_pvgis(anios=(a, a), potencia_w=w) for a, w in [(2019, 200), (2020, 400)]]
    )
    serie = solar._tipico_8760(datos, longitud=-74.1)
    assert np.allclose(serie, 0.2)


def test_descarta_29_feb_y_anios_incompletos():
    completo = _falso_pvgis(anios=(2020, 2020), potencia_w=300.0)  # bisiesto: 8784 h
    parcial = _falso_pvgis(anios=(2021, 2021), potencia_w=900.0).iloc[:2000]
    serie = solar._tipico_8760(pd.concat([completo, parcial]), longitud=-74.1)
    assert len(serie) == 8760
    assert np.allclose(serie, 0.3)


def test_pasa_a_hora_local_utc_menos_5():
    datos = _falso_pvgis(anios=(2019, 2019), potencia_w=0.0)
    datos.loc["2019-06-15 17:00", "P"] = 1000.0  # 17:00 UTC = 12:00 local
    serie = solar._tipico_8760(datos, longitud=-74.1)
    assert serie.idxmax() == pd.Timestamp("2023-06-15 12:00")
    assert serie.max() == pytest.approx(1.0)


def test_horas_que_salen_reentran_por_el_otro_extremo():
    datos = _falso_pvgis(anios=(2019, 2019), potencia_w=0.0)
    datos.loc["2019-01-01 02:00", "P"] = 1000.0  # 02:00 UTC = 21:00 local del 31-dic
    serie = solar._tipico_8760(datos, longitud=-74.1)
    assert serie.idxmax() == pd.Timestamp("2023-12-31 21:00")


def test_conservacion_de_energia_anual():
    """La energía anual del típico = la del año elegido en la fuente (sin 29-feb)."""
    datos = _falso_pvgis(anios=(2019, 2019), potencia_w=0.0)
    datos["P"] = np.linspace(0, 900, len(datos))
    serie = solar._tipico_8760(datos, longitud=-74.1)
    assert serie.sum() == pytest.approx(datos["P"].sum() / 1000.0)
    assert (serie >= 0).all()


def test_inclinacion_por_defecto_y_explicita():
    def u(lat, incl=None):
        return Ubicacion(latitud=lat, longitud=-74.1, area_techo_m2=100, inclinacion_deg=incl)

    assert solar._inclinacion(u(4.7)) == 10.0  # piso de 10°
    assert solar._inclinacion(u(-20.0)) == 20.0  # |latitud| cuando supera 10°
    assert solar._inclinacion(u(4.7, 15.0)) == 15.0  # valor de la config


def test_falla_si_faltan_horas():
    with pytest.raises(ValueError):
        solar._tipico_8760(_falso_pvgis().iloc[:1000], longitud=-74.1)


def test_generacion_descarga_una_vez_y_usa_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(solar, "DIR_RAW", tmp_path)
    llamadas = []

    def falso(lat, lon, incl, perd):
        llamadas.append((lat, lon, incl, perd))
        return _falso_pvgis()

    monkeypatch.setattr(solar, "_descargar", falso)

    s1 = solar.generacion_por_kwp(UBICACION, 0.14)
    s2 = solar.generacion_por_kwp(UBICACION, 0.14)

    assert len(llamadas) == 1  # la segunda sale de la caché
    assert llamadas[0] == (4.7, -74.1, 10.0, 0.14)  # inclinación = max(|lat|, 10)
    assert len(list(tmp_path.glob("pvgis_*.csv"))) == 1
    assert len(s1) == 8760
    assert np.allclose(s1, s2)
