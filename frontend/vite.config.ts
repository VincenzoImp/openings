import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8080", "/mcp": "http://127.0.0.1:8080" },
  },
  // The manifest lists every chunk and its imports for scripts/budget.mjs.
  // ui.html is the design system gallery: built so the browser tests can open
  // it, never linked from or served by the dashboard.
  build: {
    target: "es2022",
    manifest: true,
    rollupOptions: { input: { index: "index.html", ui: "ui.html" } },
  },
});
