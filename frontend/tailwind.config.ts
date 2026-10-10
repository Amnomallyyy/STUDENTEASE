import type { Config } from "tailwindcss";

// Palette and type taken from the team's "Blue Modern Robotics" deck: cream paper, deep navy titles,
// sky and periwinkle blues, a teal, a mustard accent, black outlines, chunky rounded headline type.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // The app is light-only; "class" keeps the interview components' dark: variants from switching on
  // when the operating system is in dark mode.
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        // Outfit for UI text, Fredoka for titles (see index.html for the font import). `serif` is kept
        // as an alias so earlier `font-serif` title usages pick up the display face.
        sans: ['"Outfit"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
        display: ['"Fredoka"', '"Outfit"', "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ['"Fredoka"', '"Outfit"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#f1f6fd",
          100: "#e2eefc",
          200: "#b9d9ff",
          300: "#93ccff",
          400: "#5fb0ef",
          500: "#2d8bba",
          600: "#214184",
          700: "#1b3670",
          800: "#162c5c",
          900: "#0f1e40",
        },
        ink: "#181821",
        cream: "#fbf5f1",
        sky: "#93ccff",
        periwinkle: "#8cb9dd",
        teal: { 500: "#4895aa", 700: "#2a6377" },
        mustard: "#ecb347",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(24, 24, 33, 0.05), 0 10px 28px -14px rgba(33, 65, 132, 0.25)",
        glow: "0 10px 30px -8px rgba(45, 139, 186, 0.45)",
        sticker: "4px 4px 0 0 #181821",
        "sticker-sm": "3px 3px 0 0 #181821",
        "sticker-sky": "4px 4px 0 0 #93ccff",
      },
    },
  },
  plugins: [],
} satisfies Config;
