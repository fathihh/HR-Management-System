/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // keep your existing primary scale for backwards-compat
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        // AUREON 360 palette
        ink: {
          900: "#0B1220",
          800: "#0F1A2F",
          700: "#13213D",
          600: "#182A50",
        },
        aurora: {
          300: "#9CD0FF",
          400: "#66B5FF",
          500: "#3BA3FF",
        },
      },
      boxShadow: {
        glass: "0 12px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)",
      },
      backdropBlur: {
        xs: "2px",
      },
      borderRadius: {
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};
