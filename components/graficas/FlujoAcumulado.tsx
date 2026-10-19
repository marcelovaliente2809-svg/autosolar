"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { COLOR } from "@/lib/colores";
import { num } from "@/lib/formato";
import type { Series } from "@/lib/tipos";
import { CajaTooltip, EJE, ETIQUETA_EJE, Leyenda, Tarjeta } from "./comun";

export default function FlujoAcumulado({ datos }: { datos: Series["flujo_acumulado"] }) {
  const filas = datos.anio.map((a, i) => ({
    anio: a,
    base: datos.base[i] / 1e6,
    sin: datos.sin_ley1715[i] / 1e6,
  }));
  const pb = datos.payback_base;
  const ps = datos.payback_sin_ley1715;
  const txtPb = (v: number | null) => (v == null ? "no se recupera" : `${num(v, 1)} años`);

  return (
    <Tarjeta
      titulo="Flujo de caja acumulado"
      subtitulo="Flujo acumulado [M COP] por año del proyecto · con y sin incentivos de la Ley 1715"
      leyenda={
        <Leyenda
          items={[
            { etiqueta: `Con Ley 1715 · payback ${txtPb(pb)}`, color: COLOR.base, forma: "linea" },
            { etiqueta: `Sin Ley 1715 · payback ${txtPb(ps)}`, color: COLOR.alterno, forma: "guion" },
          ]}
        />
      }
      comoLeerla={[
        "Cada curva arranca en −CAPEX (año 0) y sube con los ahorros netos de cada año; el punto donde cruza el cero es el payback, marcado con una línea vertical.",
        "La distancia entre las dos curvas es el valor de la deducción de renta y la depreciación acelerada de la Ley 1715: se concentra en los primeros años y adelanta el payback.",
      ]}
    >
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={filas} margin={{ top: 18, right: 16, bottom: 22, left: 8 }}>
          <CartesianGrid stroke={COLOR.grilla} vertical={false} />
          <XAxis
            dataKey="anio"
            type="number"
            domain={[0, "dataMax"]}
            allowDecimals={false}
            {...EJE}
            label={{ value: "Año", position: "insideBottom", offset: -12, ...ETIQUETA_EJE }}
          />
          <YAxis
            {...EJE}
            axisLine={false}
            width={64}
            tickFormatter={(v) => num(v)}
            label={{ value: "Flujo acumulado [M COP]", angle: -90, position: "insideLeft", offset: 4, ...ETIQUETA_EJE, style: { textAnchor: "middle" } }}
          />
          <ReferenceLine y={0} stroke={COLOR.eje} />
          {pb != null && (
            <ReferenceLine
              x={pb}
              stroke={COLOR.base}
              strokeDasharray="2 3"
              label={{ value: `${num(pb, 1)} a`, position: "insideTopRight", ...ETIQUETA_EJE, fill: COLOR.base }}
            />
          )}
          {ps != null && (
            <ReferenceLine
              x={ps}
              stroke={COLOR.alterno}
              strokeDasharray="2 3"
              label={{ value: `${num(ps, 1)} a`, position: "insideTopLeft", ...ETIQUETA_EJE }}
            />
          )}
          <Line dataKey="sin" stroke={COLOR.alterno} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
          <Line dataKey="base" stroke={COLOR.base} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Tooltip
            cursor={{ stroke: COLOR.eje, strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as (typeof filas)[number];
              return (
                <CajaTooltip
                  titulo={`Año ${p.anio} · M COP`}
                  filas={[
                    { etiqueta: "Con Ley 1715", valor: num(p.base), color: COLOR.base, forma: "linea" },
                    { etiqueta: "Sin Ley 1715", valor: num(p.sin), color: COLOR.alterno, forma: "guion" },
                    { etiqueta: "Diferencia", valor: num(p.base - p.sin), fuerte: true },
                  ]}
                />
              );
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Tarjeta>
  );
}
