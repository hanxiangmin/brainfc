import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
const version = readFileSync(new URL("../src/brainfc/_version.py", import.meta.url), "utf8").match(/__version__ = "([^"]+)"/)![1];
export default defineConfig({
  plugins: [react()],
  define: { "process.env.NODE_ENV": JSON.stringify("production"), __FMRI_VERSION__: JSON.stringify(version) },
  build: {
    outDir: "../src/brainfc/web/static",
    emptyOutDir: false,
    cssCodeSplit: false,
    lib: {
      entry: "src/main.tsx",
      name: "BrainFC",
      formats: ["iife"],
      fileName: () => "app.js",
      cssFileName: "app",
    },
    chunkSizeWarningLimit: 2200,
  },
});
