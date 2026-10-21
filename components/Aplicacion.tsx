"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Formulario from "@/components/Formulario";
import BalanceMensual from "@/components/graficas/BalanceMensual";
import DiaTipico from "@/components/graficas/DiaTipico";
import FlujoAcumulado from "@/components/graficas/FlujoAcumulado";
import LcoeValores from "@/components/graficas/LcoeValores";
import VpnKwp from "@/components/graficas/VpnKwp";
import { ProveedorTips } from "@/components/Info";
import { Comparacion, Recomendacion } from "@/components/Resumen";
import Sensibilidad from "@/components/Sensibilidad";
import {
  aConfig,
  aValores,
  hayErrores,
  leerErrores,
  SIN_ERRORES,
  type Errores,
  type Valores,
} from "@/lib/formulario";
import type { Tips } from "@/lib/glosario";
import type { Config, ResultadoOptimizar, ResultadoSensibilidad } from "@/lib/tipos";

type Pestana = "resultados" | "sensibilidad" | "metodologia" | "glosario";

const PESTANAS: { id: Pestana; titulo: string }[] = [
  { id: "resultados", titulo: "Resultados" },
  { id: "sensibilidad", titulo: "Sensibilidad" },
  { id: "metodologia", titulo: "Metodología" },
  { id: "glosario", titulo: "Glosario" },
];

interface Corrida {
  resultado: ResultadoOptimizar;
  config: Config; // la config con que se corrió (para el tope de techo)
  valores: Valores;
}

interface CorridaSens {
  datos: ResultadoSensibilidad;
  valores: Valores;
  nombre: string;
}

/** Segundos transcurridos mientras `activo` es true. */
function useSegundos(activo: boolean): number {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!activo) return;
    setS(0);
    const t = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [activo]);
  return s;
}

function techoKwp(cfg: Config): number {
  const fv = cfg.sistema_fv as { kwp_max: number; m2_por_kwp: number };
  const area = (cfg.ubicacion as { area_techo_m2: number }).area_techo_m2;
  return Math.min(fv.kwp_max, area / fv.m2_por_kwp);
}

export default function Aplicacion({
  tips,
  glosario,
  metodologia,
}: {
  tips: Tips;
  glosario: ReactNode;
  metodologia: ReactNode;
}) {
  const [base, setBase] = useState<Config | null>(null);
  const [valores, setValores] = useState<Valores>({});
  const [errores, setErrores] = useState<Errores>(SIN_ERRORES);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [sens, setSens] = useState<CorridaSens | null>(null);
  const [cargandoSens, setCargandoSens] = useState(false);
  const [errorSens, setErrorSens] = useState<string[]>([]);
  const [corrida, setCorrida] = useState<Corrida | null>(null);
  const [pestana, setPestana] = useState<Pestana>("resultados");
  const control = useRef<AbortController | null>(null);
  const refResultados = useRef<HTMLElement>(null);

  useEffect(() => {
    fetch("/api/config-ejemplo")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((cfg: Config) => {
        setBase(cfg);
        setValores(aValores(cfg));
      })
      .catch((e) =>
        setErrorCarga(`No se pudo leer /api/config-ejemplo (${e.message}). ¿Está corriendo la API en el puerto 8000?`),
      );
  }, []);

  const segundos = useSegundos(cargando);
  const segundosSens = useSegundos(cargandoSens);

  function cambiar(ruta: string, valor: string | boolean) {
    setValores((v) => ({ ...v, [ruta]: valor }));
    if (errores.campo[ruta]) {
      setErrores((e) => {
        const campo = { ...e.campo };
        delete campo[ruta];
        return { ...e, campo };
      });
    }
  }

  async function optimizar() {
    if (!base || cargando) return;
    const cfg = aConfig(base, valores);
    control.current = new AbortController();
    setCargando(true);
    setErrores(SIN_ERRORES);
    try {
      const r = await fetch("/api/optimizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
        signal: control.current.signal,
      });
      const cuerpo = await r.json().catch(() => null);
      if (r.status === 422) {
        setErrores(leerErrores(cuerpo?.detail));
        return;
      }
      if (!r.ok) throw new Error(cuerpo?.detail ?? `HTTP ${r.status}`);
      setCorrida({ resultado: cuerpo as ResultadoOptimizar, config: cfg, valores });
      setPestana("resultados");
      // en móvil el formulario va encima: llevar la vista a los resultados
      if (window.matchMedia("(max-width: 1023px)").matches) {
        refResultados.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setErrores({ ...SIN_ERRORES, general: [`Error al optimizar: ${(e as Error).message}`] });
      }
    } finally {
      setCargando(false);
    }
  }

  async function calcularSensibilidad() {
    if (!base || cargandoSens) return;
    const cfg = aConfig(base, valores);
    setCargandoSens(true);
    setErrorSens([]);
    try {
      const r = await fetch("/api/sensibilidad", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      const cuerpo = await r.json().catch(() => null);
      if (r.status === 422) {
        const e = leerErrores(cuerpo?.detail);
        setErrores(e);
        setErrorSens(
          e.general.length
            ? e.general
            : [typeof cuerpo?.detail === "string" ? cuerpo.detail : "Revisa los campos marcados del formulario."],
        );
        return;
      }
      if (!r.ok) throw new Error(cuerpo?.detail ?? `HTTP ${r.status}`);
      setSens({ datos: cuerpo as ResultadoSensibilidad, valores, nombre: String(cfg.empresa.nombre) });
    } catch (e) {
      setErrorSens([`Error al calcular la sensibilidad: ${(e as Error).message}`]);
    } finally {
      setCargandoSens(false);
    }
  }

  const sensDesactualizada = sens != null && JSON.stringify(sens.valores) !== JSON.stringify(valores);
  const desactualizada =
    corrida != null && JSON.stringify(corrida.valores) !== JSON.stringify(valores);

  // ¿El formulario sigue con los valores de la config de ejemplo?
  const valoresEjemplo = useMemo(() => (base ? aValores(base) : null), [base]);
  const esEjemplo =
    valoresEjemplo != null && Object.keys(valoresEjemplo).every((k) => valoresEjemplo[k] === valores[k]);

  return (
    <ProveedorTips value={tips}>
      <div className="min-h-dvh lg:flex lg:h-dvh lg:flex-col">
        {/* ---------- encabezado ---------- */}
        <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5 border-b border-borde bg-panel px-4 py-3 sm:px-5">
          <div className="min-w-0">
            <p className="flex items-baseline gap-2">
              <span className="font-mono text-[15px] font-medium tracking-tight text-tinta">autosolar</span>
              <span className="hidden text-xs text-tinta-3 sm:inline">CREG 174 de 2021</span>
            </p>
            <p className="text-xs leading-snug text-tinta-2">
              Dimensionamiento y evaluación de autogeneración solar con baterías para industria en Colombia
            </p>
          </div>
          <Estado
            cargada={base != null}
            error={errorCarga != null}
            ejemplo={esEjemplo}
            onFuentes={() => setPestana("metodologia")}
          />
        </header>

        <div className="lg:flex lg:min-h-0 lg:flex-1">
          {/* ---------- panel lateral ---------- */}
          <aside
            aria-label="Datos de la empresa"
            className="flex flex-col border-b border-borde bg-panel lg:w-[300px] lg:shrink-0 lg:border-r lg:border-b-0"
          >
            <div className="lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
              {errorCarga && (
                <p className="m-4 rounded-md bg-error-fondo p-3 text-sm text-error">{errorCarga}</p>
              )}
              {!base && !errorCarga && <p className="p-4 text-sm text-tinta-3">Cargando configuración de ejemplo…</p>}
              {base && (
                <Formulario
                  valores={valores}
                  errores={errores}
                  deshabilitado={cargando || cargandoSens}
                  onCambio={cambiar}
                />
              )}
            </div>

            {/* fijo abajo del panel (en móvil, pegado al borde inferior mientras se ve el formulario) */}
            <div className="sticky bottom-0 border-t border-borde bg-panel/95 p-3 backdrop-blur">
              {errores.general.map((m) => (
                <p key={m} className="mb-2 rounded-md bg-error-fondo px-3 py-2 text-xs text-error">
                  {m}
                </p>
              ))}
              {hayErrores(errores) && errores.general.length === 0 && (
                <p className="mb-2 text-xs text-error">Revisa los campos marcados.</p>
              )}
              <Boton onClick={optimizar} deshabilitado={!base || cargando || cargandoSens} ancho>
                {cargando ? (
                  <>
                    <Giro />
                    Optimizando… <span className="num font-normal opacity-70">{segundos} s</span>
                  </>
                ) : (
                  "Optimizar"
                )}
              </Boton>
            </div>
          </aside>

          {/* ---------- resultados ---------- */}
          <main ref={refResultados} className="min-w-0 flex-1 scroll-mt-0 lg:overflow-y-auto">
            <nav className="sticky top-0 z-10 flex gap-1 overflow-x-auto border-b border-borde bg-fondo/90 px-3 pt-2.5 backdrop-blur sm:px-5">
              {PESTANAS.map(({ id, titulo }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPestana(id)}
                  aria-current={pestana === id ? "page" : undefined}
                  className={`-mb-px border-b-2 px-2.5 pb-2 text-sm font-medium whitespace-nowrap ${
                    pestana === id ? "border-acento text-tinta" : "border-transparent text-tinta-3 hover:text-tinta-2"
                  }`}
                >
                  {titulo}
                </button>
              ))}
            </nav>

            <div className="mx-auto max-w-[1280px] space-y-4 p-3 sm:p-5">
              {pestana === "glosario" ? (
                glosario
              ) : pestana === "metodologia" ? (
                metodologia
              ) : pestana === "sensibilidad" ? (
                <PanelSensibilidad
                  listo={base != null}
                  sens={sens}
                  cargando={cargandoSens}
                  segundos={segundosSens}
                  errores={errorSens}
                  desactualizada={sensDesactualizada}
                  onCalcular={calcularSensibilidad}
                />
              ) : cargando && !corrida ? (
                <Cargando segundos={segundos} />
              ) : !corrida ? (
                <Vacio
                  titulo="Sin resultados todavía"
                  texto="Ajusta los datos de la empresa en el panel y presiona Optimizar: se barre la grilla de potencia FV y batería y se elige la combinación con mayor VPN."
                />
              ) : (
                <Resultados corrida={corrida} cargando={cargando} desactualizada={desactualizada} />
              )}
            </div>
          </main>
        </div>
      </div>
    </ProveedorTips>
  );
}

function Estado({
  cargada,
  error,
  ejemplo,
  onFuentes,
}: {
  cargada: boolean;
  error: boolean;
  ejemplo: boolean;
  onFuentes: () => void;
}) {
  if (cargada && !error && ejemplo) {
    // los valores de ejemplo tienen fuente: el indicador lleva a la pestaña que las cita
    return (
      <p role="status" className="text-xs">
        <button
          type="button"
          onClick={onFuentes}
          className="flex items-center gap-1.5 rounded-full border border-borde px-2.5 py-0.5 hover:border-acento/60 focus-visible:ring-2 focus-visible:ring-acento/40 focus-visible:outline-none"
        >
          <span className="size-1.5 rounded-full bg-tinta-3" aria-hidden />
          <span className="font-medium text-tinta">Datos de ejemplo</span>
          <span className="text-tinta-3">
            · fuentes en <span className="text-acento underline underline-offset-2">Metodología</span>
          </span>
        </button>
      </p>
    );
  }
  const [texto, detalle, punto] = error
    ? ["Sin conexión", "la API no respondió", "bg-error"]
    : !cargada
      ? ["Cargando…", "", "bg-tinta-3"]
      : ["Datos propios", "editados en el panel", "bg-acento"];
  return (
    <p className="flex items-center gap-1.5 rounded-full border border-borde px-2.5 py-0.5 text-xs" role="status">
      <span className={`size-1.5 rounded-full ${punto}`} aria-hidden />
      <span className="font-medium text-tinta">{texto}</span>
      {detalle && <span className="hidden text-tinta-3 sm:inline">· {detalle}</span>}
    </p>
  );
}

function Boton({
  onClick,
  deshabilitado,
  ancho = false,
  children,
}: {
  onClick: () => void;
  deshabilitado: boolean;
  ancho?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={deshabilitado}
      className={`flex items-center justify-center gap-2 rounded-md bg-acento px-4 py-2 text-sm font-semibold text-sobre-acento transition hover:brightness-105 focus-visible:ring-2 focus-visible:ring-acento/40 focus-visible:ring-offset-2 focus-visible:ring-offset-panel focus-visible:outline-none active:brightness-95 disabled:cursor-not-allowed disabled:opacity-60 ${
        ancho ? "w-full" : ""
      }`}
    >
      {children}
    </button>
  );
}

function Giro() {
  return <span className="size-4 animate-spin rounded-full border-2 border-sobre-acento/30 border-t-sobre-acento" />;
}

function Aviso({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-acento/40 bg-acento-suave px-3 py-2 text-xs text-tinta-2">{children}</p>
  );
}

function PanelSensibilidad({
  listo,
  sens,
  cargando,
  segundos,
  errores,
  desactualizada,
  onCalcular,
}: {
  listo: boolean;
  sens: CorridaSens | null;
  cargando: boolean;
  segundos: number;
  errores: string[];
  desactualizada: boolean;
  onCalcular: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Boton onClick={onCalcular} deshabilitado={!listo || cargando}>
          {cargando ? (
            <>
              <Giro />
              Calculando… <span className="num font-normal opacity-70">{segundos} s</span>
            </>
          ) : (
            "Calcular sensibilidad"
          )}
        </Boton>
        <p className="min-w-0 flex-1 basis-60 text-xs text-tinta-3">
          Usa los parámetros actuales del formulario. Tarda unos 7 s: tornado ±20 %, 5 escenarios y breakeven de batería.
        </p>
      </div>

      {errores.map((m) => (
        <p key={m} className="rounded-md bg-error-fondo px-3 py-2 text-sm text-error">
          {m}
        </p>
      ))}
      {desactualizada && !cargando && (
        <Aviso>
          Cambiaste parámetros desde el último cálculo: estos resultados no los reflejan hasta que vuelvas a calcular.
        </Aviso>
      )}

      {cargando && !sens ? (
        <div className="space-y-4" aria-busy>
          <div className="h-36 animate-pulse rounded-lg bg-borde/60" />
          <div className="h-72 animate-pulse rounded-lg bg-borde/50" />
          <div className="h-52 animate-pulse rounded-lg bg-borde/40" />
        </div>
      ) : !sens ? (
        <Vacio
          titulo="Sin sensibilidad todavía"
          texto="Presiona Calcular sensibilidad para ver el tornado de variables, los escenarios regulatorios y el breakeven de la batería."
        />
      ) : (
        <div className={`space-y-4 transition-opacity ${cargando ? "pointer-events-none opacity-50" : ""}`}>
          <h2 className="text-xs font-medium text-tinta-3">Sensibilidad · {sens.nombre}</h2>
          <Sensibilidad datos={sens.datos} />
        </div>
      )}
    </div>
  );
}

function Resultados({
  corrida,
  cargando,
  desactualizada,
}: {
  corrida: Corrida;
  cargando: boolean;
  desactualizada: boolean;
}) {
  const { resultado: r, config } = corrida;
  return (
    <div className={`space-y-4 transition-opacity ${cargando ? "pointer-events-none opacity-50" : ""}`}>
      {(desactualizada || cargando) && (
        <Aviso>
          {cargando
            ? "Recalculando con los nuevos parámetros…"
            : "Cambiaste parámetros desde la última optimización: los resultados no los reflejan hasta que vuelvas a optimizar."}
        </Aviso>
      )}
      <Recomendacion mejor={r.mejor} empresa={String(config.empresa.nombre)} />
      <Comparacion sinBat={r.mejor_sin_bateria} conBat={r.mejor_con_bateria} mejor={r.mejor} />
      <div className="grid gap-4 xl:grid-cols-2">
        <VpnKwp tabla={r.tabla} mejor={r.mejor} techoKwp={techoKwp(config)} />
        <BalanceMensual datos={r.series.balance_mensual} />
        <DiaTipico habil={r.series.dia_habil} domingo={r.series.dia_domingo} />
        <FlujoAcumulado datos={r.series.flujo_acumulado} />
        <LcoeValores valores={r.series.lcoe_vs_valores} kwp={r.mejor.kwp} />
      </div>
    </div>
  );
}

function Vacio({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div className="rounded-lg border border-dashed border-borde px-5 py-14 text-center">
      <p className="text-base font-semibold">{titulo}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-tinta-3">{texto}</p>
    </div>
  );
}

function Cargando({ segundos }: { segundos: number }) {
  return (
    <div className="space-y-4" aria-busy>
      <p className="text-sm text-tinta-2">
        Barriendo la grilla de potencia FV × batería… <span className="num text-tinta-3">{segundos} s</span>
      </p>
      <div className="h-[180px] animate-pulse rounded-lg bg-borde/60" />
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="h-80 animate-pulse rounded-lg bg-borde/50" />
        <div className="h-80 animate-pulse rounded-lg bg-borde/40" />
      </div>
    </div>
  );
}
