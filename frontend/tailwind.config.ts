// =============================================================
// FILE: frontend/tailwind.config.ts
// PURPOSE: Tailwind CSS configuration.
//          Points content at all app/ and components/ files so
//          Tailwind can tree-shake unused classes in production.
// =============================================================

import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0f4ff",
          100: "#dbe4ff",
          500: "#4f72e8",
          600: "#3b5bdb",
          700: "#2f4ac2",
        },
      },
    },
  },
  plugins: [],
};

export default config;
