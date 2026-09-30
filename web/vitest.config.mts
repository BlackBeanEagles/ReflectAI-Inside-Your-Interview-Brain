import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// Component tests, not a second build pipeline. Next builds the app; this
// only has to render components in jsdom, so it needs the React plugin and
// the same "@/" alias tsconfig uses, and nothing else.
//
// .mts because this project is CommonJS by default, and Vite warns (and
// will eventually fail) on ESM syntax in a config it loads as CJS.
//
// pool "threads": the default forks pool times out waiting for a worker to
// start on Windows here, which fails the whole run before a single test is
// collected.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    pool: "threads",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
