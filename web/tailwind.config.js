export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        teamsync: {
          primary: "#2563eb",
          secondary: "#14b8a6",
          accent: "#f59e0b",
          neutral: "#111827",
          "base-100": "#f8fafc",
          info: "#0ea5e9",
          success: "#16a34a",
          warning: "#f97316",
          error: "#dc2626",
        },
      },
      "night",
    ],
  },
};
