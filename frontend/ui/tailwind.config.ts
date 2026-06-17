import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0a0e27",
        panel: "rgba(20,30,50,0.40)",
        cyan: { DEFAULT: "#00d9ff", glow: "rgba(0,217,255,0.5)" },
        danger: { DEFAULT: "#e63946", glow: "rgba(230,57,70,0.5)" },
        nominal: { DEFAULT: "#1aba45", glow: "rgba(26,186,69,0.5)" },
        warning: { DEFAULT: "#f4a261", glow: "rgba(244,162,97,0.5)" },
        ink: "#e8eef7",
        muted: "#8a92a8",
        faint: "#5a6a8a",
        hairline: "rgba(255,255,255,0.10)",
      },
      fontFamily: {
        sans: ["Geist", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        ultra: "0.28em",
      },
      keyframes: {
        meshA: {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "50%": { transform: "translate(6%,-4%) scale(1.15)" },
        },
        meshB: {
          "0%,100%": { transform: "translate(0,0) scale(1.05)" },
          "50%": { transform: "translate(-5%,6%) scale(0.92)" },
        },
        meshC: {
          "0%,100%": { transform: "translate(0,0) scale(0.95)" },
          "50%": { transform: "translate(4%,5%) scale(1.12)" },
        },
        pulseRing: {
          "0%": { transform: "scale(0.85)", opacity: "0.85" },
          "70%": { transform: "scale(2.4)", opacity: "0" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        softPulse: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        sweep: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
      animation: {
        meshA: "meshA 26s ease-in-out infinite",
        meshB: "meshB 32s ease-in-out infinite",
        meshC: "meshC 22s ease-in-out infinite",
        pulseRing: "pulseRing 2.4s cubic-bezier(0.4,0,0.6,1) infinite",
        softPulse: "softPulse 2.2s ease-in-out infinite",
        scan: "scan 6s linear infinite",
        sweep: "sweep 8s linear infinite",
      },
      backdropBlur: {
        glass: "14px",
      },
    },
  },
  plugins: [],
} satisfies Config;
