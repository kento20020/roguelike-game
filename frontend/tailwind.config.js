/** @type {import('tailwindcss').Config} */
// カジノ・ノワールのトークンは CSS 変数（src/index.css :root）が正本。
// ここでは Tailwind から var(--x) を参照できるよう色名を割り当てる。
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        paper2: "var(--paper2)",
        paper3: "var(--paper3)",
        felt: "var(--felt)",
        ink: "var(--ink)",
        ink2: "var(--ink2)",
        ink3: "var(--ink3)",
        rule: "var(--rule)",
        rule2: "var(--rule2)",
        accent: "var(--accent)",
        accent2: "var(--accent2)",
        brass: "var(--brass)",
        danger: "var(--danger)",
        moss: "var(--moss)",
      },
      fontFamily: {
        serif: ["Instrument Serif", "Noto Serif JP", "serif"],
        sans: ["Geist", "Noto Sans JP", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
