// Números en formato es-CO (miles con punto, decimales con coma). Montos en millones de COP.

const cache = new Map<string, Intl.NumberFormat>();

function nf(min: number, max: number): Intl.NumberFormat {
  const clave = `${min}-${max}`;
  let f = cache.get(clave);
  if (!f) {
    f = new Intl.NumberFormat("es-CO", { minimumFractionDigits: min, maximumFractionDigits: max });
    cache.set(clave, f);
  }
  return f;
}

export const SIN_DATO = "—";

export function num(v: number | null | undefined, decimales = 0): string {
  if (v == null || !Number.isFinite(v)) return SIN_DATO;
  return nf(decimales, decimales).format(v);
}

/** COP → millones de COP, p. ej. 1.696.011.297 → "1.696" */
export function mcop(v: number | null | undefined, decimales = 0): string {
  return v == null ? SIN_DATO : num(v / 1e6, decimales);
}

/** fracción → porcentaje, p. ej. 0,3415 → "34,1 %" */
export function pct(v: number | null | undefined, decimales = 1): string {
  return v == null ? SIN_DATO : `${num(v * 100, decimales)} %`;
}

export const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
