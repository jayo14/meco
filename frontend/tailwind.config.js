/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090d16",
        surface: "#0f1523",
        "surface-card": "#131b2e",
        "surface-border": "#1e293b",
        primary: {
          DEFAULT: "#00f0ff",
          hover: "#00d4e3",
          dim: "rgba(0, 240, 255, 0.12)",
        },
        success: {
          DEFAULT: "#10b981",
          dim: "rgba(16, 185, 129, 0.15)",
        },
        warning: {
          DEFAULT: "#f59e0b",
          dim: "rgba(245, 158, 11, 0.15)",
        },
        danger: {
          DEFAULT: "#ef4444",
          dim: "rgba(239, 68, 68, 0.15)",
        },
        accent: {
          DEFAULT: "#8b5cf6",
          dim: "rgba(139, 92, 246, 0.15)",
        },
        muted: "#94a3b8",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
