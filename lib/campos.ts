// Campos del formulario: ruta en la Config del motor (src/autosolar/config.py), unidad y escala.
// `factor` convierte del valor de la API al que se muestra: fracción → % (100), COP → M COP (1e-6).

export type TipoCampo = "numero" | "entero" | "texto" | "booleano" | "opcion";

export interface Campo {
  ruta: string; // "seccion.clave"
  etiqueta: string;
  unidad?: string;
  tipo: TipoCampo;
  factor?: number;
  opcional?: boolean; // vacío → null
  placeholder?: string;
  opciones?: { valor: string; etiqueta: string }[];
  ayuda?: string;
}

export interface Seccion {
  id: string;
  titulo: string;
  campos: Campo[];
}

const PCT = 100;

export const SECCIONES: Seccion[] = [
  {
    id: "empresa",
    titulo: "Empresa y ubicación",
    campos: [
      { ruta: "empresa.nombre", etiqueta: "Nombre", tipo: "texto" },
      {
        ruta: "empresa.declara_renta",
        etiqueta: "Declara renta",
        tipo: "booleano",
        ayuda: "Habilita la deducción de la Ley 1715",
      },
      { ruta: "ubicacion.latitud", etiqueta: "Latitud", unidad: "°", tipo: "numero" },
      { ruta: "ubicacion.longitud", etiqueta: "Longitud", unidad: "°", tipo: "numero" },
      { ruta: "ubicacion.area_techo_m2", etiqueta: "Área de techo", unidad: "m²", tipo: "numero" },
      {
        ruta: "ubicacion.inclinacion_deg",
        etiqueta: "Inclinación",
        unidad: "°",
        tipo: "numero",
        opcional: true,
        placeholder: "auto",
        ayuda: "Vacío: máx(|latitud|, 10°)",
      },
    ],
  },
  {
    id: "consumo",
    titulo: "Consumo",
    campos: [
      {
        ruta: "consumo.consumo_mensual_kwh",
        etiqueta: "Consumo mensual",
        unidad: "kWh/mes",
        tipo: "numero",
      },
      {
        ruta: "consumo.jornada",
        etiqueta: "Jornada",
        tipo: "opcion",
        opciones: [
          { valor: "1_turno", etiqueta: "1 turno" },
          { valor: "2_turnos", etiqueta: "2 turnos" },
          { valor: "continua", etiqueta: "Continua (24 h)" },
        ],
      },
    ],
  },
  {
    id: "tarifa",
    titulo: "Tarifa",
    campos: [
      { ruta: "tarifa.operador_red", etiqueta: "Operador de red", tipo: "texto" },
      {
        ruta: "tarifa.nivel_tension",
        etiqueta: "Nivel de tensión",
        tipo: "opcion",
        opciones: ["1", "2", "3", "4"].map((n) => ({ valor: n, etiqueta: `Nivel ${n}` })),
      },
      { ruta: "tarifa.cu_cop_kwh", etiqueta: "Costo unitario CU", unidad: "COP/kWh", tipo: "numero" },
      {
        ruta: "tarifa.componente_comercializacion_cop_kwh",
        etiqueta: "Comercialización Cv",
        unidad: "COP/kWh",
        tipo: "numero",
      },
      { ruta: "tarifa.g_cop_kwh", etiqueta: "Generación G", unidad: "COP/kWh", tipo: "numero" },
      {
        ruta: "tarifa.escalamiento_anual",
        etiqueta: "Escalamiento",
        unidad: "%/año",
        tipo: "numero",
        factor: PCT,
      },
      {
        ruta: "tarifa.valoracion_exc2",
        etiqueta: "Valoración Exc2",
        tipo: "opcion",
        opciones: [
          { valor: "precio_bolsa", etiqueta: "Precio de bolsa" },
          { valor: "mc", etiqueta: "Mc (CREG 101 072/087)" },
        ],
      },
      {
        ruta: "tarifa.precio_exc2_cop_kwh",
        etiqueta: "Precio Exc2",
        unidad: "COP/kWh",
        tipo: "numero",
      },
      {
        ruta: "tarifa.precio_mc_cop_kwh",
        etiqueta: "Precio Mc",
        unidad: "COP/kWh",
        tipo: "numero",
        opcional: true,
      },
    ],
  },
  {
    id: "fv",
    titulo: "Sistema FV",
    campos: [
      { ruta: "sistema_fv.capex_cop_wp", etiqueta: "CAPEX", unidad: "COP/Wp", tipo: "numero" },
      {
        ruta: "sistema_fv.opex_pct_capex",
        etiqueta: "O&M",
        unidad: "% CAPEX/año",
        tipo: "numero",
        factor: PCT,
      },
      {
        ruta: "sistema_fv.degradacion_anual",
        etiqueta: "Degradación",
        unidad: "%/año",
        tipo: "numero",
        factor: PCT,
      },
      {
        ruta: "sistema_fv.perdidas_sistema",
        etiqueta: "Pérdidas",
        unidad: "%",
        tipo: "numero",
        factor: PCT,
      },
      { ruta: "sistema_fv.kwp_min", etiqueta: "Potencia mínima", unidad: "kWp", tipo: "numero" },
      { ruta: "sistema_fv.kwp_max", etiqueta: "Potencia máxima", unidad: "kWp", tipo: "numero" },
      { ruta: "sistema_fv.paso_kwp", etiqueta: "Paso", unidad: "kWp", tipo: "numero" },
      {
        ruta: "sistema_fv.m2_por_kwp",
        etiqueta: "Área por kWp",
        unidad: "m²/kWp",
        tipo: "numero",
      },
    ],
  },
  {
    id: "bateria",
    titulo: "Batería",
    campos: [
      { ruta: "bateria.capex_cop_kwh", etiqueta: "CAPEX", unidad: "COP/kWh", tipo: "numero" },
      {
        ruta: "bateria.eficiencia_ciclo",
        etiqueta: "Eficiencia de ciclo",
        unidad: "%",
        tipo: "numero",
        factor: PCT,
      },
      { ruta: "bateria.dod", etiqueta: "Profundidad de descarga", unidad: "%", tipo: "numero", factor: PCT },
      { ruta: "bateria.c_rate", etiqueta: "C-rate", unidad: "1/h", tipo: "numero" },
      { ruta: "bateria.vida_ciclos", etiqueta: "Vida en ciclos", unidad: "ciclos", tipo: "entero" },
      {
        ruta: "bateria.vida_calendario_anios",
        etiqueta: "Vida calendario",
        unidad: "años",
        tipo: "entero",
      },
      { ruta: "bateria.kwh_min", etiqueta: "Capacidad mínima", unidad: "kWh", tipo: "numero" },
      { ruta: "bateria.kwh_max", etiqueta: "Capacidad máxima", unidad: "kWh", tipo: "numero" },
      { ruta: "bateria.paso_kwh", etiqueta: "Paso", unidad: "kWh", tipo: "numero" },
    ],
  },
  {
    id: "finanzas",
    titulo: "Finanzas",
    campos: [
      { ruta: "finanzas.horizonte_anios", etiqueta: "Horizonte", unidad: "años", tipo: "entero" },
      {
        ruta: "finanzas.tasa_descuento",
        etiqueta: "Tasa de descuento",
        unidad: "%/año",
        tipo: "numero",
        factor: PCT,
      },
      { ruta: "finanzas.tasa_renta", etiqueta: "Tasa de renta", unidad: "%", tipo: "numero", factor: PCT },
      { ruta: "finanzas.inflacion", etiqueta: "Inflación", unidad: "%/año", tipo: "numero", factor: PCT },
      {
        ruta: "finanzas.renta_liquida_anual_cop",
        etiqueta: "Renta líquida anual",
        unidad: "M COP",
        tipo: "numero",
        factor: 1e-6,
        ayuda: "Tope de la deducción: 50 % de este valor por año",
      },
      {
        ruta: "finanzas.anios_depreciacion",
        etiqueta: "Depreciación acelerada",
        unidad: "años",
        tipo: "entero",
      },
      {
        ruta: "finanzas.anios_depreciacion_normal",
        etiqueta: "Depreciación normal",
        unidad: "años",
        tipo: "entero",
      },
      {
        ruta: "finanzas.incentivos_ley1715",
        etiqueta: "Incentivos Ley 1715",
        tipo: "booleano",
        ayuda: "Deducción del 50 % del CAPEX en renta",
      },
    ],
  },
];

export const CAMPOS: Campo[] = SECCIONES.flatMap((s) => s.campos);
export const CAMPO_POR_RUTA = new Map(CAMPOS.map((c) => [c.ruta, c]));
export const SECCION_DE_RUTA = new Map(
  SECCIONES.flatMap((s) => s.campos.map((c) => [c.ruta, s.id] as const)),
);
