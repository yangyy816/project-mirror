import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "server-only": new URL("./src/test/server-only-shim.ts", import.meta.url)
        .pathname,
    },
  },
  test: {
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
