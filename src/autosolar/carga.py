"""Módulo 2 · Perfil de consumo horario.

Contrato:
    perfil_carga(consumo) -> pd.Series
        8760 valores horarios en kWh, mismo índice que solar.generacion_por_kwp.
        - modo "archivo": lee el CSV y valida 8760 filas sin huecos.
        - modo "sintetico": reparte consumo_mensual_kwh según la jornada
          (1_turno, 2_turnos, continua) con días hábiles y fines de semana.

Supuestos de modelado (modo sintético):
    - Forma horaria relativa al pico (=1.0), en PERFILES. Fuera de turno rige la carga base
      (fracción del pico): 1_turno 0.20, 2_turnos 0.25.
    - 1_turno: 7–17 h L-V y 7–12 h sábado. 2_turnos: 6–22 h L-S. Domingos y festivos de
      Colombia 2023 (librería holidays): solo carga base.
    - continua: 24/7 sin distinción de día; de noche (22–6 h) 10 % menos que de día. No hay
      carga base aparte: la noche ya es el nivel mínimo.
    - Cada mes se escala para sumar exactamente consumo_mensual_kwh (todos los meses iguales).
    - Modo archivo: CSV con columna "kwh" horaria (8760 filas) o cada 15 min (35040 filas,
      se suma por hora). El índice es el de 2023, igual que solar. Si el archivo es de un
      año bisiesto (8784 h o 35136 de 15 min), se descarta el 29-feb antes de validar.
"""

from __future__ import annotations

from pathlib import Path

import holidays
import numpy as np
import pandas as pd

from autosolar.config import Consumo

ANIO_INDICE = 2023  # mismo año sin bisiesto que solar.ANIO_INDICE
HORAS_ANIO = 8760
FILAS_15MIN = HORAS_ANIO * 4
HORAS_BISIESTO = 8784  # 2024 bisiesto: 8784 h = 8760 + 29-feb
NOCHE_CONTINUA = 0.90  # factor de la carga nocturna (22–6 h) respecto al día en "continua"


def _forma(turno: tuple[int, int] | None, base: float) -> list[float]:
    """24 factores relativos al pico: 1.0 dentro de [ini, fin) y `base` fuera."""
    forma = [base] * 24
    if turno is not None:
        for h in range(*turno):
            forma[h] = 1.0
    return forma


_NOCHE_CONTINUA = [NOCHE_CONTINUA if (h < 6 or h >= 22) else 1.0 for h in range(24)]

# Forma horaria por jornada y tipo de día (hora local 0–23, relativa al pico = 1.0).
#   "habil" = lunes–viernes, "sabado", "domingo_festivo".
PERFILES: dict[str, dict[str, list[float]]] = {
    "1_turno": {
        "habil": _forma((7, 17), 0.20),
        "sabado": _forma((7, 12), 0.20),
        "domingo_festivo": _forma(None, 0.20),
    },
    "2_turnos": {
        "habil": _forma((6, 22), 0.25),
        "sabado": _forma((6, 22), 0.25),
        "domingo_festivo": _forma(None, 0.25),
    },
    "continua": {
        "habil": _NOCHE_CONTINUA,
        "sabado": _NOCHE_CONTINUA,
        "domingo_festivo": _NOCHE_CONTINUA,
    },
}


def _indice_anio() -> pd.DatetimeIndex:
    return pd.date_range(f"{ANIO_INDICE}-01-01", periods=HORAS_ANIO, freq="h")


def _tipo_dia(indice: pd.DatetimeIndex, festivos: set) -> np.ndarray:
    """Etiqueta cada hora: 'habil', 'sabado' o 'domingo_festivo'."""
    dow = indice.dayofweek.to_numpy()
    es_festivo = np.isin(indice.date, list(festivos))
    tipo = np.where(dow == 5, "sabado", "habil").astype(object)
    tipo[(dow == 6) | es_festivo] = "domingo_festivo"
    return tipo


def _escalar_por_mes(forma: pd.Series, kwh_mes: float) -> pd.Series:
    """Escala la serie para que cada mes sume `kwh_mes` (kWh)."""
    suma_mes = forma.groupby(forma.index.month).transform("sum")
    return forma / suma_mes * kwh_mes


def _sintetico(consumo: Consumo) -> pd.Series:
    indice = _indice_anio()
    festivos = set(holidays.Colombia(years=ANIO_INDICE))
    tipo = _tipo_dia(indice, festivos)
    perfil = PERFILES[consumo.jornada]
    relativo = np.array(
        [perfil[t][h] for t, h in zip(tipo, indice.hour, strict=True)], dtype=float
    )
    serie = pd.Series(relativo, index=indice)
    return _escalar_por_mes(serie, consumo.consumo_mensual_kwh).rename("kwh")


def _desde_archivo(ruta: Path) -> pd.Series:
    df = pd.read_csv(ruta)
    if "kwh" not in df.columns:
        raise ValueError(f"{ruta}: falta la columna 'kwh'")
    valores = pd.to_numeric(df["kwh"], errors="coerce").to_numpy(dtype=float)
    if np.isnan(valores).any():
        raise ValueError(f"{ruta}: hay huecos o valores no numéricos en 'kwh'")
    if (valores < 0).any():
        raise ValueError(f"{ruta}: 'kwh' tiene valores negativos")
    if len(valores) in (HORAS_BISIESTO, HORAS_BISIESTO * 4):
        # Año bisiesto: se quita el 29-feb (año de referencia 2024) antes de validar.
        pasos = len(valores) // HORAS_BISIESTO  # 1 si horario, 4 si de 15 min
        indice = pd.date_range("2024-01-01", periods=len(valores), freq=f"{60 // pasos}min")
        valores = valores[~((indice.month == 2) & (indice.day == 29))]
    if len(valores) == FILAS_15MIN:
        valores = valores.reshape(HORAS_ANIO, 4).sum(axis=1)  # kWh/15 min → kWh/h
    elif len(valores) != HORAS_ANIO:
        raise ValueError(
            f"{ruta}: se esperaban {HORAS_ANIO} filas (horario) o {FILAS_15MIN} (15 min); "
            f"hay {len(valores)}"
        )
    return pd.Series(valores, index=_indice_anio(), name="kwh")


def perfil_carga(consumo: Consumo) -> pd.Series:
    """Consumo horario del año típico (8760 valores, kWh por hora, índice 2023)."""
    if consumo.modo == "archivo":
        return _desde_archivo(Path(consumo.archivo))
    return _sintetico(consumo)
