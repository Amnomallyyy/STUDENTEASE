import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d9eaff",
          200: "#bcd9ff",
          300: "#8ec0ff",
          400: "#599dff",
          500: "#3277fb",
          600: "#1c57f0",
          700: "#1543dd",
          800: "#1737b3",
          900: "#19338d",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
