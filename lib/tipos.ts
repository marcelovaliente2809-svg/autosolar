// Formas de las respuestas de api/index.py (NaN/inf del motor llegan como null).

export type Config = Record<string, Record<string, unknown>>;

export interface Fila {
  kwp: number;
  kwh_bat: number;
  gen_kwh: number;
  autoconsumo_pct: number; // fracción 0–1
  exc1_kwh: number;
  exc2_kwh: number;
  ciclos: number;
  ahorro_anio1: number;
  capex: number;
  vpn: number | null;
  tir: number | null;
  payback: number | null;
  lcoe: number | null;
}

export interface Dia {
  fecha: string;
  hora: number[];
  carga: number[];
  generacion: number[];
  autoconsumo: number[];
  carga_bat: number[];
  descarga_bat: number[];
  exportado: number[];
  importado: number[];
  soc: number[];
}

export interface Series {
  dia_habil: Dia;
  dia_domingo: Dia;
  balance_mensual: {
    mes: number[];
    generacion_kwh: number[];
    consumo_kwh: number[];
    autoconsumo_kwh: number[];
    exc1_kwh: number[];
    exc2_kwh: number[];
    importado_kwh: number[];
  };
  flujo_acumulado: {
    anio: number[];
    base: number[];
    sin_ley1715: number[];
    payback_base: number | null;
    payback_sin_ley1715: number | null;
  };
  lcoe_vs_valores: {
    lcoe: number | null;
    cu: number;
    cu_menos_cv: number;
    g: number;
    precio_exc2: number;
    // solo /api/optimizar: s·CU + (1 − s)·crédito Exc1 del último paso de kWp (null sin paso previo)
    valor_kwh_marginal?: number | null;
  };
}

export interface ResultadoOptimizar {
  mejor: Fila;
  mejor_sin_bateria: Fila | null;
  mejor_con_bateria: Fila | null;
  tabla: Fila[];
  series: Series;
}

export interface ErrorPydantic {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface FilaTornado {
  variable: string;
  vpn_bajo: number; // VPN con la variable −20 %
  vpn_base: number;
  vpn_alto: number; // VPN con la variable +20 %
}

export interface Escenario {
  escenario: string;
  kwp: number;
  kwh_bat: number;
  vpn: number | null;
  tir: number | null;
  payback: number | null;
  autoconsumo_pct: number;
}

export interface ResultadoSensibilidad {
  sistema: { kwp: number; kwh_bat: number };
  tornado: FilaTornado[]; // ya ordenado por amplitud
  escenarios: Escenario[];
  breakeven: {
    capex_actual_cop_kwh: number;
    capex_breakeven_cop_kwh: number | null; // null con estado "siempre" o "nunca"
    estado: "umbral" | "siempre" | "nunca";
  };
}
