"use client";

import { ComoLeerla } from "@/components/graficas/comun";
import { Info } from "@/components/Info";
import { COLOR } from "@/lib/colores";
import { mcop, num, pct, SIN_DATO } from "@/lib/formato";
import type { Escenario, FilaTornado, ResultadoSensibilidad } from "@/lib/tipos";

const NOMBRE_VARIABLE: Record<string, string> = {
  cu: "CU (con G y Cv)",
  capex_fv: "CAPEX fotovoltaico",
  capex_bateria: "CAPEX de batería",
  tasa_descuento: "Tasa de descuento",
  escalamiento_tarifa: "Escalamiento de tarifa",
  degradacion: "Degradación FV",
  precio_exc2: "Precio de Exc2",
};

const NOMBRE_ESCENARIO: Record<string, string> = {
  base: "Base",
  exc2_a_mc: "Exc2 valorado a Mc",
  sin_ley1715: "Sin incentivos Ley 1715",
  jornada_2_turnos: "Jornada de 2 turnos",
  jornada_continua: "Jornada continua",
};

// Constantes de búsqueda de breakeven_bateria (src/autosolar/sensibilidad.py)
const VECES_MAX = 64;
const VECES_MIN = 1024;

const DELTA_NEUTRO = 1e-9;

function signo(v: number): string {
  return v > 0 ? "+" : v < 0 ? "−" : "";
}

/** Por qué una variable no mueve el VPN de la solución evaluada. */
function notaSinEfecto(f: FilaTornado, kwhBat: number): string {
  if (f.variable === "capex_bateria" && kwhBat === 0) {
    return "Sin efecto: la solución no incluye batería, así que su CAPEX no entra al flujo.";
  }
  if (f.variable === "precio_exc2") {
    return "Sin efecto: la solución no genera Exc2 (todo lo exportado cabe en Exc1), así que su precio no entra al flujo.";
  }
  return "Sin efecto sobre el VPN de esta solución.";
}

export default function Sensibilidad({ datos }: { datos: ResultadoSensibilidad }) {
  return (
    <div className="space-y-5">
      <p className="text-sm text-tinta-2">
        Sistema evaluado: <b className="num">{num(datos.sistema.kwp)} kWp</b> +{" "}
        <b className="num">{num(datos.sistema.kwh_bat)} kWh</b> de batería (la mejor de la grilla por VPN).
      </p>
      <BreakevenBateria datos={datos} />
      <Tornado filas={datos.tornado} kwhBat={datos.sistema.kwh_bat} />
      <TablaEscenarios filas={datos.escenarios} />
    </div>
  );
}

/* ------------------------------ tornado ------------------------------ */

function Tornado({ filas, kwhBat }: { filas: FilaTornado[]; kwhBat: number }) {
  const base = filas[0]?.vpn_base ?? 0;
  const amplitud = (f: FilaTornado) => Math.abs(f.vpn_alto - f.vpn_bajo);
  const tol = Math.max(1, Math.abs(base) * DELTA_NEUTRO);
  const conEfecto = filas.filter((f) => amplitud(f) > tol);
  const sinEfecto = filas.filter((f) => amplitud(f) <= tol);

  // eje: desvío máximo respecto al base, simétrico para que el base quede al centro
  const maxDesvio = Math.max(1, ...filas.flatMap((f) => [Math.abs(f.vpn_bajo - base), Math.abs(f.vpn_alto - base)]));
  const lim = maxDesvio * 1.1; // las etiquetas caben en el margen lateral (mx-10)
  const x = (vpn: number) => 50 + ((vpn - base) / lim) * 50; // % del ancho
  const marcas = [-1, -0.5, 0, 0.5, 1].map((t) => t * maxDesvio + base);

  return (
    <figure className="overflow-hidden rounded-lg border border-borde bg-panel">
      <figcaption className="space-y-2 px-4 pt-4 sm:px-5">
        <div>
          <h3 className="text-[15px] leading-snug font-semibold">Tornado: ¿qué mueve más el VPN?</h3>
          <p className="mt-0.5 text-xs text-tinta-3">
            VPN [M COP] con cada variable ±20 %, sistema fijo · base{" "}
            <b className="num whitespace-nowrap">{mcop(base)} M COP</b>
            <Info termino="VPN" />
          </p>
        </div>
        <ul className="flex gap-4 text-xs text-tinta-2">
          <li className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-[3px]" style={{ background: COLOR.autoconsumo }} />
            Variable −20 %
          </li>
          <li className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-[3px]" style={{ background: COLOR.fv }} />
            Variable +20 %
          </li>
        </ul>
      </figcaption>

      <div className="grid grid-cols-[6rem_1fr] sm:grid-cols-[minmax(110px,170px)_1fr] items-center gap-x-3 px-4 pt-3 pb-4 sm:px-5">
        {conEfecto.map((f) => (
          <FilaBarras key={f.variable} f={f} base={base} x={x} />
        ))}
        {/* eje */}
        <div />
        <div className="relative mx-10 mt-1 h-5 border-t border-borde text-[11px] text-tinta-3">
          {marcas.map((m, i) => (
            <span
              key={i}
              // en móvil solo la marca central (el VPN base), para que no se encimen
              className={`num absolute -translate-x-1/2 pt-1 ${i === 2 ? "" : "hidden sm:inline"}`}
              style={{ left: `${Math.min(97, Math.max(3, x(m)))}%` }}
            >
              {mcop(m)}
            </span>
          ))}
        </div>
      </div>

      {sinEfecto.length > 0 && (
        <ul className="space-y-1 px-4 pb-4 text-[13px] text-tinta-2 sm:px-5">
          {sinEfecto.map((f) => (
            <li key={f.variable}>
              <b>{NOMBRE_VARIABLE[f.variable] ?? f.variable}</b> — {notaSinEfecto(f, kwhBat)}
            </li>
          ))}
        </ul>
      )}

      <ComoLeerla
        parrafos={[
          "Cada fila mueve una sola variable un 20 % hacia abajo (azul) y hacia arriba (naranja); la línea central es el VPN base. Cuanto más largas las barras, más sensible es el proyecto a esa variable.",
          "Azul y naranja no son peor y mejor caso: en variables como la tasa de descuento o el CAPEX, subir la variable baja el VPN, así que el naranja queda a la izquierda del base.",
        ]}
      />
    </figure>
  );
}

function FilaBarras({ f, base, x }: { f: FilaTornado; base: number; x: (v: number) => number }) {
  const nombre = NOMBRE_VARIABLE[f.variable] ?? f.variable;
  const barras = [
    { vpn: f.vpn_bajo, color: COLOR.autoconsumo, rotulo: "−20 %" },
    { vpn: f.vpn_alto, color: COLOR.fv, rotulo: "+20 %" },
  ];
  return (
    <>
      <div className="py-2 pr-1 text-right text-[13px] leading-tight text-tinta-2">{nombre}</div>
      <div className="relative mx-10 h-10">
        <div className="absolute inset-y-0 w-px bg-tinta/60" style={{ left: "50%" }} />
        {barras.map((b, i) => {
          const a = x(base);
          const e = x(b.vpn);
          const izq = Math.min(a, e);
          const ancho = Math.abs(e - a);
          const hacia = b.vpn >= base ? "der" : "izq";
          return (
            <div
              key={b.rotulo}
              className="absolute h-[15px]"
              style={{ top: i === 0 ? 3 : 22, left: `${izq}%`, width: `${ancho}%` }}
              title={`${nombre} ${b.rotulo}: VPN ${mcop(b.vpn)} M COP (${signo(b.vpn - base)}${mcop(Math.abs(b.vpn - base), 1)})`}
            >
              <div className="size-full rounded-[3px]" style={{ background: b.color }} />
              <span
                className="num absolute top-0 text-[11px] leading-[15px] whitespace-nowrap text-tinta-2"
                style={hacia === "der" ? { left: "100%", paddingLeft: 4 } : { right: "100%", paddingRight: 4 }}
              >
                {signo(b.vpn - base)}
                {mcop(Math.abs(b.vpn - base), 1)}
              </span>
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ------------------------------ escenarios ------------------------------ */

type Columna = {
  titulo: string;
  info?: "VPN" | "TIR" | "Payback";
  valor: (e: Escenario) => number | null;
  fmt: (v: number | null) => string;
  delta: (d: number) => string;
  mejor: "mayor" | "menor" | null;
};

const COLUMNAS: Columna[] = [
  { titulo: "FV [kWp]", valor: (e) => e.kwp, fmt: (v) => num(v), delta: (d) => num(Math.abs(d)), mejor: null },
  { titulo: "Batería [kWh]", valor: (e) => e.kwh_bat, fmt: (v) => num(v), delta: (d) => num(Math.abs(d)), mejor: null },
  { titulo: "VPN [M COP]", info: "VPN", valor: (e) => e.vpn, fmt: (v) => mcop(v), delta: (d) => mcop(Math.abs(d)), mejor: "mayor" },
  { titulo: "TIR", info: "TIR", valor: (e) => e.tir, fmt: (v) => pct(v), delta: (d) => `${num(Math.abs(d) * 100, 1)} pp`, mejor: "mayor" },
  { titulo: "Payback [años]", info: "Payback", valor: (e) => e.payback, fmt: (v) => num(v, 1), delta: (d) => num(Math.abs(d), 1), mejor: "menor" },
  { titulo: "Autoconsumo", valor: (e) => e.autoconsumo_pct, fmt: (v) => pct(v), delta: (d) => `${num(Math.abs(d) * 100, 1)} pp`, mejor: null },
];

function TablaEscenarios({ filas }: { filas: Escenario[] }) {
  const base = filas.find((e) => e.escenario === "base");
  return (
    <section className="min-w-0 rounded-lg border border-borde bg-panel" aria-labelledby="titulo-escenarios">
      <div className="px-4 pt-4 pb-2 sm:px-5">
        <h3 id="titulo-escenarios" className="text-[15px] leading-snug font-semibold">
          Escenarios regulatorios y operativos
        </h3>
        <p className="mt-0.5 text-xs text-tinta-3">
          Cada escenario re-optimiza la mejor solución por VPN. Bajo cada cifra, la diferencia frente al escenario base.
        </p>
      </div>
      <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-sm">
        <thead className="border-b border-borde text-xs text-tinta-2">
          <tr>
            <th className="px-4 py-2 text-left font-semibold">Escenario</th>
            {COLUMNAS.map((c) => (
              <th key={c.titulo} className="px-3 py-2 text-right font-semibold whitespace-nowrap">
                {c.titulo}
                {c.info && <Info termino={c.info} />}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-borde/70">
          {filas.map((e) => {
            const esBase = e.escenario === "base";
            return (
              <tr key={e.escenario} className={esBase ? "bg-fondo/70" : ""}>
                <td className="px-4 py-2 font-medium text-tinta">
                  {NOMBRE_ESCENARIO[e.escenario] ?? e.escenario}
                  {esBase && <span className="ml-1.5 text-xs font-normal text-tinta-3">referencia</span>}
                </td>
                {COLUMNAS.map((c) => {
                  const v = c.valor(e);
                  const b = base ? c.valor(base) : null;
                  const d = v != null && b != null ? v - b : null;
                  const mueve = d != null && Math.abs(d) > 1e-9;
                  const bueno = mueve && c.mejor ? (c.mejor === "mayor" ? d > 0 : d < 0) : null;
                  return (
                    <td key={c.titulo} className="num px-3 py-1.5 text-right">
                      <div className={mueve && !esBase ? "font-semibold" : ""}>{c.fmt(v)}</div>
                      {!esBase && (
                        <div
                          className={`text-xs ${
                            bueno == null ? "text-tinta-3" : bueno ? "text-bien" : "text-error"
                          }`}
                        >
                          {d == null ? SIN_DATO : mueve ? `${d > 0 ? "▲ +" : "▼ −"}${c.delta(d)}` : "="}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </section>
  );
}

/* ------------------------------ breakeven ------------------------------ */

function BreakevenBateria({ datos }: { datos: ResultadoSensibilidad }) {
  const { estado, capex_actual_cop_kwh: actual, capex_breakeven_cop_kwh: umbral } = datos.breakeven;
  const cop = (v: number) => `${num(v)} COP/kWh`;

  let titular: string;
  let detalle: string;
  let acento: string;
  if (estado === "siempre") {
    titular = "La batería conviene a cualquier precio razonable";
    detalle = `Sigue siendo parte de la mejor solución aun con el CAPEX multiplicado por ${VECES_MAX} (${cop(actual * VECES_MAX)}). El precio actual de ${cop(actual)} no es el factor que decide.`;
    acento = COLOR.exc2;
  } else if (estado === "nunca") {
    titular = "La batería no conviene a ningún precio probado";
    detalle = `Ni dividiendo el CAPEX entre ${num(VECES_MIN)} (${cop(actual / VECES_MIN)}) la mejor solución incluiría batería. Con este perfil de carga y estas tarifas, el almacenamiento no aporta valor.`;
    acento = COLOR.importacion;
  } else if (umbral != null && umbral >= actual) {
    titular = `La batería entra mientras cueste menos de ${cop(umbral)}`;
    detalle = `Hoy cuesta ${cop(actual)}: ya está dentro, con un margen de ${pct(umbral / actual - 1, 0)} de sobreprecio antes de que deje de convenir.`;
    acento = COLOR.exc2;
  } else if (umbral != null) {
    titular = `La batería entra si su CAPEX baja a ${cop(umbral)}`;
    detalle = `Hoy cuesta ${cop(actual)}: tendría que abaratarse ${pct(1 - umbral / actual, 0)} para que la mejor solución la incluya.`;
    acento = COLOR.exc1;
  } else {
    return null;
  }

  // escala logarítmica solo cuando hay umbral: dos marcas sobre una barra
  const marcas =
    estado === "umbral" && umbral != null
      ? (() => {
          const lo = Math.min(umbral, actual);
          const hi = Math.max(umbral, actual);
          const l = (v: number) => Math.log(v);
          const pos = (v: number) => 12 + (hi === lo ? 0.5 : (l(v) - l(lo)) / (l(hi) - l(lo))) * 76;
          return { actual: pos(actual), umbral: pos(umbral) };
        })()
      : null;

  return (
    <section className="rounded-lg border border-l-4 border-borde bg-panel p-4 sm:p-5" style={{ borderLeftColor: acento }} aria-label="Breakeven de batería">
      <p className="text-[11px] font-semibold tracking-wider text-tinta-3 uppercase">Breakeven de batería</p>
      <h3 className="mt-1 text-lg leading-snug font-semibold sm:text-xl">{titular}</h3>
      <p className="mt-1 max-w-3xl text-sm text-tinta-2">{detalle}</p>
      {marcas && umbral != null && (
        <div className="mx-10 mt-5 mb-14 max-w-xl sm:mx-0">
          <div className="relative h-1.5 rounded-full bg-borde">
            <Marca x={marcas.umbral} color={acento} etiqueta="Umbral" valor={cop(umbral)} />
            <Marca x={marcas.actual} color={COLOR.tinta} etiqueta="CAPEX actual" valor={cop(actual)} />
          </div>
        </div>
      )}
      <dl className="mt-4 grid max-w-xl gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-tinta-3">capex_cop_kwh actual</dt>
          <dd className="num font-semibold">{cop(actual)}</dd>
        </div>
        <div>
          <dt className="text-xs text-tinta-3">Umbral de breakeven</dt>
          <dd className="num font-semibold">
            {estado === "umbral" && umbral != null ? cop(umbral) : estado === "siempre" ? `> ${cop(actual * VECES_MAX)}` : `< ${cop(actual / VECES_MIN)}`}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function Marca({
  x,
  color,
  etiqueta,
  valor,
  arriba = false,
}: {
  x: number;
  color: string;
  etiqueta: string;
  valor: string;
  arriba?: boolean;
}) {
  return (
    <div className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%` }}>
      <div className="size-3.5 rounded-full border-2 border-panel shadow" style={{ background: color }} />
      <div
        className={`num absolute left-1/2 -translate-x-1/2 text-center text-[11px] leading-tight whitespace-nowrap text-tinta-2 ${
          arriba ? "bottom-5" : "top-5"
        }`}
      >
        <b className="block">{etiqueta}</b>
        {valor}
      </div>
    </div>
  );
}
