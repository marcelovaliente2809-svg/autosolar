"""Módulo 1 · Generación FV horaria.

Contrato:
    generacion_por_kwp(ubicacion, perdidas) -> pd.Series
        8760 valores horarios de kWh producidos por 1 kWp instalado (año típico),
        índice horario. Fuente: PVGIS vía pvlib.iotools.get_pvgis_hourly, con caché en
        data/raw/ (o en $AUTOSOLAR_CACHE_DIR si está definida) para no repetir la descarga.

Supuestos de modelado:
    - Inclinación = ubicacion.inclinacion_deg o, si es None, max(|latitud|, 10) (mínimo
      10° para que el agua lluvia escurra). Azimut sur (180° en pvlib), montaje libre.
    - PVGIS entrega varios años en UTC. Se descarta el 29-feb y se conservan solo los años
      completos (8760 h). Año típico = el año real cuya energía anual está más cerca de la
      mediana de todos los años (empate → el más antiguo); se usa completo, sin promediar.
    - Hora local: huso = round(lon / 15). Al desplazar la serie, las horas que salen por un
      extremo (nocturnas) reentran por el otro: se rota la serie (np.roll).
    - Índice resultante: año 2023 (no bisiesto) a hora local, sin zona horaria.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

from autosolar.config import Ubicacion

RAIZ = Path(__file__).resolve().parents[2]
DIR_RAW = RAIZ / "data" / "raw"
VAR_CACHE = "AUTOSOLAR_CACHE_DIR"  # p. ej. /tmp en Vercel (disco de solo lectura)
ANIO_INDICE = 2023  # año sin bisiesto para el índice de salida
AZIMUT_SUR = 180  # convención pvlib: 180 = sur
HORAS_ANIO = 8760
INCLINACION_MIN = 10.0  # grados


def _descargar(latitud: float, longitud: float, inclinacion: float, perdidas: float) -> pd.DataFrame:
    """Baja de PVGIS la potencia horaria (W) de 1 kWp. Única función que usa la red."""
    datos, *_ = pvlib.iotools.get_pvgis_hourly(
        latitud,
        longitud,
        surface_tilt=inclinacion,
        surface_azimuth=AZIMUT_SUR,
        pvcalculation=True,
        peakpower=1.0,
        loss=perdidas * 100,  # PVGIS recibe porcentaje
        mountingplace="free",
        usehorizon=True,
    )
    return datos[["P"]]


def _ruta_cache(u: Ubicacion, inclinacion: float, perdidas: float) -> Path:
    nombre = f"pvgis_{u.latitud:.4f}_{u.longitud:.4f}_t{inclinacion:.1f}_l{perdidas:.3f}.csv"
    return _dir_cache() / nombre


def _dir_cache() -> Path:
    """Carpeta de la caché: $AUTOSOLAR_CACHE_DIR si está definida; si no, data/raw/."""
    return Path(os.environ[VAR_CACHE]) if os.environ.get(VAR_CACHE) else DIR_RAW


def _inclinacion(u: Ubicacion) -> float:
    """Inclinación en grados: la de la config, o max(|latitud|, 10) si es None."""
    if u.inclinacion_deg is not None:
        return u.inclinacion_deg
    return max(abs(u.latitud), INCLINACION_MIN)


def _tipico_8760(datos: pd.DataFrame, longitud: float) -> pd.Series:
    """Año real más cercano a la mediana, en hora local (8760 kWh/kWp). Entrada: W/kWp en UTC."""
    potencia = datos["P"]
    potencia = potencia[~((potencia.index.month == 2) & (potencia.index.day == 29))]

    anuales = {
        anio: serie.to_numpy()
        for anio, serie in potencia.groupby(potencia.index.year)
        if len(serie) == HORAS_ANIO
    }
    if not anuales:
        raise ValueError(f"Ningún año completo de {HORAS_ANIO} horas en los datos de PVGIS")

    energia = pd.Series({anio: v.sum() / 1000.0 for anio, v in anuales.items()}).sort_index()
    anio_tipico = (energia - energia.median()).abs().idxmin()  # empate → el más antiguo

    desfase = round(longitud / 15)  # horas respecto a UTC (Colombia: -5)
    local = np.roll(anuales[anio_tipico], desfase) / 1000.0

    indice = pd.date_range(f"{ANIO_INDICE}-01-01", periods=HORAS_ANIO, freq="h")
    return pd.Series(local, index=indice, name="kwh_por_kwp")


def generacion_por_kwp(ubicacion: Ubicacion, perdidas: float) -> pd.Series:
    """kWh/h producidos por 1 kWp en un año típico (8760 valores).

    ubicacion: config.ubicacion (latitud, longitud en grados). perdidas: fracción (0.14).
    Usa la caché (data/raw/ o $AUTOSOLAR_CACHE_DIR) si existe; si no, descarga de PVGIS y
    la guarda.
    """
    inclinacion = _inclinacion(ubicacion)
    ruta = _ruta_cache(ubicacion, inclinacion, perdidas)

    if ruta.exists():
        datos = pd.read_csv(ruta, index_col=0, parse_dates=True)
    else:
        datos = _descargar(ubicacion.latitud, ubicacion.longitud, inclinacion, perdidas)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos.to_csv(ruta)

    return _tipico_8760(datos, ubicacion.longitud)
