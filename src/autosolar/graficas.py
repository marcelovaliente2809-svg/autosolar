"""Módulo 8 · Gráficas para el informe.

Contrato (todas devuelven matplotlib.figure.Figure, 300 dpi, sin título interior: el título
va como pie de figura en el informe; etiquetas en español; COP en millones):
    dia_tipico(cfg, balance, dia_habil=None, dia_fin_semana=None) -> Figure
        balance: salida de balance.simular (índice horario). Carga vs. generación FV de un día
        hábil y uno de fin de semana, con autoconsumo, exportación e importación sombreados
        (y la batería si se usó). Sin días dados, toma un miércoles de julio no festivo
        (holidays.Colombia) y el domingo de julio más cercano; si los datos no tienen julio
        (pruebas cortas) cae al día hábil / fin de semana más cercano a mitad de julio.
    vpn_vs_kwp(cfg, tabla, kwh_bats=(0, 100, 200, 500)) -> Figure
        tabla: salida de optimizacion.optimizar. VPN contra kWp, una curva por kwh_bat
        presente en la tabla; líneas verticales en LIMITE_AGPE_MENOR_KWP (100 kW) y en el
        límite de techo min(kwp_max, area_techo_m2 / m2_por_kwp).
    lcoe_vs_valores(cfg, lcoe) -> Figure
        Barras horizontales [COP/kWh]: LCOE, CU, CU − Cv, G y precio_exc2.
    tornado(cfg, tabla, variacion=0.2) -> Figure
        tabla: salida de sensibilidad.tornado (ya ordenada por amplitud).
    escenarios(cfg, tabla) -> Figure
        tabla: salida de sensibilidad.escenarios. VPN por escenario.
    flujo_acumulado(cfg, flujo_base, flujo_sin_ley) -> Figure
        Flujos de finanzas.flujo_caja; marca el payback simple de cada uno.
    balance_mensual(cfg, mensual) -> Figure
        mensual: liquidar(...)["mensual"]. Dos barras apiladas por mes [MWh/mes]:
        Generación = autoconsumo + Exc1 + Exc2 y Consumo = autoconsumo + importación
        (autoconsumo = carga − importado, incluye descarga de batería; mismo color en ambas).

Supuestos de modelado:
    - Se crea Figure directamente (sin pyplot): no hay estado global ni ventanas.
    - Números con coma decimal y punto de miles (convención colombiana).
"""

from __future__ import annotations

import math

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from autosolar.balance import dias_tipicos as _dias_tipicos
from autosolar.config import LIMITE_AGPE_MENOR_KWP, Config
from autosolar.finanzas import kpis
from autosolar.liquidacion import valor_credito_cop_kwh

DPI = 300
COLORES = {
    "carga": "#222222",
    "generacion": "#D55E00",
    "autoconsumo": "#0072B2",
    "exportacion": "#009E73",
    "exc1": "#E69F00",
    "exc2": "#009E73",
    "importacion": "#999999",
    "bateria": "#CC79A7",
    "neutro": "#BBBBBB",
    "destacado": "#0072B2",
    "malo": "#D55E00",
}
CURVAS_BATERIA = ("#222222", "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
NOMBRES_TORNADO = {
    "cu": "CU (con G y Cv)",
    "capex_fv": "CAPEX FV",
    "capex_bateria": "CAPEX batería",
    "tasa_descuento": "Tasa de descuento",
    "escalamiento_tarifa": "Escalamiento de tarifa",
    "degradacion": "Degradación",
    "precio_exc2": "Precio Exc2",
}
NOMBRES_ESCENARIOS = {
    "base": "Base",
    "exc2_a_mc": "Exc2 a Mc",
    "sin_ley1715": "Sin Ley 1715",
    "jornada_2_turnos": "Jornada 2 turnos",
    "jornada_continua": "Jornada continua",
}


def _num(x: float, decimales: int = 0) -> str:
    """Formato colombiano: punto de miles, coma decimal."""
    s = f"{x:,.{decimales}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _formato(decimales: int = 0, escala: float = 1.0) -> FuncFormatter:
    return FuncFormatter(lambda x, _: _num(x / escala, decimales))


def _figura(ancho: float = 6.5, alto: float = 3.6, **kw) -> Figure:
    return Figure(figsize=(ancho, alto), dpi=DPI, layout="constrained", **kw)


def _limpiar(ax, eje_valor: str = "y") -> None:
    """Sin marco superior/derecho y rejilla tenue solo en el eje de valores."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis=eje_valor, color="#DDDDDD", linewidth=0.6)
    ax.set_axisbelow(True)


def _tramo_dia(balance: pd.DataFrame, dia: pd.Timestamp) -> pd.DataFrame:
    return balance[balance.index.normalize() == dia]


def dia_tipico(
    cfg: Config,
    balance: pd.DataFrame,
    dia_habil: str | pd.Timestamp | None = None,
    dia_fin_semana: str | pd.Timestamp | None = None,
) -> Figure:
    """Carga vs. generación [kWh/h] de un día hábil y uno de fin de semana."""
    habil, finde = _dias_tipicos(balance)
    if dia_habil is not None:
        habil = pd.Timestamp(dia_habil).normalize()
    if dia_fin_semana is not None:
        finde = pd.Timestamp(dia_fin_semana).normalize()

    fig = _figura(7.5, 3.6)
    axes = fig.subplots(1, 2, sharey=True)
    hay_bateria = bool((balance["carga_bat"] + balance["descarga_bat"]).any())

    for ax, dia, nombre in zip(axes, (habil, finde), ("Día hábil", "Fin de semana"), strict=True):
        d = _tramo_dia(balance, dia)
        h = d.index.hour
        auto = d["autoconsumo"].to_numpy()
        carga = (d["autoconsumo"] + d["descarga_bat"] + d["importado"]).to_numpy()
        bat = (d["carga_bat"] + d["descarga_bat"]).to_numpy()
        arriba_gen = auto + d["carga_bat"].to_numpy()
        arriba_carga = auto + d["descarga_bat"].to_numpy()
        kw = {"step": "mid", "linewidth": 0}

        ax.fill_between(h, 0, auto, color=COLORES["autoconsumo"], alpha=0.35, **kw,
                        label="Autoconsumo")
        if hay_bateria:
            ax.fill_between(h, auto, auto + bat, color=COLORES["bateria"], alpha=0.35, **kw,
                            label="Batería (carga/descarga)")
        ax.fill_between(h, arriba_gen, d["generacion"].to_numpy(), color=COLORES["exportacion"],
                        alpha=0.35, **kw, label="Exportación")
        ax.fill_between(h, arriba_carga, carga, color=COLORES["importacion"], alpha=0.45, **kw,
                        label="Importación")
        ax.plot(h, carga, drawstyle="steps-mid", color=COLORES["carga"], linewidth=1.6,
                label="Carga")
        ax.plot(h, d["generacion"].to_numpy(), drawstyle="steps-mid",
                color=COLORES["generacion"], linewidth=1.6, label="Generación FV")

        ax.set_xlabel(f"Hora del día · {nombre} ({dia:%d-%m})")
        ax.set_xlim(0, 23)
        ax.set_xticks(range(0, 24, 3))
        ax.yaxis.set_major_formatter(_formato(0))
        _limpiar(ax)
    axes[0].set_ylabel("Potencia media horaria (kWh/h)")
    handles, etiquetas = axes[0].get_legend_handles_labels()
    fig.legend(handles, etiquetas, loc="outside lower center", ncol=len(handles), frameon=False)
    return fig


def vpn_vs_kwp(cfg: Config, tabla: pd.DataFrame, kwh_bats=(0, 100, 200, 500)) -> Figure:
    """VPN [millones COP] contra kWp, una curva por capacidad de batería."""
    fig = _figura(6.5, 3.8)
    ax = fig.subplots()
    for color, kwh in zip(CURVAS_BATERIA, kwh_bats, strict=False):
        sub = tabla[tabla["kwh_bat"] == kwh].sort_values("kwp")
        if sub.empty:
            continue
        etiqueta = "Sin batería" if kwh == 0 else f"{_num(kwh)} kWh"
        ax.plot(sub["kwp"], sub["vpn"], color=color, linewidth=1.8, marker="o", markersize=3,
                label=etiqueta)

    techo = min(cfg.sistema_fv.kwp_max, cfg.ubicacion.area_techo_m2 / cfg.sistema_fv.m2_por_kwp)
    # El umbral va arriba y el techo abajo: a la derecha las curvas ocupan la parte alta
    for x, texto, y, va, dy in (
        (LIMITE_AGPE_MENOR_KWP, f"Umbral AGPE {_num(LIMITE_AGPE_MENOR_KWP)} kW", 1.0, "top", -4),
        (techo, f"Límite de techo {_num(techo)} kWp", 0.0, "bottom", 4),
    ):
        ax.axvline(x, color="#555555", linestyle="--", linewidth=1.0)
        ax.annotate(texto, (x, y), xycoords=("data", "axes fraction"), xytext=(-3, dy),
                    textcoords="offset points", rotation=90, ha="right", va=va, fontsize=8,
                    color="#333333")

    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.set_xlabel("Potencia FV instalada (kWp)")
    ax.set_ylabel("VPN (millones de COP)")
    ax.xaxis.set_major_formatter(_formato(0))
    ax.yaxis.set_major_formatter(_formato(0, 1e6))
    ax.legend(title="Batería", frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    _limpiar(ax)
    return fig


def lcoe_vs_valores(cfg: Config, lcoe: float) -> Figure:
    """LCOE frente a los valores que remunera la factura [COP/kWh]."""
    t = cfg.tarifa
    filas = [
        ("LCOE del sistema", lcoe, COLORES["destacado"]),
        ("CU (autoconsumo)", t.cu_cop_kwh, COLORES["neutro"]),
        (
            "CU − Cv (Exc1, ≤ 100 kW)",
            valor_credito_cop_kwh(t, LIMITE_AGPE_MENOR_KWP),
            COLORES["neutro"],
        ),
        ("G (Exc1, > 100 kW)", t.g_cop_kwh, COLORES["neutro"]),
        ("Precio Exc2", t.precio_exc2_cop_kwh, COLORES["neutro"]),
    ]
    fig = _figura(6.5, 3.0)
    ax = fig.subplots()
    y = list(range(len(filas)))
    ax.barh(y, [f[1] for f in filas], color=[f[2] for f in filas], height=0.6)
    for yi, (_, v, _) in zip(y, filas, strict=True):
        ax.annotate(_num(v), (v, yi), xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=8)
    ax.set_yticks(y, [f[0] for f in filas])
    ax.invert_yaxis()
    ax.set_xlabel("COP/kWh")
    ax.xaxis.set_major_formatter(_formato(0))
    ax.set_xlim(0, max(f[1] for f in filas) * 1.12)
    _limpiar(ax, "x")
    return fig


def tornado(cfg: Config, tabla: pd.DataFrame, variacion: float = 0.2) -> Figure:
    """Diagrama de tornado: VPN [millones COP] con cada variable en −/+ variacion."""
    n = len(tabla)
    fig = _figura(6.5, 1.5 + 0.45 * n)
    ax = fig.subplots()
    base = float(tabla["vpn_base"].iloc[0]) if n else 0.0
    y = list(range(n))
    pct = f"{variacion:.0%}".replace("%", " %")
    ax.barh(y, tabla["vpn_bajo"] - base, left=base, height=0.6, color=COLORES["destacado"],
            label=f"Variable −{pct}")
    ax.barh(y, tabla["vpn_alto"] - base, left=base, height=0.6, color=COLORES["generacion"],
            label=f"Variable +{pct}")
    ax.axvline(base, color="#333333", linewidth=1.0)
    ax.set_yticks(y, [NOMBRES_TORNADO.get(v, v) for v in tabla["variable"]])
    ax.invert_yaxis()
    ax.set_xlabel(f"VPN (millones de COP) · base {_num(base / 1e6, 0)}")
    ax.xaxis.set_major_formatter(_formato(0, 1e6))
    ax.legend(frameon=False, loc="lower right")
    _limpiar(ax, "x")
    return fig


def escenarios(cfg: Config, tabla: pd.DataFrame) -> Figure:
    """VPN [millones COP] de la mejor solución de cada escenario."""
    n = len(tabla)
    fig = _figura(6.5, 1.4 + 0.5 * n)
    ax = fig.subplots()
    y = list(range(n))
    colores = [COLORES["destacado"] if e == "base" else COLORES["neutro"] for e in tabla["escenario"]]
    ax.barh(y, tabla["vpn"], color=colores, height=0.6)
    for yi, f in zip(y, tabla.itertuples(), strict=True):
        texto = f"{_num(f.vpn / 1e6)} · {_num(f.kwp)} kWp / {_num(f.kwh_bat)} kWh"
        ax.annotate(texto, (f.vpn, yi), xytext=(4 if f.vpn >= 0 else -4, 0),
                    textcoords="offset points", ha="left" if f.vpn >= 0 else "right",
                    va="center", fontsize=8)
    ax.set_yticks(y, [NOMBRES_ESCENARIOS.get(e, e) for e in tabla["escenario"]])
    ax.invert_yaxis()
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("VPN (millones de COP)")
    ax.xaxis.set_major_formatter(_formato(0, 1e6))
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo, hi + 0.25 * (hi - lo))  # espacio para las etiquetas
    _limpiar(ax, "x")
    return fig


def flujo_acumulado(cfg: Config, flujo_base: pd.DataFrame, flujo_sin_ley: pd.DataFrame) -> Figure:
    """Flujo de caja acumulado [millones COP] con y sin Ley 1715, marcando el payback."""
    fig = _figura(6.5, 3.6)
    ax = fig.subplots()
    casos = (
        ("Base (con Ley 1715)", flujo_base, COLORES["destacado"], (-8, 14), "right"),
        ("Sin Ley 1715", flujo_sin_ley, COLORES["generacion"], (8, -16), "left"),
    )
    for nombre, flujo, color, desplazamiento, ha in casos:
        ax.plot(flujo.index, flujo["flujo_acumulado"], color=color, linewidth=1.8, label=nombre)
        pb = kpis(flujo, cfg)["payback_simple"]
        if not math.isnan(pb):
            ax.plot([pb], [0], marker="o", markersize=7, color=color, markeredgecolor="white",
                    markeredgewidth=1.5, linestyle="none", zorder=5)
            ax.annotate(f"Payback {_num(pb, 1)} años", (pb, 0), xytext=desplazamiento,
                        textcoords="offset points", fontsize=8, color="#333333", ha=ha)
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.set_xlabel("Año")
    ax.set_ylabel("Flujo de caja acumulado (millones de COP)")
    ax.yaxis.set_major_formatter(_formato(0, 1e6))
    ax.legend(frameon=False, loc="upper left")
    _limpiar(ax)
    return fig


def balance_mensual(cfg: Config, mensual: pd.DataFrame) -> Figure:
    """Por mes [MWh]: barra Generación (autoconsumo + Exc1 + Exc2) y barra Consumo."""
    fig = _figura(7.5, 3.8)
    ax = fig.subplots()
    auto = mensual["carga_kwh"] - mensual["importado_kwh"]
    ancho = 0.38
    x = list(range(len(mensual)))
    x_gen = [i - ancho / 2 for i in x]
    x_con = [i + ancho / 2 for i in x]
    # (posiciones, nombre en la leyenda, serie, color); autoconsumo solo se rotula una vez
    apilados = (
        (x_gen, [("Autoconsumo", auto, COLORES["autoconsumo"]),
                 ("Exc1", mensual["exc1_kwh"], COLORES["exc1"]),
                 ("Exc2", mensual["exc2_kwh"], COLORES["exc2"])]),
        (x_con, [("_autoconsumo", auto, COLORES["autoconsumo"]),
                 ("Importación", mensual["importado_kwh"], COLORES["importacion"])]),
    )
    for posiciones, capas in apilados:
        fondo = pd.Series(0.0, index=mensual.index)
        for nombre, valores, color in capas:
            ax.bar(posiciones, valores / 1e3, bottom=fondo / 1e3, color=color, label=nombre,
                   width=ancho, edgecolor="white", linewidth=0.8)
            fondo = fondo + valores

    # Cada barra se rotula (G/C) y el mes va debajo, centrado en el par
    ax.set_xticks(x_gen + x_con, ["Gen."] * len(x) + ["Cons."] * len(x), fontsize=6, rotation=90)
    ax.set_xticks(x, [MESES[(int(m) - 1) % 12] for m in mensual.index], minor=True)
    ax.tick_params(axis="x", which="minor", length=0, pad=34)
    ax.set_xlabel("Mes", labelpad=4)
    ax.set_ylabel("Energía (MWh/mes)")
    ax.yaxis.set_major_formatter(_formato(0))
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    _limpiar(ax)
    return fig
