import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
const version = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8")).version;
export default defineConfig({
  plugins: [react()],
  define: { __NETWORK_VERSION__: JSON.stringify(version) },
  base: "./",
  build: {
    outDir: "../src/brainfc/network/web/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 5000,
  },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
