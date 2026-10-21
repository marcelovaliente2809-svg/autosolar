"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { COLOR } from "@/lib/colores";
import { num } from "@/lib/formato";
import type { Series } from "@/lib/tipos";
import { CajaTooltip, EJE, ETIQUETA_EJE, Tarjeta } from "./comun";

export default function LcoeValores({
  valores: v,
  kwp,
}: {
  valores: Series["lcoe_vs_valores"];
  kwp: number;
}) {
  const menor100 = kwp <= 100; // CREG 174: Exc1 se acredita a CU − Cv (≤ 100 kW) o a G (> 100 kW)
  const filas = [
    { nombre: "LCOE", valor: v.lcoe, color: COLOR.fv, nota: "Costo nivelado de la energía FV", activa: true },
    ...(v.valor_kwh_marginal != null
      ? [
          {
            nombre: "Valor kWh marginal",
            valor: v.valor_kwh_marginal,
            color: COLOR.base,
            nota: "Lo que vale el kWh extra del último paso de kWp (autoconsumo a CU, el resto a crédito de Exc1)",
            activa: true,
          },
        ]
      : []),
    { nombre: "CU", valor: v.cu, color: COLOR.autoconsumo, nota: "Lo que ahorra cada kWh autoconsumido", activa: true },
    { nombre: "CU − Cv", valor: v.cu_menos_cv, color: COLOR.exc1, nota: menor100 ? "Crédito de Exc1 (≤ 100 kW): aplica" : "Crédito de Exc1 si fuera ≤ 100 kW", activa: menor100 },
    { nombre: "G", valor: v.g, color: COLOR.exc1, nota: menor100 ? "Crédito de Exc1 si fuera > 100 kW" : "Crédito de Exc1 (> 100 kW): aplica", activa: !menor100 },
    { nombre: "Precio Exc2", valor: v.precio_exc2, color: COLOR.exc2, nota: "Lo que se recibe por cada kWh de Exc2", activa: true },
  ];

  return (
    <Tarjeta
      titulo="LCOE frente a los valores de la factura"
      subtitulo={`COP/kWh · sistema de ${num(kwp)} kWp: Exc1 se valora a ${menor100 ? "CU − Cv" : "G"}`}
      comoLeerla={[
        "La barra naranja es lo que cuesta producir un kWh con el sistema (LCOE); la línea punteada la prolonga sobre las demás para comparar. Justo debajo, el valor del kWh marginal: lo que vale la energía que agregó el último paso de kWp. El sistema crece mientras el valor marginal supere al LCOE; cuando cae por debajo, ampliarlo ya no paga.",
        "Toda barra que supera la línea es un destino donde el kWh solar deja margen: autoconsumo (CU), Exc1 (CU − Cv o G, la tenue no aplica a este tamaño) y Exc2; las que quedan por debajo pierden plata.",
      ]}
    >
      <ResponsiveContainer width="100%" height={40 * filas.length + 40}>
        <BarChart data={filas} layout="vertical" margin={{ top: 6, right: 56, bottom: 22, left: 8 }} barCategoryGap="28%">
          <CartesianGrid stroke={COLOR.grilla} horizontal={false} />
          <XAxis
            type="number"
            {...EJE}
            tickFormatter={(x) => num(x)}
            label={{ value: "COP/kWh", position: "insideBottom", offset: -12, ...ETIQUETA_EJE }}
          />
          <YAxis type="category" dataKey="nombre" {...EJE} axisLine={false} width={v.valor_kwh_marginal != null ? 128 : 84} tick={{ fill: COLOR.tinta, fontSize: 12 }} />
          <Bar dataKey="valor" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {filas.map((f) => (
              <Cell key={f.nombre} fill={f.color} fillOpacity={f.activa ? 1 : 0.35} />
            ))}
            <LabelList dataKey="valor" position="right" formatter={(x: number) => num(x)} fill={COLOR.tinta} fontSize={11} />
          </Bar>
          {v.lcoe != null && <ReferenceLine x={v.lcoe} stroke={COLOR.fv} strokeDasharray="4 3" strokeWidth={1.5} />}
          <Tooltip
            cursor={{ fill: COLOR.grilla, fillOpacity: 0.5 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const f = payload[0].payload as (typeof filas)[number];
              const margen = f.nombre !== "LCOE" && f.valor != null && v.lcoe != null ? f.valor - v.lcoe : null;
              return (
                <CajaTooltip
                  titulo={f.nombre}
                  filas={[
                    { etiqueta: f.nota, valor: "" },
                    { etiqueta: "Valor", valor: `${num(f.valor)} COP/kWh`, color: f.color, fuerte: true },
                    ...(margen != null ? [{ etiqueta: "Margen sobre LCOE", valor: `${num(margen)} COP/kWh` }] : []),
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
