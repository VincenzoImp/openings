import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// ui.html is the design system gallery: built so the browser tests can open
// it, never linked from or served by the dashboard. The image builds the
// dashboard alone (`npm run build -- --mode dashboard`).
const pages = (mode: string): Record<string, string> =>
  mode === "dashboard"
    ? { index: "index.html" }
    : { index: "index.html", ui: "ui.html" };
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8080", "/mcp": "http://127.0.0.1:8080" },
  },
  // The manifest lists every chunk and its imports for scripts/budget.mjs.
  build: {
    target: "es2022",
    manifest: true,
    rollupOptions: {
      input: pages(mode),
      // Every stylesheet of the dashboard ships as one file with the first
      // screen: together they compress to about two thirds of the size of
      // the per-screen files, and a screen opened later draws without waiting
      // for its styles. The gallery's own stylesheet stays apart.
      output: {
        manualChunks: (id) =>
          id.endsWith(".css") && !id.includes("/gallery/")
            ? "styles"
            : undefined,
      },
    },
  },
}));
