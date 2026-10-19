"use client";

import { useState } from "react";
import { SECCIONES, type Campo } from "@/lib/campos";
import type { Errores, Valores } from "@/lib/formulario";

interface Props {
  valores: Valores;
  errores: Errores;
  deshabilitado: boolean;
  onCambio: (ruta: string, valor: string | boolean) => void;
}

export default function Formulario({ valores, errores, deshabilitado, onCambio }: Props) {
  const [abiertas, setAbiertas] = useState<Record<string, boolean>>({ empresa: true });

  return (
    <div className="divide-y divide-borde">
      {SECCIONES.map((s) => {
        const nErr =
          s.campos.filter((c) => errores.campo[c.ruta]).length + (errores.seccion[s.id]?.length ?? 0);
        // una sección con errores se muestra abierta aunque el usuario la haya plegado
        const abierta = abiertas[s.id] || nErr > 0;
        return (
          <section key={s.id}>
            <button
              type="button"
              onClick={() => setAbiertas((a) => ({ ...a, [s.id]: !abierta }))}
              aria-expanded={abierta}
              className="flex w-full items-center justify-between px-4 py-2.5 text-left text-[13px] font-semibold text-tinta hover:bg-fondo/60"
            >
              <span className="flex items-center gap-2">
                {s.titulo}
                {nErr > 0 && (
                  <span className="num rounded-full bg-error px-1.5 py-px text-[10px] font-semibold text-panel">
                    {nErr}
                  </span>
                )}
              </span>
              <svg
                viewBox="0 0 12 12"
                className={`size-3 text-tinta-3 transition-transform ${abierta ? "rotate-180" : ""}`}
                aria-hidden
              >
                <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" />
              </svg>
            </button>
            {abierta && (
              <div className="space-y-2.5 px-4 pt-0.5 pb-4">
                {errores.seccion[s.id]?.map((m) => (
                  <p key={m} className="rounded-md bg-error-fondo px-3 py-2 text-xs text-error">
                    {m}
                  </p>
                ))}
                {s.campos.map((c) => (
                  <CampoForm
                    key={c.ruta}
                    campo={c}
                    valor={valores[c.ruta]}
                    error={errores.campo[c.ruta]}
                    deshabilitado={deshabilitado}
                    onCambio={(v) => onCambio(c.ruta, v)}
                  />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

function CampoForm({
  campo: c,
  valor,
  error,
  deshabilitado,
  onCambio,
}: {
  campo: Campo;
  valor: string | boolean | undefined;
  error?: string;
  deshabilitado: boolean;
  onCambio: (v: string | boolean) => void;
}) {
  const id = `campo-${c.ruta.replace(".", "-")}`;
  const idErr = `${id}-error`;

  if (c.tipo === "booleano") {
    return (
      <div>
        <label htmlFor={id} className="flex cursor-pointer items-start gap-2 text-[13px]">
          <input
            id={id}
            type="checkbox"
            checked={Boolean(valor)}
            disabled={deshabilitado}
            onChange={(e) => onCambio(e.target.checked)}
            className="mt-0.5 size-4 accent-acento"
          />
          <span>
            {c.etiqueta}
            {c.ayuda && <span className="block text-[11px] leading-snug text-tinta-3">{c.ayuda}</span>}
          </span>
        </label>
        {error && <p className="mt-1 text-xs text-error">{error}</p>}
      </div>
    );
  }

  const borde = error
    ? "border-error focus-within:ring-error/30"
    : "border-borde focus-within:border-acento focus-within:ring-acento/25";

  return (
    <div>
      <label htmlFor={id} className="mb-0.5 block text-xs text-tinta-2">
        {c.etiqueta}
      </label>
      <div
        className={`flex items-center rounded border bg-campo focus-within:ring-2 ${borde} ${deshabilitado ? "opacity-60" : ""}`}
      >
        {c.tipo === "opcion" ? (
          <select
            id={id}
            value={String(valor ?? "")}
            disabled={deshabilitado}
            onChange={(e) => onCambio(e.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? idErr : undefined}
            className="w-full min-w-0 bg-transparent px-2 py-1 text-[13px] outline-none"
          >
            {c.opciones?.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.etiqueta}
              </option>
            ))}
          </select>
        ) : (
          <input
            id={id}
            type="text"
            inputMode={c.tipo === "texto" ? "text" : "decimal"}
            value={String(valor ?? "")}
            placeholder={c.placeholder}
            disabled={deshabilitado}
            onChange={(e) => onCambio(e.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? idErr : undefined}
            className={`w-full min-w-0 bg-transparent px-2 py-1 text-[13px] outline-none ${c.tipo === "texto" ? "" : "num text-right"}`}
          />
        )}
        {c.unidad && (
          <span className="shrink-0 pr-2 pl-1 text-[11px] whitespace-nowrap text-tinta-3">{c.unidad}</span>
        )}
      </div>
      {error ? (
        <p id={idErr} className="mt-1 text-xs text-error">
          {error}
        </p>
      ) : (
        c.ayuda && <p className="mt-0.5 text-[11px] leading-snug text-tinta-3">{c.ayuda}</p>
      )}
    </div>
  );
}
