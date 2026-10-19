// Conversión Config ↔ valores del formulario y lectura de los errores 422 de la API.

import { CAMPOS, CAMPO_POR_RUTA, type Campo } from "./campos";
import type { Config, ErrorPydantic } from "./tipos";

export type Valores = Record<string, string | boolean>;

/** Sección de la Config → sección del formulario (empresa y ubicación comparten panel). */
export const SECCION_FORM: Record<string, string> = {
  empresa: "empresa",
  ubicacion: "empresa",
  consumo: "consumo",
  tarifa: "tarifa",
  sistema_fv: "fv",
  bateria: "bateria",
  finanzas: "finanzas",
};

function leer(cfg: Config, ruta: string): unknown {
  const [s, k] = ruta.split(".");
  return cfg[s]?.[k];
}

const escalar = (v: number, f: number) => Number((v * f).toPrecision(12));

export function aValores(cfg: Config): Valores {
  const out: Valores = {};
  for (const c of CAMPOS) {
    const v = leer(cfg, c.ruta);
    if (c.tipo === "booleano") out[c.ruta] = Boolean(v);
    else if (v == null) out[c.ruta] = "";
    else if (typeof v === "number") out[c.ruta] = String(escalar(v, c.factor ?? 1)).replace(".", ",");
    else out[c.ruta] = String(v);
  }
  return out;
}

/** "6,2442" → 6.2442; "1.500,5" → 1500.5; "6.2442" → 6.2442. NaN si no es un número. */
export function aNumero(s: string): number {
  const t = s.trim().replace(/\s/g, "");
  if (t === "") return NaN;
  const normal = t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t;
  return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(normal) ? Number(normal) : NaN;
}

function valorApi(c: Campo, v: string | boolean): unknown {
  if (c.tipo === "booleano") return Boolean(v);
  const s = String(v);
  if (c.tipo === "texto") return s;
  if (c.tipo === "opcion") return c.ruta === "tarifa.nivel_tension" ? Number(s) : s;
  if (s.trim() === "") return null; // obligatorio vacío → pydantic responde "missing"/tipo
  const n = aNumero(s);
  if (Number.isNaN(n)) return s; // que pydantic diga que no es un número
  const f = c.factor ?? 1;
  return f === 1 ? n : Number((n / f).toPrecision(12));
}

/** Config para la API: la base (de /api/config-ejemplo) con los valores del formulario encima. */
export function aConfig(base: Config, valores: Valores): Config {
  const cfg: Config = structuredClone(base);
  cfg.consumo = { ...cfg.consumo, modo: "sintetico", archivo: null };
  for (const c of CAMPOS) {
    const [s, k] = c.ruta.split(".");
    cfg[s] = { ...cfg[s], [k]: valorApi(c, valores[c.ruta]) };
  }
  return cfg;
}

// ---------- errores 422 ----------

export interface Errores {
  campo: Record<string, string>; // ruta → mensaje
  seccion: Record<string, string[]>; // id de sección del formulario → mensajes
  general: string[];
}

export const SIN_ERRORES: Errores = { campo: {}, seccion: {}, general: [] };

function limite(v: unknown, c?: Campo): string {
  return typeof v === "number"
    ? new Intl.NumberFormat("es-CO", { maximumFractionDigits: 4 }).format(escalar(v, c?.factor ?? 1))
    : String(v);
}

function mensaje(e: ErrorPydantic, c?: Campo): string {
  const ctx = e.ctx ?? {};
  switch (e.type) {
    case "greater_than":
      return `Debe ser mayor que ${limite(ctx.gt, c)}`;
    case "greater_than_equal":
      return `Debe ser mayor o igual a ${limite(ctx.ge, c)}`;
    case "less_than":
      return `Debe ser menor que ${limite(ctx.lt, c)}`;
    case "less_than_equal":
      return `Debe ser menor o igual a ${limite(ctx.le, c)}`;
    case "float_parsing":
    case "float_type":
      return "Ingresa un número";
    case "int_parsing":
    case "int_type":
    case "int_from_float":
      return "Ingresa un número entero";
    case "missing":
      return "Campo obligatorio";
    case "literal_error":
      return "Opción no válida";
    case "value_error":
      return e.msg.replace(/^Value error, /, "");
    default:
      return e.msg;
  }
}

/** Reparte el `detail` de un 422 entre campos, secciones y errores generales. */
export function leerErrores(detail: unknown): Errores {
  const out: Errores = { campo: {}, seccion: {}, general: [] };
  if (!Array.isArray(detail)) {
    out.general.push(typeof detail === "string" ? detail : "La configuración no es válida");
    return out;
  }
  for (const e of detail as ErrorPydantic[]) {
    const loc = e.loc[0] === "body" ? e.loc.slice(1) : e.loc;
    const ruta = loc.slice(0, 2).join(".");
    const campo = CAMPO_POR_RUTA.get(ruta);
    if (campo) {
      out.campo[ruta] ??= mensaje(e, campo);
      continue;
    }
    // Validadores de modelo (p. ej. consumo): el mensaje nombra el campo, "consumo.consumo_mensual_kwh"
    const nombrado = [...CAMPO_POR_RUTA.keys()].find((r) => e.msg.includes(r));
    if (nombrado) {
      out.campo[nombrado] ??= / requiere /.test(e.msg) ? "Campo obligatorio" : mensaje(e);
      continue;
    }
    const sec = SECCION_FORM[String(loc[0])];
    if (sec) (out.seccion[sec] ??= []).push(mensaje(e));
    else out.general.push(mensaje(e));
  }
  return out;
}

export function hayErrores(e: Errores): boolean {
  return (
    Object.keys(e.campo).length > 0 || Object.keys(e.seccion).length > 0 || e.general.length > 0
  );
}
