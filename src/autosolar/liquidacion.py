"""Módulo 4 · Liquidación de excedentes y factura según CREG 174 de 2021.

Contrato:
    liquidar(balance, tarifa, kwp) -> dict
        Ahorro anual en COP desglosado: energía autoconsumida, Exc1 (créditos de energía,
        hasta lo importado en el periodo) y Exc2 (excedentes por encima de lo importado,
        valorados a precio de bolsa o Mc según tarifa.valoracion_exc2).
        Las reglas normativas están en la skill normativa-agpe.

Supuestos de modelado:
    - balance: salida de balance.simular, con índice DatetimeIndex. Periodo = mes calendario.
    - Por mes: Imp = Σ importado, Exp = Σ exportado, Exc1 = min(Exp, Imp),
      Exc2 = max(0, Exp − Imp).
    - Valor del crédito por kWh de Exc1: kwp ≤ LIMITE_AGPE_MENOR_KWP → CU − Cv;
      kwp > LIMITE_AGPE_MENOR_KWP → G.  Exc2 se paga a tarifa.precio_exc2_cop_kwh.
    - carga = autoconsumo + descarga_bat + importado (balance del módulo 3), así que la
      energía evitada de la red es autoconsumo + descarga_bat y se valora a CU.
    - factura_base = Σ carga·CU; factura_con_sistema = Imp·CU − Exc1·valor_credito
      − Exc2·precio_exc2 (puede ser negativa si el pago por excedentes supera lo importado).
    - ahorro = factura_base − factura_con_sistema = autoconsumo + Exc1 + Exc2 (COP).

Salida (dict):
    ahorro_cop, ahorro_autoconsumo_cop, ahorro_exc1_cop, ahorro_exc2_cop,
    factura_base_cop, factura_con_sistema_cop, exc1_kwh, exc2_kwh, valor_credito_cop_kwh,
    mensual (DataFrame, índice mes 1..12).
    liquidar_sumas(carga_kwh, importado_kwh, exportado_kwh, tarifa, kwp) -> dict
        Lo mismo sin `mensual`, desde las sumas mensuales (arrays de igual largo, un valor
        por mes): evita armar un balance horario por combinación en la optimización.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from autosolar.config import LIMITE_AGPE_MENOR_KWP, Tarifa

COLUMNAS_MENSUAL = (
    "carga_kwh",
    "importado_kwh",
    "exportado_kwh",
    "exc1_kwh",
    "exc2_kwh",
    "factura_base_cop",
    "factura_con_sistema_cop",
    "ahorro_autoconsumo_cop",
    "ahorro_exc1_cop",
    "ahorro_exc2_cop",
    "ahorro_cop",
)


def valor_credito_cop_kwh(tarifa: Tarifa, kwp: float) -> float:
    """COP por kWh de Exc1: CU − Cv si kwp ≤ 100; solo G si kwp > 100."""
    if kwp <= LIMITE_AGPE_MENOR_KWP:
        return tarifa.cu_cop_kwh - tarifa.componente_comercializacion_cop_kwh
    return tarifa.g_cop_kwh


def _columnas(
    carga_kwh: np.ndarray, imp: np.ndarray, exp: np.ndarray, tarifa: Tarifa, kwp: float
) -> dict[str, np.ndarray]:
    """Columnas de COLUMNAS_MENSUAL a partir de las sumas mensuales (arrays por mes)."""
    cu = tarifa.cu_cop_kwh
    precio_exc2 = tarifa.precio_exc2_cop_kwh
    credito = valor_credito_cop_kwh(tarifa, kwp)

    exc1 = np.minimum(exp, imp)
    exc2 = np.maximum(exp - imp, 0.0)
    factura_base = carga_kwh * cu
    factura_con = imp * cu - exc1 * credito - exc2 * precio_exc2
    return {
        "carga_kwh": carga_kwh,
        "importado_kwh": imp,
        "exportado_kwh": exp,
        "exc1_kwh": exc1,
        "exc2_kwh": exc2,
        "factura_base_cop": factura_base,
        "factura_con_sistema_cop": factura_con,
        "ahorro_autoconsumo_cop": (carga_kwh - imp) * cu,
        "ahorro_exc1_cop": exc1 * credito,
        "ahorro_exc2_cop": exc2 * precio_exc2,
        "ahorro_cop": factura_base - factura_con,
    }


def _totales(cols: dict[str, np.ndarray], tarifa: Tarifa, kwp: float) -> dict:
    return {
        "ahorro_cop": float(cols["ahorro_cop"].sum()),
        "ahorro_autoconsumo_cop": float(cols["ahorro_autoconsumo_cop"].sum()),
        "ahorro_exc1_cop": float(cols["ahorro_exc1_cop"].sum()),
        "ahorro_exc2_cop": float(cols["ahorro_exc2_cop"].sum()),
        "factura_base_cop": float(cols["factura_base_cop"].sum()),
        "factura_con_sistema_cop": float(cols["factura_con_sistema_cop"].sum()),
        "exc1_kwh": float(cols["exc1_kwh"].sum()),
        "exc2_kwh": float(cols["exc2_kwh"].sum()),
        "valor_credito_cop_kwh": valor_credito_cop_kwh(tarifa, kwp),
    }


def liquidar_sumas(
    carga_kwh: np.ndarray, importado_kwh: np.ndarray, exportado_kwh: np.ndarray, tarifa: Tarifa,
    kwp: float,
) -> dict:
    """Como liquidar(), sin la tabla mensual, desde las sumas mensuales (arrays por mes).

    Es lo que usa la optimización con las sumas que entrega balance.resumen_lote.
    """
    return _totales(_columnas(carga_kwh, importado_kwh, exportado_kwh, tarifa, kwp), tarifa, kwp)


def liquidar(balance: pd.DataFrame, tarifa: Tarifa, kwp: float) -> dict:
    """Liquida el año mes a mes. balance en kWh/h; tarifa en COP/kWh; kwp en kW pico."""
    if not isinstance(balance.index, pd.DatetimeIndex):
        raise TypeError("balance debe tener DatetimeIndex para agrupar por mes calendario")

    mes = balance.index.month.to_numpy()
    meses = np.unique(mes)

    def por_mes(serie: pd.Series) -> np.ndarray:
        return np.bincount(mes, weights=serie.to_numpy(dtype=float), minlength=13)[meses]

    carga_kwh = por_mes(balance["autoconsumo"] + balance["descarga_bat"] + balance["importado"])
    cols = _columnas(carga_kwh, por_mes(balance["importado"]), por_mes(balance["exportado"]),
                     tarifa, kwp)
    mensual = pd.DataFrame(cols, index=pd.Index(meses, name="mes"))[list(COLUMNAS_MENSUAL)]
    return {**_totales(cols, tarifa, kwp), "mensual": mensual}
