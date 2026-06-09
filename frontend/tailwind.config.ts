import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}", "./store/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#060816",
        panel: "#0b1022",
        panel2: "#10172d",
        line: "rgba(148,163,184,0.16)",
        accent: "#4f8cff",
        success: "#22c55e",
        warning: "#f59e0b",
        error: "#ef4444",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(79,140,255,0.18), 0 16px 40px rgba(0,0,0,0.35)",
      },
      backgroundImage: {
        "radial-soft": "radial-gradient(circle at top left, rgba(79,140,255,0.18), transparent 35%), radial-gradient(circle at top right, rgba(34,197,94,0.08), transparent 30%)",
      },
    },
  },
  plugins: [],
};

export default config;
