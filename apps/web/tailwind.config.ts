import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#191717",
        paper: "#fbf8f5",
        rose: "#c7687a",
        plum: "#6d3f55",
      },
    },
  },
  plugins: [],
} satisfies Config;
