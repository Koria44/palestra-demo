/**
 * Configuracion de Tailwind CSS para PALESTRA.
 * Se desactiva preflight (corePlugins.preflight = false) para convivir sin conflictos
 * con el reset y componentes interactivos de Bootstrap 5 (Seccion 3 y 8).
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.py",
    "./static/js/**/*.js",
  ],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        palestra: {
          "primario-900": "var(--color-primary-900)",
          "primario-700": "var(--color-primary-700)",
          "primario-500": "var(--color-primary-500)",
          "acento-500": "var(--color-accent-500)",
          "alerta-500": "var(--color-highlight-500)",
          "peligro-500": "var(--color-danger-500)",
          superficie: "var(--color-surface)",
          fondo: "var(--color-background)",
          borde: "var(--color-border)",
          texto: "var(--color-text)",
          "texto-secundario": "var(--color-text-muted)",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      spacing: {
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        6: "24px",
        8: "32px",
        12: "48px",
      },
    },
  },
  plugins: [],
};
