// Tooltips de una línea sacados de content/glosario.md (se leen en build time desde app/page.tsx).

export type Termino = "Exc1" | "Exc2" | "LCOE" | "VPN" | "TIR" | "Payback";
export type Tips = Partial<Record<Termino, string>>;

// término de la 1.ª columna del glosario (antes del paréntesis) → clave de la interfaz
const FILAS: Record<string, Termino> = {
  Exc1: "Exc1",
  Exc2: "Exc2",
  LCOE: "LCOE",
  VPN: "VPN",
  TIR: "TIR",
  "Payback simple": "Payback",
};

const MAX_CARACTERES = 120;

function sinMarkdown(s: string): string {
  return s.replace(/\*\*|\*|`/g, "").replace(/\s+/g, " ").trim();
}

/** Primera frase de la definición; si aún es larga, hasta los dos puntos. */
function unaLinea(definicion: string): string {
  let t = sinMarkdown(definicion);
  const punto = t.search(/\.(\s|$)/);
  if (punto > 0) t = t.slice(0, punto);
  if (t.length > MAX_CARACTERES && t.includes(":")) t = t.slice(0, t.indexOf(":"));
  return t.replace(/[.:]$/, "") + ".";
}

export function extraerTips(markdown: string): Tips {
  const tips: Tips = {};
  for (const linea of markdown.split(/\r?\n/)) {
    if (!linea.startsWith("|")) continue;
    const celdas = linea.split("|").slice(1, -1).map((c) => c.trim());
    if (celdas.length < 2) continue;
    const termino = FILAS[sinMarkdown(celdas[0]).replace(/\s*\(.*$/, "")];
    if (termino && !tips[termino]) tips[termino] = unaLinea(celdas[1]);
  }
  return tips;
}
