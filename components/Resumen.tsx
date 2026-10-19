"use client";

import { Info } from "@/components/Info";
import type { Termino } from "@/lib/glosario";
import { mcop, num, SIN_DATO } from "@/lib/formato";
import type { Fila } from "@/lib/tipos";

function Kpi({
  etiqueta,
  valor,
  unidad,
  info,
}: {
  etiqueta: string;
  valor: string;
  unidad: string;
  info?: Termino;
}) {
  return (
    <div className="min-w-0 bg-panel px-3 py-2.5 sm:px-4">
      <dt className="flex items-center text-xs text-tinta-3">
        <span className="truncate">{etiqueta}</span>
        {info && <Info termino={info} />}
      </dt>
      <dd className="mt-0.5 truncate leading-tight">
        <span className="num text-xl font-medium text-tinta">{valor}</span>
        {valor !== SIN_DATO && <span className="ml-1 text-xs text-tinta-3">{unidad}</span>}
      </dd>
    </div>
  );
}

export function Kpis({ mejor }: { mejor: Fila }) {
  return (
    <dl className="grid grid-cols-2 gap-px bg-borde sm:grid-cols-4 2xl:grid-cols-7">
      <Kpi etiqueta="FV" valor={num(mejor.kwp)} unidad="kWp" />
      <Kpi etiqueta="Batería" valor={num(mejor.kwh_bat)} unidad="kWh" />
      <Kpi etiqueta="VPN" valor={mcop(mejor.vpn)} unidad="M COP" info="VPN" />
      <Kpi etiqueta="TIR" valor={mejor.tir == null ? SIN_DATO : num(mejor.tir * 100, 1)} unidad="%" info="TIR" />
      <Kpi etiqueta="Payback" valor={num(mejor.payback, 1)} unidad="años" info="Payback" />
      <Kpi etiqueta="LCOE" valor={num(mejor.lcoe)} unidad="COP/kWh" />
      <Kpi etiqueta="Autoconsumo" valor={num(mejor.autoconsumo_pct * 100, 1)} unidad="%" />
      {/* celdas vacías para cerrar la grilla de 2 y de 4 columnas */}
      <div className="bg-panel 2xl:hidden" />
    </dl>
  );
}

/** Frase de una línea con la decisión: qué instalar, VPN y recuperación. */
function frase(m: Fila): string {
  const sistema =
    m.kwh_bat > 0 ? `${num(m.kwp)} kWp con ${num(m.kwh_bat)} kWh de batería` : `${num(m.kwp)} kWp sin batería`;
  if (m.vpn == null || m.vpn <= 0) {
    return `Ninguna combinación de la grilla recupera la inversión: la mejor, ${sistema}, tiene VPN ${mcop(m.vpn)} M COP.`;
  }
  const recupera =
    m.payback == null ? "sin recuperación dentro del horizonte" : `recuperación en ${num(m.payback, 1)} años`;
  return `Instalar ${sistema}: VPN ${mcop(m.vpn)} M COP, ${recupera}.`;
}

/** Cabecera de resultados: la decisión en una frase y los KPIs debajo. */
export function Recomendacion({ mejor, empresa }: { mejor: Fila; empresa: string }) {
  const viable = mejor.vpn != null && mejor.vpn > 0;
  return (
    <section aria-labelledby="titulo-recomendacion" className="overflow-hidden rounded-lg border border-borde bg-panel">
      <div className={`border-l-4 px-4 py-4 sm:px-5 ${viable ? "border-acento" : "border-tinta-3"}`}>
        <h2 id="titulo-recomendacion" className="text-xs font-medium text-tinta-3">
          Recomendación · {empresa}
        </h2>
        <p className="mt-1 text-lg leading-snug font-semibold text-balance text-tinta sm:text-xl">{frase(mejor)}</p>
        <p className="mt-1 text-xs text-tinta-3">La combinación de potencia FV y batería con mayor VPN en la grilla evaluada.</p>
      </div>
      <div className="border-t border-borde">
        <Kpis mejor={mejor} />
      </div>
    </section>
  );
}

interface Metrica {
  etiqueta: string;
  unidad: string;
  valor: (f: Fila) => number | null;
  fmt: (v: number | null) => string;
  mejorEs?: "mayor" | "menor"; // para resaltar la columna ganadora
  info?: Termino;
}

const METRICAS: Metrica[] = [
  { etiqueta: "Potencia FV", unidad: "kWp", valor: (f) => f.kwp, fmt: (v) => num(v) },
  { etiqueta: "Batería", unidad: "kWh", valor: (f) => f.kwh_bat, fmt: (v) => num(v) },
  { etiqueta: "CAPEX", unidad: "M COP", valor: (f) => f.capex, fmt: (v) => mcop(v), mejorEs: "menor" },
  { etiqueta: "Ahorro año 1", unidad: "M COP", valor: (f) => f.ahorro_anio1, fmt: (v) => mcop(v), mejorEs: "mayor" },
  { etiqueta: "VPN", info: "VPN", unidad: "M COP", valor: (f) => f.vpn, fmt: (v) => mcop(v), mejorEs: "mayor" },
  { etiqueta: "TIR", info: "TIR", unidad: "%", valor: (f) => f.tir, fmt: (v) => (v == null ? SIN_DATO : num(v * 100, 1)), mejorEs: "mayor" },
  { etiqueta: "Payback", info: "Payback", unidad: "años", valor: (f) => f.payback, fmt: (v) => num(v, 1), mejorEs: "menor" },
  { etiqueta: "LCOE", info: "LCOE", unidad: "COP/kWh", valor: (f) => f.lcoe, fmt: (v) => num(v), mejorEs: "menor" },
  { etiqueta: "Autoconsumo", unidad: "%", valor: (f) => f.autoconsumo_pct, fmt: (v) => (v == null ? SIN_DATO : num(v * 100, 1)), mejorEs: "mayor" },
  { etiqueta: "Exc1", info: "Exc1", unidad: "MWh/año", valor: (f) => f.exc1_kwh / 1e3, fmt: (v) => num(v) },
  { etiqueta: "Exc2", info: "Exc2", unidad: "MWh/año", valor: (f) => f.exc2_kwh / 1e3, fmt: (v) => num(v) },
  { etiqueta: "Ciclos de batería", unidad: "ciclos/año", valor: (f) => f.ciclos, fmt: (v) => num(v) },
];

function gana(m: Metrica, a: number | null, b: number | null): boolean {
  if (!m.mejorEs || a == null) return false;
  if (b == null) return true;
  return m.mejorEs === "mayor" ? a > b : a < b;
}

export function Comparacion({
  sinBat,
  conBat,
  mejor,
}: {
  sinBat: Fila | null;
  conBat: Fila | null;
  mejor: Fila;
}) {
  const esMejor = (f: Fila | null) => f != null && f.kwp === mejor.kwp && f.kwh_bat === mejor.kwh_bat;
  const Encabezado = ({ titulo, f }: { titulo: string; f: Fila | null }) => (
    <th className="px-3 py-2 text-right font-semibold">
      <span className="inline-flex items-center gap-1.5">
        {titulo}
        {esMejor(f) && (
          <span className="rounded-sm bg-acento-suave px-1.5 py-px text-[10px] font-semibold tracking-wide text-tinta uppercase">
            Recomendada
          </span>
        )}
      </span>
    </th>
  );

  return (
    <section className="min-w-0 rounded-lg border border-borde bg-panel" aria-labelledby="titulo-comparacion">
      <div className="px-4 pt-4 pb-2 sm:px-5">
        <h3 id="titulo-comparacion" className="text-[15px] leading-snug font-semibold">
          Mejor sin batería vs. mejor con batería
        </h3>
        <p className="mt-0.5 text-xs text-tinta-3">
          La mejor combinación de cada familia por VPN; en negrita, la que gana en cada indicador.
        </p>
      </div>
      <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-sm">
        <thead className="border-b border-borde text-xs text-tinta-2">
          <tr>
            <th className="px-4 py-2 text-left font-semibold">Indicador</th>
            <Encabezado titulo="Sin batería" f={sinBat} />
            <Encabezado titulo="Con batería" f={conBat} />
            <th className="px-4 py-2 text-right font-semibold">Diferencia</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-borde/70">
          {METRICAS.map((m) => {
            const a = sinBat ? m.valor(sinBat) : null;
            const b = conBat ? m.valor(conBat) : null;
            const delta = a != null && b != null ? b - a : null;
            return (
              <tr key={m.etiqueta}>
                <td className="px-4 py-1.5 text-tinta-2">
                  {m.etiqueta} <span className="text-xs text-tinta-3">[{m.unidad}]</span>
                  {m.info && <Info termino={m.info} />}
                </td>
                <td className={`num px-3 py-1.5 text-right ${gana(m, a, b) ? "font-semibold" : ""}`}>
                  {sinBat ? m.fmt(a) : SIN_DATO}
                </td>
                <td className={`num px-3 py-1.5 text-right ${gana(m, b, a) ? "font-semibold" : ""}`}>
                  {conBat ? m.fmt(b) : SIN_DATO}
                </td>
                <td className="num px-4 py-1.5 text-right text-tinta-3">
                  {delta == null ? SIN_DATO : `${delta > 0 ? "+" : ""}${m.fmt(delta)}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
      {!conBat && (
        <p className="px-4 pb-3 text-xs text-tinta-3">
          La grilla de baterías no tiene tamaños mayores que 0 kWh.
        </p>
      )}
    </section>
  );
}
