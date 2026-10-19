"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BATERIAS, COLOR } from "@/lib/colores";
import { mcop, num } from "@/lib/formato";
import type { Fila } from "@/lib/tipos";
import { CajaTooltip, EJE, ETIQUETA_EJE, Leyenda, Tarjeta } from "./comun";

const clave = (kwh: number) => `b${kwh}`;

// Tamaños de batería que se grafican (además de sin batería): el más cercano de la grilla a cada uno
const OBJETIVOS_KWH = [100, 200, 500];

/** Sin batería + el tamaño de la grilla más cercano a cada objetivo, sin repetir. */
function elegirBaterias(disponibles: number[]): number[] {
  const conBat = disponibles.filter((b) => b > 0);
  const elegidas = new Set<number>();
  for (const objetivo of OBJETIVOS_KWH) {
    const libres = conBat.filter((b) => !elegidas.has(b));
    if (!libres.length) break;
    elegidas.add(libres.reduce((a, b) => (Math.abs(b - objetivo) < Math.abs(a - objetivo) ? b : a)));
  }
  return [...(disponibles.includes(0) ? [0] : []), ...[...elegidas].sort((a, b) => a - b)];
}

export default function VpnKwp({
  tabla,
  mejor,
  techoKwp,
}: {
  tabla: Fila[];
  mejor: Fila;
  techoKwp: number;
}) {
  const { filas, visibles, nGrilla } = useMemo(() => {
    const todas = [...new Set(tabla.map((f) => f.kwh_bat))].sort((a, b) => a - b);
    const visibles = elegirBaterias(todas);
    const porKwp = new Map<number, Record<string, number | null>>();
    // solo las series visibles entran a los datos: el eje Y se ajusta a ellas
    for (const f of tabla) {
      if (!visibles.includes(f.kwh_bat)) continue;
      const fila = porKwp.get(f.kwp) ?? { kwp: f.kwp };
      fila[clave(f.kwh_bat)] = f.vpn == null ? null : f.vpn / 1e6;
      porKwp.set(f.kwp, fila);
    }
    const filas = [...porKwp.values()].sort((a, b) => (a.kwp as number) - (b.kwp as number));
    return { filas, visibles, nGrilla: todas.length };
  }, [tabla]);

  // eje x hasta el tope de techo aunque la grilla termine antes (paso_kwp)
  const maxKwp = Math.max(...tabla.map((f) => f.kwp), techoKwp);
  const paso = [25, 50, 100, 200, 250].find((p) => maxKwp / p <= 8) ?? 500;
  const xMax = Math.ceil(maxKwp / paso) * paso;
  const ticks = Array.from({ length: xMax / paso + 1 }, (_, i) => i * paso);

  const conBat = visibles.filter((b) => b > 0);
  const color = (kwh: number) => (kwh === 0 ? COLOR.base : BATERIAS[conBat.indexOf(kwh)] ?? COLOR.alterno);
  const etiqueta = (kwh: number) => (kwh === 0 ? "Sin batería" : `${num(kwh)} kWh`);
  const mejorVisible = visibles.includes(mejor.kwh_bat);

  return (
    <Tarjeta
      titulo="VPN según la potencia FV"
      subtitulo="VPN [M COP] vs. potencia instalada [kWp]; una línea por tamaño de batería"
      leyenda={
        <Leyenda items={visibles.map((kwh) => ({ etiqueta: etiqueta(kwh), color: color(kwh), forma: "linea" as const }))} />
      }
      comoLeerla={[
        "Cada línea es un tamaño de batería: la oscura es sin batería y las de color son los tamaños de la grilla más cercanos a 100, 200 y 500 kWh. El punto marca la mejor combinación (mayor VPN).",
        "Las líneas verticales marcan 100 kW (por encima, Exc1 se acredita a G y no a CU − Cv) y el tope que impone el área de techo; si las líneas de color quedan bajo la oscura, la batería resta valor.",
      ]}
    >
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={filas} margin={{ top: 18, right: 16, bottom: 22, left: 8 }}>
          <CartesianGrid stroke={COLOR.grilla} vertical={false} />
          <XAxis
            dataKey="kwp"
            type="number"
            domain={[0, xMax]}
            ticks={ticks}
            {...EJE}
            tickFormatter={(v) => num(v)}
            label={{ value: "Potencia FV [kWp]", position: "insideBottom", offset: -12, ...ETIQUETA_EJE }}
          />
          <YAxis
            {...EJE}
            axisLine={false}
            width={64}
            domain={["auto", "auto"]}
            tickFormatter={(v) => num(v)}
            label={{ value: "VPN [M COP]", angle: -90, position: "insideLeft", offset: 4, ...ETIQUETA_EJE, style: { textAnchor: "middle" } }}
          />
          <ReferenceLine y={0} stroke={COLOR.eje} />
          <ReferenceLine
            x={100}
            stroke={COLOR.eje}
            strokeDasharray="4 4"
            label={{ value: "100 kW", position: "top", ...ETIQUETA_EJE }}
          />
          <ReferenceLine
            x={techoKwp}
            stroke={COLOR.eje}
            strokeDasharray="4 4"
            label={{ value: `Techo ${num(techoKwp)} kWp`, position: "insideTopRight", ...ETIQUETA_EJE }}
          />
          {visibles
            .slice()
            .reverse() // sin batería encima
            .map((kwh) => (
              <Line
                key={kwh}
                dataKey={clave(kwh)}
                stroke={color(kwh)}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: color(kwh), stroke: COLOR.panel }}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          {mejor.vpn != null && (
            <ReferenceDot
              x={mejor.kwp}
              y={mejor.vpn / 1e6}
              r={5}
              fill={mejorVisible ? color(mejor.kwh_bat) : COLOR.tinta}
              stroke={COLOR.panel}
              strokeWidth={2}
              ifOverflow="extendDomain"
            />
          )}
          <Tooltip
            cursor={{ stroke: COLOR.eje, strokeDasharray: "3 3" }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const fila = payload[0].payload as Record<string, number | null>;
              return (
                <CajaTooltip
                  titulo={`${num(label as number)} kWp · VPN [M COP]`}
                  filas={visibles
                    .filter((kwh) => fila[clave(kwh)] != null)
                    .map((kwh) => ({
                      etiqueta: etiqueta(kwh),
                      valor: num(fila[clave(kwh)]),
                      color: color(kwh),
                      forma: "linea" as const,
                      fuerte: kwh === 0,
                    }))}
                />
              );
            }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="-mt-1 px-2 pb-1 text-right text-xs text-tinta-3">
        Mejor: <span className="num">{num(mejor.kwp)} kWp + {num(mejor.kwh_bat)} kWh</span> → VPN{" "}
        <span className="num">{mcop(mejor.vpn)}</span> M COP
        {!mejorVisible && " (su batería no está entre las líneas mostradas)"} · se muestran{" "}
        <span className="num">{visibles.length}</span> de <span className="num">{nGrilla}</span> tamaños de batería
        de la grilla
      </p>
    </Tarjeta>
  );
}
