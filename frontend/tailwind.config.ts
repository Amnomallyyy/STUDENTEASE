import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // The app is light-only; "class" keeps the interview components' dark: variants from switching on
  // when the operating system is in dark mode.
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        // Geist for UI text, EB Garamond for page titles (see index.html for the font import).
        sans: ['"Geist"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
        serif: ['"EB Garamond"', "ui-serif", "Georgia", "serif"],
      },
      colors: {
        brand: {
          50: "#eef5ff",
          100: "#dbe9fe",
          200: "#bfd8fd",
          300: "#93bdfb",
          400: "#5f9bf5",
          500: "#2f7deb",
          600: "#1d5fe6",
          700: "#1c45d8",
          800: "#1b39ad",
          900: "#1b3487",
        },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15, 23, 42, 0.04), 0 12px 32px -12px rgba(30, 64, 175, 0.18)",
        glow: "0 10px 30px -8px rgba(47, 125, 235, 0.45)",
      },
    },
  },
  plugins: [],
} satisfies Config;
