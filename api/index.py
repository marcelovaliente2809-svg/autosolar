"""API FastAPI de autosolar (Vercel: Next.js en la raíz, Python en api/).

Sólo adapta HTTP ↔ motor: la lógica vive en src/autosolar. Rutas:
    GET  /api/config-ejemplo   config/empresa_ejemplo.yaml como JSON
    POST /api/optimizar        body: Config → mejores soluciones, tabla y series de la mejor
    POST /api/evaluar          body: {config, kwp, kwh_bat} → una combinación y sus series
    POST /api/sensibilidad     body: Config → tornado, escenarios y breakeven de la batería

Un Config inválido responde 422 con el detalle de pydantic. NaN e infinitos salen como null.
Local: uvicorn api.index:app --reload --port 8000
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # sin `pip install -e .` (Vercel sólo instala requirements)

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from autosolar import optimizacion, sensibilidad
from autosolar.carga import perfil_carga
from autosolar.config import LIMITE_AGPE_KWP, Config, cargar_config
from autosolar.finanzas import kpis
from autosolar.solar import generacion_por_kwp

CONFIG_EJEMPLO = RAIZ / "config" / "empresa_ejemplo.yaml"

app = FastAPI(title="autosolar", docs_url="/api/docs", openapi_url="/api/openapi.json")


class EvaluarIn(BaseModel):
    config: Config
    kwp: float = Field(ge=0, le=LIMITE_AGPE_KWP)
    kwh_bat: float = Field(ge=0)


def limpiar(obj):
    """Deja `obj` listo para JSON: DataFrames → registros, numpy → nativos, NaN/inf → None."""
    if isinstance(obj, pd.DataFrame):
        return limpiar(obj.to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return limpiar(obj.to_list())
    if isinstance(obj, dict):
        return {str(k): limpiar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [limpiar(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return limpiar(obj.tolist())
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(obj).date().isoformat()
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _json(contenido) -> JSONResponse:
    return JSONResponse(limpiar(contenido))


def _entradas(cfg: Config) -> tuple[pd.Series, pd.Series]:
    """g y c de la config (una vez por petición). El modo 'archivo' lee disco del servidor."""
    if cfg.consumo.modo == "archivo":
        raise HTTPException(422, "consumo.modo = 'archivo' no está disponible en la API")
    return generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema), perfil_carga(
        cfg.consumo
    )


def _dia(fecha_y_tramo: tuple[pd.Timestamp, pd.DataFrame]) -> dict:
    fecha, tramo = fecha_y_tramo
    cols = ("carga", "generacion", "autoconsumo", "carga_bat", "descarga_bat", "exportado")
    return {
        "fecha": fecha,
        "hora": tramo.index.hour.to_list(),
        **{c: tramo[c] for c in (*cols, "importado", "soc")},
    }


def _series(cfg: Config, kwp: float, kwh_bat: float, g: pd.Series, c: pd.Series) -> dict:
    s = optimizacion.series_solucion(cfg, kwp, kwh_bat, g, c)
    m = s["mensual"]
    base, sin = s["flujo_base"], s["flujo_sin_ley1715"]
    return {
        "dia_habil": _dia(s["dia_habil"]),
        "dia_domingo": _dia(s["dia_domingo"]),
        "balance_mensual": {
            "mes": m.index.to_list(),
            "generacion_kwh": m["generacion_kwh"],
            "consumo_kwh": m["carga_kwh"],
            "autoconsumo_kwh": m["autoconsumo_kwh"],
            "exc1_kwh": m["exc1_kwh"],
            "exc2_kwh": m["exc2_kwh"],
            "importado_kwh": m["importado_kwh"],
        },
        "flujo_acumulado": {
            "anio": base.index.to_list(),
            "base": base["flujo_acumulado"],
            "sin_ley1715": sin["flujo_acumulado"],
            "payback_base": kpis(base, cfg)["payback_simple"],
            "payback_sin_ley1715": kpis(sin, cfg)["payback_simple"],
        },
        "lcoe_vs_valores": s["valores"],
    }


@app.get("/api/config-ejemplo")
def config_ejemplo():
    return _json(cargar_config(CONFIG_EJEMPLO).model_dump(mode="json"))


@app.post("/api/optimizar")
def optimizar(cfg: Config):
    g, c = _entradas(cfg)
    tabla = optimizacion.optimizar(cfg, g, c)
    if tabla.empty:
        raise HTTPException(422, "La grilla (kwp_min, techo, kwp_max) no deja ninguna combinación")

    def primera(filtro: pd.Series):
        sub = tabla[filtro]
        return None if sub.empty else sub.iloc[0].to_dict()

    mejor = tabla.iloc[0]
    return _json(
        {
            "mejor": mejor.to_dict(),
            "mejor_sin_bateria": primera(tabla["kwh_bat"] == 0),
            "mejor_con_bateria": primera(tabla["kwh_bat"] > 0),
            "tabla": tabla,
            "series": _series(cfg, float(mejor["kwp"]), float(mejor["kwh_bat"]), g, c),
        }
    )


@app.post("/api/evaluar")
def evaluar(entrada: EvaluarIn):
    cfg = entrada.config
    g, c = _entradas(cfg)
    return _json(
        {
            "resultado": optimizacion.evaluar(cfg, entrada.kwp, entrada.kwh_bat, g, c),
            "series": _series(cfg, entrada.kwp, entrada.kwh_bat, g, c),
        }
    )


@app.post("/api/sensibilidad")
def sensibilidad_(cfg: Config):
    g, c = _entradas(cfg)
    try:
        # Una sola simulación de la grilla base sirve a la mejor solución, al breakeven y a los
        # escenarios base / Exc2 a Mc / sin Ley 1715; sólo las jornadas vuelven a simular.
        casos = sensibilidad.simular_casos_base(cfg, g, c)
        if not casos:
            raise ValueError("La grilla (kwp_min, techo, kwp_max) no deja ninguna combinación")
        mejor = optimizacion.mejor_caso(cfg, casos)
        kwp, kwh_bat = float(mejor["kwp"]), float(mejor["kwh_bat"])

        capex_eq = sensibilidad.breakeven_bateria(cfg, casos)
        return _json(
            {
                "sistema": {"kwp": kwp, "kwh_bat": kwh_bat},
                "tornado": sensibilidad.tornado(cfg, kwp, kwh_bat, g=g, c=c),
                "escenarios": sensibilidad.escenarios(cfg, casos, g),
                "breakeven": {
                    "capex_actual_cop_kwh": cfg.bateria.capex_cop_kwh,
                    "capex_breakeven_cop_kwh": capex_eq,
                    # null no distingue "nunca" de "siempre": el estado lo aclara
                    "estado": (
                        "siempre" if math.isinf(capex_eq) else "nunca" if capex_eq == 0 else "umbral"
                    ),
                },
            }
        )
    except ValueError as e:  # p. ej. falta tarifa.precio_mc_cop_kwh para el escenario Mc
        raise HTTPException(422, str(e)) from e
