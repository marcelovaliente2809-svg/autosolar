// Colores fijos de las series: los mismos en todas las gráficas (y en app/globals.css).
// Los neutros (base, alterno, grilla, eje, tinta) son variables CSS: cambian con el modo oscuro.
export const COLOR = {
  autoconsumo: "#2a6fdb", // azul
  autoconsumoBat: "#8db4ee", // azul claro: parte del autoconsumo que sale de la batería
  exc1: "#e5a50a", // ámbar
  exc2: "#2e9d5a", // verde
  importacion: "#8b9099", // gris
  fv: "#f2711c", // naranja: generación FV
  base: "var(--color-tinta)", // escenario base (tinta)
  alterno: "var(--color-tinta-3)", // escenario comparado (tinta tenue)
  grilla: "var(--color-grilla)",
  eje: "var(--color-tinta-3)",
  tinta: "var(--color-tinta)",
  panel: "var(--color-panel)", // borde de puntos sobre la gráfica
} as const;

/** Colores de los tamaños de batería mostrados en la gráfica de VPN (de menor a mayor). */
export const BATERIAS = ["var(--color-bat-1)", "var(--color-bat-2)", "var(--color-bat-3)"] as const;
