"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { COLOR } from "@/lib/colores";
import { MESES, num } from "@/lib/formato";
import type { Series } from "@/lib/tipos";
import { CajaTooltip, EJE, ETIQUETA_EJE, Leyenda, Tarjeta } from "./comun";

const SEP = { stroke: "#fcfcfb", strokeWidth: 1 }; // separación entre segmentos apilados

export default function BalanceMensual({ datos }: { datos: Series["balance_mensual"] }) {
  // kWh → MWh
  const filas = datos.mes.map((m, i) => ({
    mes: MESES[m - 1],
    auto_g: datos.autoconsumo_kwh[i] / 1e3,
    exc1: datos.exc1_kwh[i] / 1e3,
    exc2: datos.exc2_kwh[i] / 1e3,
    auto_c: datos.autoconsumo_kwh[i] / 1e3,
    imp: datos.importado_kwh[i] / 1e3,
    gen: datos.generacion_kwh[i] / 1e3,
    con: datos.consumo_kwh[i] / 1e3,
  }));
  const etiqueta = (texto: string) => ({
    position: "top" as const,
    formatter: () => texto,
    fill: COLOR.eje,
    fontSize: 10,
  });

  return (
    <Tarjeta
      titulo="Balance mensual de energía"
      subtitulo="Energía [MWh/mes] · barra G = generación FV, barra C = consumo de la planta"
      leyenda={
        <Leyenda
          items={[
            { etiqueta: "Autoconsumo", color: COLOR.autoconsumo },
            { etiqueta: "Exc1", color: COLOR.exc1 },
            { etiqueta: "Exc2", color: COLOR.exc2 },
            { etiqueta: "Importación", color: COLOR.importacion },
          ]}
        />
      }
      comoLeerla={[
        "En cada mes, la barra G reparte la generación en autoconsumo, Exc1 (exportado hasta lo importado, se cruza en la factura) y Exc2 (lo que excede lo importado, se vende).",
        "La barra C reparte el consumo en autoconsumo e importación; el tramo azul es el mismo en ambas, así que mientras más alto sea frente a la barra C, menos depende la planta de la red.",
      ]}
    >
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={filas} margin={{ top: 16, right: 12, bottom: 22, left: 8 }} barGap={3} barCategoryGap="22%">
          <CartesianGrid stroke={COLOR.grilla} vertical={false} />
          <XAxis
            dataKey="mes"
            {...EJE}
            label={{ value: "Mes", position: "insideBottom", offset: -12, ...ETIQUETA_EJE }}
          />
          <YAxis
            {...EJE}
            axisLine={false}
            width={56}
            tickFormatter={(v) => num(v)}
            label={{ value: "Energía [MWh]", angle: -90, position: "insideLeft", offset: 4, ...ETIQUETA_EJE, style: { textAnchor: "middle" } }}
          />
          <Bar dataKey="auto_g" stackId="g" fill={COLOR.autoconsumo} {...SEP} isAnimationActive={false} />
          <Bar dataKey="exc1" stackId="g" fill={COLOR.exc1} {...SEP} isAnimationActive={false} />
          <Bar dataKey="exc2" stackId="g" fill={COLOR.exc2} {...SEP} radius={[3, 3, 0, 0]} isAnimationActive={false}>
            <LabelList dataKey="exc2" {...etiqueta("G")} />
          </Bar>
          <Bar dataKey="auto_c" stackId="c" fill={COLOR.autoconsumo} {...SEP} isAnimationActive={false} />
          <Bar dataKey="imp" stackId="c" fill={COLOR.importacion} {...SEP} radius={[3, 3, 0, 0]} isAnimationActive={false}>
            <LabelList dataKey="imp" {...etiqueta("C")} />
          </Bar>
          <Tooltip
            cursor={{ fill: "rgba(28,36,48,0.04)" }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as (typeof filas)[number];
              return (
                <CajaTooltip
                  titulo={`${label} · MWh`}
                  filas={[
                    { etiqueta: "Generación (G)", valor: num(p.gen, 1), fuerte: true },
                    { etiqueta: "Autoconsumo", valor: num(p.auto_g, 1), color: COLOR.autoconsumo },
                    { etiqueta: "Exc1", valor: num(p.exc1, 1), color: COLOR.exc1 },
                    { etiqueta: "Exc2", valor: num(p.exc2, 1), color: COLOR.exc2 },
                    { etiqueta: "Consumo (C)", valor: num(p.con, 1), fuerte: true },
                    { etiqueta: "Importación", valor: num(p.imp, 1), color: COLOR.importacion },
                  ]}
                />
              );
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </Tarjeta>
  );
}
