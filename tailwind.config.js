/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0f14",
          900: "#0f141a",
          800: "#161c24",
          700: "#1f2731",
          600: "#2a333f",
          500: "#3a4554",
          400: "#586477",
          300: "#8392a4",
          200: "#b7c1cc",
          100: "#dde3ea",
        },
      },
    },
  },
  plugins: [],
};