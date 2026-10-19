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
"""

from __future__ import annotations

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


def liquidar(balance: pd.DataFrame, tarifa: Tarifa, kwp: float) -> dict:
    """Liquida el año mes a mes. balance en kWh/h; tarifa en COP/kWh; kwp en kW pico."""
    if not isinstance(balance.index, pd.DatetimeIndex):
        raise TypeError("balance debe tener DatetimeIndex para agrupar por mes calendario")

    cu = tarifa.cu_cop_kwh
    precio_exc2 = tarifa.precio_exc2_cop_kwh
    credito = valor_credito_cop_kwh(tarifa, kwp)

    carga = balance["autoconsumo"] + balance["descarga_bat"] + balance["importado"]
    mes = balance.index.month
    imp = balance["importado"].groupby(mes).sum()
    exp = balance["exportado"].groupby(mes).sum()
    exc1 = pd.concat([exp, imp], axis=1).min(axis=1)
    exc2 = (exp - imp).clip(lower=0.0)

    mensual = pd.DataFrame(index=imp.index)
    mensual.index.name = "mes"
    mensual["carga_kwh"] = carga.groupby(mes).sum()
    mensual["importado_kwh"] = imp
    mensual["exportado_kwh"] = exp
    mensual["exc1_kwh"] = exc1
    mensual["exc2_kwh"] = exc2
    mensual["factura_base_cop"] = mensual["carga_kwh"] * cu
    mensual["factura_con_sistema_cop"] = imp * cu - exc1 * credito - exc2 * precio_exc2
    mensual["ahorro_autoconsumo_cop"] = (mensual["carga_kwh"] - imp) * cu
    mensual["ahorro_exc1_cop"] = exc1 * credito
    mensual["ahorro_exc2_cop"] = exc2 * precio_exc2
    mensual["ahorro_cop"] = mensual["factura_base_cop"] - mensual["factura_con_sistema_cop"]
    mensual = mensual[list(COLUMNAS_MENSUAL)]

    return {
        "ahorro_cop": float(mensual["ahorro_cop"].sum()),
        "ahorro_autoconsumo_cop": float(mensual["ahorro_autoconsumo_cop"].sum()),
        "ahorro_exc1_cop": float(mensual["ahorro_exc1_cop"].sum()),
        "ahorro_exc2_cop": float(mensual["ahorro_exc2_cop"].sum()),
        "factura_base_cop": float(mensual["factura_base_cop"].sum()),
        "factura_con_sistema_cop": float(mensual["factura_con_sistema_cop"].sum()),
        "exc1_kwh": float(exc1.sum()),
        "exc2_kwh": float(exc2.sum()),
        "valor_credito_cop_kwh": credito,
        "mensual": mensual,
    }
