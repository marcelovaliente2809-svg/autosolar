"""Uso: python -m autosolar config/empresa.yaml [--sensibilidad] [--graficas]

Imprime la mejor combinación, la mejor sin batería y la mejor con batería, y guarda la
tabla completa en data/processed/<nombre del YAML>_optimizacion.csv.

Con --sensibilidad imprime además el tornado (sobre la mejor combinación), los escenarios
y el CAPEX de equilibrio de la batería, y los guarda en data/processed/ como
<nombre del YAML>_tornado.csv, _escenarios.csv y _breakeven_bateria.csv.

Con --graficas (que implica --sensibilidad) guarda además las 7 figuras del informe como PNG
a 300 dpi en data/processed/figuras/<nombre del YAML>_<figura>.png.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from autosolar import graficas
from autosolar.balance import simular
from autosolar.carga import perfil_carga
from autosolar.config import cargar_config
from autosolar.finanzas import flujo_caja
from autosolar.liquidacion import liquidar
from autosolar.optimizacion import optimizar
from autosolar.sensibilidad import breakeven_bateria, escenarios, tornado
from autosolar.solar import RAIZ, generacion_por_kwp


def _mostrar(titulo: str, tabla: pd.DataFrame) -> None:
    print(f"\n{titulo}")
    if tabla.empty:
        print("  (sin combinaciones)")
        return
    f = tabla.iloc[0]
    print(
        f"  FV {f.kwp:,.0f} kWp · batería {f.kwh_bat:,.0f} kWh · CAPEX {f.capex / 1e6:,.1f} M COP\n"
        f"  VPN {f.vpn / 1e6:,.1f} M COP · TIR {f.tir:.1%} · payback {f.payback:.1f} años · "
        f"LCOE {f.lcoe:,.0f} COP/kWh\n"
        f"  generación {f.gen_kwh:,.0f} kWh · autoconsumo {f.autoconsumo_pct:.1%} · "
        f"ahorro año 1 {f.ahorro_anio1 / 1e6:,.1f} M COP · ciclos/año {f.ciclos:,.0f}"
    )


def _sensibilidad(cfg, mejor: pd.Series, base: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Imprime y guarda tornado, escenarios y breakeven de batería; devuelve (tornado, escenarios)."""
    t = tornado(cfg, float(mejor["kwp"]), float(mejor["kwh_bat"]))
    e = escenarios(cfg)
    capex_eq = breakeven_bateria(cfg)
    b = pd.DataFrame(
        {
            "capex_actual_cop_kwh": [cfg.bateria.capex_cop_kwh],
            "capex_breakeven_cop_kwh": [capex_eq],
        }
    )

    print(f"\nTornado ±20 % (FV {mejor['kwp']:,.0f} kWp · batería {mejor['kwh_bat']:,.0f} kWh)")
    print(t.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
    print("\nEscenarios (re-optimizados)")
    print(e.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    print(
        f"\nBreakeven batería: {capex_eq:,.0f} COP/kWh "
        f"(YAML: {cfg.bateria.capex_cop_kwh:,.0f} COP/kWh)"
    )

    for nombre, tabla in (("tornado", t), ("escenarios", e), ("breakeven_bateria", b)):
        destino = base.with_name(f"{base.name}_{nombre}.csv")
        tabla.to_csv(destino, index=False)
        print(f"Guardado en {destino}")
    return t, e


def _graficas(cfg, tabla, t, e, nombre: str) -> None:
    """Guarda las 7 figuras del informe en data/processed/figuras/ como PNG."""
    mejor = tabla.iloc[0]
    kwp, kwh = float(mejor["kwp"]), float(mejor["kwh_bat"])
    g = generacion_por_kwp(cfg.ubicacion, cfg.sistema_fv.perdidas_sistema)
    c = perfil_carga(cfg.consumo)
    bal = simular(c, g, kwp, kwh, cfg.bateria)
    mensual = liquidar(bal, cfg.tarifa, kwp)["mensual"]

    sin_ley = cfg.model_copy(deep=True)
    sin_ley.finanzas.incentivos_ley1715 = False
    args = (kwp, kwh, float(mejor["ahorro_anio1"]), float(mejor["gen_kwh"]), float(mejor["ciclos"]))
    flujo_base = flujo_caja(*args, cfg)
    flujo_sin = flujo_caja(*args, sin_ley)

    figuras = {
        "dia_tipico": graficas.dia_tipico(cfg, bal),
        "vpn_vs_kwp": graficas.vpn_vs_kwp(cfg, tabla),
        "lcoe_vs_valores": graficas.lcoe_vs_valores(cfg, float(mejor["lcoe"])),
        "tornado": graficas.tornado(cfg, t),
        "escenarios": graficas.escenarios(cfg, e),
        "flujo_acumulado": graficas.flujo_acumulado(cfg, flujo_base, flujo_sin),
        "balance_mensual": graficas.balance_mensual(cfg, mensual),
    }
    carpeta = RAIZ / "data" / "processed" / "figuras"
    carpeta.mkdir(parents=True, exist_ok=True)
    print()
    for clave, fig in figuras.items():
        destino = carpeta / f"{nombre}_{clave}.png"
        fig.savefig(destino, dpi=graficas.DPI)
        print(f"Figura guardada en {destino}")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    con_graf = "--graficas" in args
    con_sens = "--sensibilidad" in args or con_graf  # las figuras 4 y 5 la necesitan
    posicionales = [a for a in args if not a.startswith("--")]
    if len(posicionales) != 1:
        print("Uso: python -m autosolar <config.yaml> [--sensibilidad] [--graficas]", file=sys.stderr)
        return 2

    ruta = Path(posicionales[0])
    t0 = time.perf_counter()
    cfg = cargar_config(ruta)
    tabla = optimizar(cfg)

    base = RAIZ / "data" / "processed" / ruta.stem
    destino = base.with_name(f"{ruta.stem}_optimizacion.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(destino, index=False)

    print(f"{cfg.empresa.nombre}: {len(tabla)} combinaciones evaluadas")
    _mostrar("Mejor combinación", tabla)
    _mostrar("Mejor sin batería", tabla[tabla["kwh_bat"] == 0])
    _mostrar("Mejor con batería", tabla[tabla["kwh_bat"] > 0])
    print(f"\nTabla guardada en {destino}")

    if con_sens:
        t, e = _sensibilidad(cfg, tabla.iloc[0], base)
        if con_graf:
            _graficas(cfg, tabla, t, e, ruta.stem)

    print(f"Tiempo total: {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
