"use client";

import { COLOR } from "@/lib/colores";

/** Tarjeta de una gráfica: título, subtítulo con unidades, leyenda, la gráfica y "Cómo leerla" plegable. */
export function Tarjeta({
  titulo,
  subtitulo,
  leyenda,
  comoLeerla,
  ancha = false,
  children,
}: {
  titulo: string;
  subtitulo?: React.ReactNode;
  leyenda?: React.ReactNode;
  comoLeerla: [React.ReactNode, React.ReactNode];
  ancha?: boolean; // ocupa las dos columnas de la grilla de resultados
  children: React.ReactNode;
}) {
  return (
    <figure
      className={`flex min-w-0 flex-col rounded-lg border border-borde bg-panel ${ancha ? "xl:col-span-2" : ""}`}
    >
      <figcaption className="space-y-2 px-4 pt-4 sm:px-5">
        <div>
          <h3 className="text-[15px] leading-snug font-semibold">{titulo}</h3>
          {subtitulo && <p className="mt-0.5 text-xs text-tinta-3">{subtitulo}</p>}
        </div>
        {leyenda}
      </figcaption>
      <div className="flex-1 px-2 pt-3 sm:px-3">{children}</div>
      <ComoLeerla parrafos={comoLeerla} />
    </figure>
  );
}

/** Pie plegable de una tarjeta con la explicación de la gráfica. */
export function ComoLeerla({ parrafos }: { parrafos: React.ReactNode[] }) {
  return (
    <details className="group border-t border-borde text-[13px] leading-relaxed text-tinta-2">
      <summary className="flex cursor-pointer items-center gap-1.5 px-4 py-2.5 text-xs font-medium text-tinta-3 select-none hover:text-tinta sm:px-5">
        <svg viewBox="0 0 12 12" className="size-3 transition-transform group-open:rotate-90" aria-hidden>
          <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
        Cómo leerla
      </summary>
      <div className="space-y-1.5 px-4 pb-4 sm:px-5">
        {parrafos.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
    </details>
  );
}

export interface ItemLeyenda {
  etiqueta: string;
  color: string;
  forma?: "bloque" | "linea" | "guion";
}

export function Leyenda({ items }: { items: ItemLeyenda[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-tinta-2">
      {items.map((i) => (
        <li key={i.etiqueta} className="flex items-center gap-1.5">
          <Muestra color={i.color} forma={i.forma} />
          {i.etiqueta}
        </li>
      ))}
    </ul>
  );
}

export function Muestra({ color, forma = "bloque" }: { color: string; forma?: ItemLeyenda["forma"] }) {
  if (forma === "bloque") {
    return <span className="inline-block size-2.5 shrink-0 rounded-[3px]" style={{ background: color }} />;
  }
  return (
    <svg width="16" height="8" aria-hidden className="shrink-0">
      <line
        x1="1"
        x2="15"
        y1="4"
        y2="4"
        stroke={color}
        strokeWidth="2"
        strokeDasharray={forma === "guion" ? "4 3" : undefined}
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Caja de tooltip común: título y filas (etiqueta, valor) con muestra de color. */
export function CajaTooltip({
  titulo,
  filas,
}: {
  titulo: string;
  filas: { etiqueta: string; valor: string; color?: string; forma?: ItemLeyenda["forma"]; fuerte?: boolean }[];
}) {
  return (
    <div className="max-w-[280px] min-w-44 rounded-md border border-borde bg-panel/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
      <p className="mb-1 font-semibold text-tinta">{titulo}</p>
      <table className="w-full">
        <tbody>
          {filas.map((f) => (
            <tr key={f.etiqueta} className={f.fuerte ? "font-semibold" : ""}>
              <td className="py-0.5 pr-3 text-tinta-2">
                <span className="flex items-center gap-1.5">
                  {f.color ? <Muestra color={f.color} forma={f.forma} /> : <span className="w-2.5" />}
                  {f.etiqueta}
                </span>
              </td>
              <td className="num py-0.5 text-right text-tinta">{f.valor}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Props comunes de ejes y grilla (recesivos)
export const EJE = {
  stroke: COLOR.grilla,
  tick: { fill: COLOR.eje, fontSize: 11 },
  tickLine: false,
} as const;

export const ETIQUETA_EJE = { fill: COLOR.eje, fontSize: 11 } as const;
