/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Every colour in the product resolves to one of these tokens, and each
        // is a CSS variable so the whole palette can be re-themed (or the brand
        // swapped out) without touching a component.
        bg:        "rgb(var(--bg) / <alpha-value>)",
        surface:   "rgb(var(--surface) / <alpha-value>)",
        elevated:  "rgb(var(--elevated) / <alpha-value>)",
        border:    "rgb(var(--border) / <alpha-value>)",
        "border-strong": "rgb(var(--border-strong) / <alpha-value>)",
        text:      "rgb(var(--text) / <alpha-value>)",
        muted:     "rgb(var(--muted) / <alpha-value>)",
        faint:     "rgb(var(--faint) / <alpha-value>)",
        accent:    "rgb(var(--accent) / <alpha-value>)",
        "accent-dim": "rgb(var(--accent-dim) / <alpha-value>)",
        warning:   "rgb(var(--warning) / <alpha-value>)",
        danger:    "rgb(var(--danger) / <alpha-value>)",
        success:   "rgb(var(--success) / <alpha-value>)",
        info:      "rgb(var(--info) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "display": ["clamp(2.75rem, 7vw, 5.25rem)", { lineHeight: "0.98", letterSpacing: "-0.035em" }],
        "headline": ["clamp(2rem, 4.2vw, 3.25rem)", { lineHeight: "1.05", letterSpacing: "-0.028em" }],
        "title": ["clamp(1.375rem, 2.2vw, 1.875rem)", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
      },
      borderRadius: { card: "14px", pill: "999px" },
      boxShadow: {
        glow: "0 0 0 1px rgb(var(--accent) / 0.25), 0 0 28px -6px rgb(var(--accent) / 0.35)",
        "glow-sm": "0 0 18px -6px rgb(var(--accent) / 0.45)",
        lift: "0 18px 48px -24px rgb(0 0 0 / 0.9)",
      },
      keyframes: {
        "scan-sweep": { "0%": { transform: "translateY(-100%)" }, "100%": { transform: "translateY(400%)" } },
        "pulse-dot":  { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.25" } },
        blink:        { "0%,49%": { opacity: "1" }, "50%,100%": { opacity: "0" } },
        "dash-flow":  { to: { strokeDashoffset: "-24" } },
        "fade-up":    { from: { opacity: "0", transform: "translateY(14px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        "scan-sweep": "scan-sweep 2.6s linear infinite",
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
        blink: "blink 1.05s step-end infinite",
        "dash-flow": "dash-flow 1s linear infinite",
        "fade-up": "fade-up .5s cubic-bezier(.22,1,.36,1) both",
      },
    },
  },
  plugins: [],
};
