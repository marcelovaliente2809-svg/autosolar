"use client";

import { createContext, useContext, useId, useState } from "react";
import type { Termino, Tips } from "@/lib/glosario";

const TipsContext = createContext<Tips>({});
export const ProveedorTips = TipsContext.Provider;

/** Ícono (i) con tooltip de una línea; el texto viene del glosario. Sin texto, no pinta nada. */
export function Info({ termino }: { termino: Termino }) {
  const texto = useContext(TipsContext)[termino];
  const id = useId();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  if (!texto) return null;

  // position: fixed para que no lo recorten los contenedores con overflow (tablas, KPIs)
  function mostrar(el: HTMLElement) {
    const r = el.getBoundingClientRect();
    setPos({ x: r.left + r.width / 2, y: r.bottom });
  }

  // la mitad del ancho máximo del tooltip, para que no se salga de la pantalla en móvil
  const medio = typeof window === "undefined" ? 220 : Math.min(220, (window.innerWidth - 24) / 2);

  return (
    <span className="inline-flex align-middle">
      <button
        type="button"
        aria-label={`Qué es ${termino}`}
        aria-describedby={pos ? id : undefined}
        onMouseEnter={(e) => mostrar(e.currentTarget)}
        onMouseLeave={() => setPos(null)}
        onFocus={(e) => mostrar(e.currentTarget)}
        onBlur={() => setPos(null)}
        onKeyDown={(e) => e.key === "Escape" && setPos(null)}
        className="ml-1 inline-flex size-3.5 shrink-0 cursor-help items-center justify-center rounded-full border border-tinta-3 font-serif text-[9px] leading-none font-semibold text-tinta-3 normal-case italic hover:border-tinta hover:text-tinta focus-visible:border-tinta focus-visible:text-tinta"
      >
        i
      </button>
      {pos && (
        <span
          id={id}
          role="tooltip"
          style={{
            position: "fixed",
            top: pos.y + 6,
            left: Math.min(Math.max(pos.x, 12 + medio), window.innerWidth - 12 - medio),
            maxWidth: 2 * medio,
            transform: "translateX(-50%)",
          }}
          className="pointer-events-none z-50 w-max rounded-md bg-tinta px-2.5 py-1.5 text-xs leading-snug font-normal tracking-normal text-fondo normal-case shadow-lg"
        >
          {texto}
        </span>
      )}
    </span>
  );
}
