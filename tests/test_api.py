"""Pruebas de la API (api/index.py) con TestClient, sin red, y de los atajos del motor que
usa (simulación en lote, VPN rápido, casos reutilizables). PVGIS se mockea con un año sintético."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.index import app, limpiar
from autosolar import balance, liquidacion, optimizacion, sensibilidad, solar
from autosolar.config import Config, cargar_config
from autosolar.finanzas import flujo_caja, kpis, vpn_flujo

EJEMPLO = Path(__file__).parents[1] / "config" / "empresa_ejemplo.yaml"


def _pvgis_sintetico() -> pd.DataFrame:
    """Campana diurna (UTC 11–23 h ≈ 6–18 h locales) en tres años; 2020 es bisiesto."""
    indice = pd.date_range("2019-01-01", "2021-12-31 23:00", freq="h", tz="UTC")
    forma = np.sin(np.pi * np.clip(indice.hour - 11, 0, 12) / 12)
    return pd.DataFrame({"P": 800.0 * forma}, index=indice)


@pytest.fixture
def descargas(monkeypatch, tmp_path):
    """Caché en tmp_path vía AUTOSOLAR_CACHE_DIR y descarga de PVGIS falsa (cuenta llamadas)."""
    monkeypatch.setenv(solar.VAR_CACHE, str(tmp_path))
    llamadas = []

    def falso(*args):
        llamadas.append(args)
        return _pvgis_sintetico()

    monkeypatch.setattr(solar, "_descargar", falso)
    return llamadas


@pytest.fixture
def cliente(descargas):
    return TestClient(app)


def _cfg_dict(**cambios) -> dict:
    """Config de ejemplo con una grilla corta (kWp 0–150, kWh 0–200) para que corra rápido."""
    cfg = cargar_config(EJEMPLO)
    cfg.sistema_fv.kwp_max, cfg.sistema_fv.paso_kwp = 150, 50
    cfg.bateria.kwh_max, cfg.bateria.paso_kwh = 200, 100
    cfg.finanzas.horizonte_anios = 12
    datos = cfg.model_dump(mode="json")
    for ruta, valor in cambios.items():
        *padres, hoja = ruta.split(".")
        destino = datos
        for p in padres:
            destino = destino[p]
        destino[hoja] = valor
    return datos


def _cfg() -> Config:
    return Config.model_validate(_cfg_dict())


# ───────────────────────── endpoints ─────────────────────────


def test_config_ejemplo_es_un_config_valido(cliente):
    r = cliente.get("/api/config-ejemplo")
    assert r.status_code == 200
    assert Config.model_validate(r.json()) == cargar_config(EJEMPLO)


def test_optimizar_estructura_y_series(cliente):
    r = cliente.post("/api/optimizar", json=_cfg_dict())
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"mejor", "mejor_sin_bateria", "mejor_con_bateria", "tabla", "series"}
    assert d["mejor"]["vpn"] == max(f["vpn"] for f in d["tabla"])
    assert d["mejor_sin_bateria"]["kwh_bat"] == 0
    assert d["mejor_con_bateria"]["kwh_bat"] > 0
    assert set(d["tabla"][0]) == set(optimizacion.COLUMNAS)

    s = d["series"]
    assert set(s) == {
        "dia_habil", "dia_domingo", "balance_mensual", "flujo_acumulado", "lcoe_vs_valores"
    }
    for dia in ("dia_habil", "dia_domingo"):
        assert s[dia]["hora"] == list(range(24))
        assert len(s[dia]["carga"]) == len(s[dia]["generacion"]) == 24
    assert s["dia_habil"]["fecha"] == "2023-07-12"  # miércoles de julio
    assert pd.Timestamp(s["dia_domingo"]["fecha"]).weekday() == 6
    assert s["balance_mensual"]["mes"] == list(range(1, 13))
    assert len(s["balance_mensual"]["generacion_kwh"]) == 12
    assert len(s["flujo_acumulado"]["base"]) == len(s["flujo_acumulado"]["anio"]) == 13
    assert set(s["lcoe_vs_valores"]) == {"lcoe", "cu", "cu_menos_cv", "g", "precio_exc2"}


def test_optimizar_series_son_las_de_la_mejor(cliente):
    d = cliente.post("/api/optimizar", json=_cfg_dict()).json()
    s, mejor = d["series"], d["mejor"]
    m = s["balance_mensual"]
    # generación = autoconsumo + Exc1 + Exc2, igual que el mejor caso de la tabla
    assert sum(m["generacion_kwh"]) == pytest.approx(
        sum(m["autoconsumo_kwh"]) + sum(m["exc1_kwh"]) + sum(m["exc2_kwh"])
    )
    assert sum(m["exc1_kwh"]) == pytest.approx(mejor["exc1_kwh"])
    assert s["lcoe_vs_valores"]["lcoe"] == pytest.approx(mejor["lcoe"])
    assert s["flujo_acumulado"]["payback_base"] == pytest.approx(mejor["payback"])


def test_nan_e_infinitos_salen_como_null(cliente):
    # CAPEX absurdo: nunca se recupera → payback = NaN y TIR indefinida
    r = cliente.post("/api/optimizar", json=_cfg_dict(**{"sistema_fv.capex_cop_wp": 1e9}))
    assert r.status_code == 200
    assert "NaN" not in r.text and "Infinity" not in r.text
    json.loads(r.text, parse_constant=lambda c: pytest.fail(f"constante no JSON: {c}"))
    assert any(f["payback"] is None for f in r.json()["tabla"])


def test_config_invalido_responde_422_con_mensaje_de_pydantic(cliente):
    r = cliente.post("/api/optimizar", json=_cfg_dict(**{"finanzas.tasa_descuento": -1}))
    assert r.status_code == 422
    detalle = r.json()["detail"][0]
    assert detalle["loc"][-1] == "tasa_descuento"
    assert "greater than 0" in detalle["msg"]

    r = cliente.post("/api/sensibilidad", json={})
    assert r.status_code == 422


def test_modo_archivo_no_esta_disponible(cliente):
    cfg = _cfg_dict(**{"consumo.modo": "archivo", "consumo.archivo": "c:/secreto.csv"})
    r = cliente.post("/api/optimizar", json=cfg)
    assert r.status_code == 422
    assert "archivo" in r.json()["detail"]


def test_evaluar_una_combinacion(cliente):
    cuerpo = {"config": _cfg_dict(), "kwp": 100, "kwh_bat": 100}
    r = cliente.post("/api/evaluar", json=cuerpo)
    assert r.status_code == 200
    d = r.json()
    assert (d["resultado"]["kwp"], d["resultado"]["kwh_bat"]) == (100, 100)
    # coincide con la fila equivalente de /api/optimizar
    fila = next(
        f
        for f in cliente.post("/api/optimizar", json=_cfg_dict()).json()["tabla"]
        if (f["kwp"], f["kwh_bat"]) == (100, 100)
    )
    assert d["resultado"]["vpn"] == pytest.approx(fila["vpn"])
    assert len(d["series"]["dia_habil"]["hora"]) == 24


def test_evaluar_valida_limites(cliente):
    for malo in ({"kwp": -1, "kwh_bat": 0}, {"kwp": 5000, "kwh_bat": 0}, {"kwp": 1, "kwh_bat": -5}):
        assert cliente.post("/api/evaluar", json={"config": _cfg_dict(), **malo}).status_code == 422
    assert cliente.post("/api/evaluar", json={"kwp": 1, "kwh_bat": 0}).status_code == 422


def test_sensibilidad_tornado_escenarios_y_breakeven(cliente):
    r = cliente.post("/api/sensibilidad", json=_cfg_dict())
    assert r.status_code == 200
    d = r.json()
    assert [f["variable"] for f in d["tornado"]].count("cu") == 1
    assert len(d["tornado"]) == 7
    assert [e["escenario"] for e in d["escenarios"]] == [
        "base", "exc2_a_mc", "sin_ley1715", "jornada_2_turnos", "jornada_continua"
    ]
    be = d["breakeven"]
    assert be["estado"] in {"umbral", "siempre", "nunca"}
    assert be["capex_actual_cop_kwh"] == 1_800_000
    if be["estado"] == "siempre":
        assert be["capex_breakeven_cop_kwh"] is None  # inf → null


def test_sensibilidad_pide_mc_para_el_escenario(cliente):
    r = cliente.post("/api/sensibilidad", json=_cfg_dict(**{"tarifa.precio_mc_cop_kwh": None}))
    assert r.status_code == 422
    assert "precio_mc_cop_kwh" in r.json()["detail"]


def test_pvgis_se_descarga_una_vez_y_va_a_la_cache_del_entorno(cliente, descargas, tmp_path):
    cliente.post("/api/optimizar", json=_cfg_dict())
    cliente.post("/api/optimizar", json=_cfg_dict())
    assert len(descargas) == 1
    assert len(list(tmp_path.glob("pvgis_*.csv"))) == 1


def test_sin_variable_la_cache_es_data_raw(monkeypatch):
    monkeypatch.delenv(solar.VAR_CACHE, raising=False)
    assert solar._dir_cache() == solar.DIR_RAW


# ───────────────────────── limpiar (JSON) ─────────────────────────


def test_limpiar_convierte_tipos_y_no_finitos():
    df = pd.DataFrame({"a": [1.0, np.nan], "b": [np.inf, -np.inf]})
    salida = limpiar(
        {
            "df": df,
            "n": np.float64("nan"),
            "i": np.int64(3),
            "fecha": pd.Timestamp("2023-07-12"),
            "arr": np.array([1.0, np.nan]),
            "t": (math.inf, 1),
        }
    )
    assert salida["df"] == [{"a": 1.0, "b": None}, {"a": None, "b": None}]
    assert salida["n"] is None and salida["i"] == 3 and type(salida["i"]) is int
    assert salida["fecha"] == "2023-07-12"
    assert salida["arr"] == [1.0, None]
    assert salida["t"] == [None, 1]
    json.dumps(salida, allow_nan=False)


# ───────────────── atajos del motor (mismos resultados, más rápido) ─────────────────


def _g_c(cfg):
    return (
        solar.generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema),
        optimizacion.perfil_carga(cfg.consumo),
    )


def test_resumen_lote_igual_a_simular_mas_liquidar(descargas):
    cfg = _cfg()
    g, c = _g_c(cfg)
    combos = [(50.0, 100.0), (150.0, 200.0), (100.0, 30.0)]
    resumenes = list(
        balance.resumen_lote(c, g, [k for k, _ in combos], [h for _, h in combos], cfg.bateria)
    )
    for (kwp, kwh), r in zip(combos, resumenes, strict=True):
        bal = balance.simular(c, g, kwp, kwh, cfg.bateria)
        liq = liquidacion.liquidar(bal, cfg.tarifa, kwp)
        assert r["generacion"] == pytest.approx(bal["generacion"].sum())
        assert r["descarga_bat"] == pytest.approx(bal["descarga_bat"].sum())
        assert r["autoconsumo"] == pytest.approx(bal["autoconsumo"].sum())
        sumas = liquidacion.liquidar_sumas(
            r["carga_kwh"], r["importado_kwh"], r["exportado_kwh"], cfg.tarifa, kwp
        )
        for k, v in sumas.items():
            assert v == pytest.approx(liq[k], rel=1e-9), k


def test_resumen_lote_rechaza_sin_bateria(descargas):
    cfg = _cfg()
    g, c = _g_c(cfg)
    with pytest.raises(ValueError):
        list(balance.resumen_lote(c, g, [10.0], [0.0], cfg.bateria))


def test_vpn_flujo_igual_a_kpis(descargas):
    cfg = _cfg()
    args = (80.0, 100.0, 5e7, 120_000.0, 150.0)
    assert vpn_flujo(*args, cfg) == pytest.approx(kpis(flujo_caja(*args, cfg), cfg)["vpn"])


def test_optimizar_igual_con_g_y_c_dados_y_mejor_caso_es_la_primera_fila(descargas):
    cfg = _cfg()
    g, c = _g_c(cfg)
    tabla = optimizacion.optimizar(cfg)
    pd.testing.assert_frame_equal(tabla, optimizacion.optimizar(cfg, g, c))

    # el camino en lote da lo mismo que evaluar() combinación por combinación
    for _, fila in tabla.iterrows():
        e = optimizacion.evaluar(cfg, fila["kwp"], fila["kwh_bat"], g, c)
        assert e["vpn"] == pytest.approx(fila["vpn"], rel=1e-9)

    casos = optimizacion.simular_casos(cfg, g, c)
    mejor = optimizacion.mejor_caso(cfg, casos)
    assert mejor["vpn"] == tabla.iloc[0]["vpn"]
    assert (mejor["kwp"], mejor["kwh_bat"]) == (tabla.iloc[0]["kwp"], tabla.iloc[0]["kwh_bat"])


def test_breakeven_y_escenarios_con_casos_reutilizados(descargas):
    cfg = _cfg()
    casos = sensibilidad.simular_casos_base(cfg)
    assert sensibilidad.breakeven_bateria(cfg, casos) == pytest.approx(
        sensibilidad.breakeven_bateria(cfg)
    )
    pd.testing.assert_frame_equal(
        sensibilidad.escenarios(cfg, casos), sensibilidad.escenarios(cfg)
    )


def test_breakeven_exacto_frente_a_reoptimizar(descargas):
    """Con el umbral devuelto, optimizar() incluye batería justo por debajo y no por encima."""
    cfg = _cfg()
    capex = sensibilidad.breakeven_bateria(cfg)
    assert 0 < capex < math.inf

    def kwh_mejor(factor):
        c = cfg.model_copy(deep=True)
        c.bateria.capex_cop_kwh = capex * factor
        return optimizacion.optimizar(c).iloc[0]["kwh_bat"]

    assert kwh_mejor(0.98) > 0
    assert kwh_mejor(1.03) == 0


def test_series_solucion_dias_y_flujos(descargas):
    cfg = _cfg()
    s = optimizacion.series_solucion(cfg, 100.0, 100.0)
    for clave in ("dia_habil", "dia_domingo"):
        fecha, tramo = s[clave]
        assert len(tramo) == 24 and (tramo.index.normalize() == fecha).all()
        assert np.allclose(
            tramo["carga"], tramo["autoconsumo"] + tramo["descarga_bat"] + tramo["importado"]
        )
    assert s["flujo_base"].index[-1] == cfg.finanzas.horizonte_anios
    # sin incentivos de la Ley 1715 el flujo final es menor
    assert s["flujo_sin_ley1715"]["flujo_acumulado"].iloc[-1] < (
        s["flujo_base"]["flujo_acumulado"].iloc[-1]
    )
