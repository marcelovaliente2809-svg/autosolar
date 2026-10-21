"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { COLOR } from "@/lib/colores";
import { num } from "@/lib/formato";
import type { Dia } from "@/lib/tipos";
import { CajaTooltip, EJE, ETIQUETA_EJE, Leyenda, Tarjeta } from "./comun";

function filas(d: Dia) {
  return d.hora.map((h, i) => ({
    hora: h,
    autoconsumo: d.autoconsumo[i],
    descarga_bat: d.descarga_bat[i],
    importado: d.importado[i],
    generacion: d.generacion[i],
    carga: d.carga[i],
    carga_bat: d.carga_bat[i],
    exportado: d.exportado[i],
    soc: d.soc[i],
  }));
}

function Panel({
  titulo,
  dia,
  yMax,
  ticks,
  conBateria,
}: {
  titulo: string;
  dia: Dia;
  yMax: number;
  ticks: number[];
  conBateria: boolean;
}) {
  const fecha = new Date(`${dia.fecha}T00:00:00`).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "long",
  });
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-tinta-2">
        {titulo} <span className="font-normal text-tinta-3">· {fecha}</span>
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={filas(dia)} margin={{ top: 6, right: 8, bottom: 22, left: 0 }}>
          <CartesianGrid stroke={COLOR.grilla} vertical={false} />
          <XAxis
            dataKey="hora"
            {...EJE}
            ticks={[0, 6, 12, 18, 23]}
            tickFormatter={(h) => `${h}:00`}
            label={{ value: "Hora", position: "insideBottom", offset: -12, ...ETIQUETA_EJE }}
          />
          <YAxis
            {...EJE}
            axisLine={false}
            width={52}
            domain={[0, yMax]}
            ticks={ticks}
            tickFormatter={(v) => num(v)}
            label={{ value: "Potencia [kW]", angle: -90, position: "insideLeft", offset: 6, ...ETIQUETA_EJE, style: { textAnchor: "middle" } }}
          />
          {/* La carga se cubre con autoconsumo directo + descarga de batería + importación */}
          <Area dataKey="autoconsumo" stackId="c" type="linear" fill={COLOR.autoconsumo} fillOpacity={0.85} stroke="none" isAnimationActive={false} />
          {conBateria && (
            <Area dataKey="descarga_bat" stackId="c" type="linear" fill={COLOR.autoconsumoBat} fillOpacity={0.9} stroke="none" isAnimationActive={false} />
          )}
          <Area dataKey="importado" stackId="c" type="linear" fill={COLOR.importacion} fillOpacity={0.55} stroke="none" isAnimationActive={false} />
          {/* Encima de la carga: lo que sale a la red (generación − autoconsumo − carga de batería) */}
          <Area dataKey="exportado" stackId="c" type="linear" fill={COLOR.exc2} fillOpacity={0.45} stroke="none" isAnimationActive={false} />
          <Line dataKey="generacion" type="linear" stroke={COLOR.fv} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Tooltip
            cursor={{ stroke: COLOR.eje, strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as ReturnType<typeof filas>[number];
              return (
                <CajaTooltip
                  titulo={`${p.hora}:00–${p.hora + 1}:00 · kWh`}
                  filas={[
                    { etiqueta: "Generación FV", valor: num(p.generacion, 1), color: COLOR.fv, forma: "linea" },
                    { etiqueta: "Carga", valor: num(p.carga, 1), fuerte: true },
                    { etiqueta: "Autoconsumo directo", valor: num(p.autoconsumo, 1), color: COLOR.autoconsumo },
                    ...(conBateria
                      ? [
                          { etiqueta: "Descarga batería", valor: num(p.descarga_bat, 1), color: COLOR.autoconsumoBat },
                          { etiqueta: "Carga batería", valor: num(p.carga_bat, 1) },
                          { etiqueta: "Estado de carga", valor: `${num(p.soc, 0)} kWh` },
                        ]
                      : []),
                    { etiqueta: "Importación", valor: num(p.importado, 1), color: COLOR.importacion },
                    { etiqueta: "Exportación", valor: num(p.exportado, 1), color: COLOR.exc2 },
                  ]}
                />
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function DiaTipico({ habil, domingo }: { habil: Dia; domingo: Dia }) {
  const conBateria = [...habil.descarga_bat, ...domingo.descarga_bat, ...habil.carga_bat].some((v) => v > 0);
  const tope = Math.max(...habil.carga, ...habil.generacion, ...domingo.carga, ...domingo.generacion);
  const paso = [10, 25, 50, 100, 200, 250, 500, 1000].find((s) => (tope * 1.05) / s <= 5) ?? 2000;
  const yMax = Math.ceil((tope * 1.05) / paso) * paso;
  const ticks = Array.from({ length: yMax / paso + 1 }, (_, i) => i * paso);
  return (
    <Tarjeta
      titulo="Día típico"
      ancha
      subtitulo="Potencia media horaria [kW = kWh/h] · julio, solución recomendada"
      leyenda={
        <Leyenda
          items={[
            { etiqueta: "Generación FV", color: COLOR.fv, forma: "linea" },
            { etiqueta: "Autoconsumo", color: COLOR.autoconsumo },
            ...(conBateria ? [{ etiqueta: "Autoconsumo vía batería", color: COLOR.autoconsumoBat }] : []),
            { etiqueta: "Importación", color: COLOR.importacion },
            { etiqueta: "Exportación", color: COLOR.exc2 },
          ]}
        />
      }
      comoLeerla={[
        "El área apilada es la carga de la planta, separada en lo que cubre el sol (azul) y lo que se compra a la red (gris); la línea naranja es la generación FV.",
        "Sobre la carga, el área verde es lo que se exporta a la red; si la línea naranja queda por encima del verde, esa diferencia está cargando la batería. Compare el miércoles hábil con el domingo, cuando la planta consume poco y casi todo se exporta.",
      ]}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Panel titulo="Miércoles hábil" dia={habil} yMax={yMax} ticks={ticks} conBateria={conBateria} />
        <Panel titulo="Domingo" dia={domingo} yMax={yMax} ticks={ticks} conBateria={conBateria} />
      </div>
    </Tarjeta>
  );
}
