import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// ui.html is the design system gallery: built so the browser tests can open
// it, never linked from or served by the dashboard. The image builds the
// dashboard alone (`npm run build -- --mode dashboard`).
const pages = (mode: string): Record<string, string> =>
  mode === "dashboard"
    ? { index: "index.html" }
    : { index: "index.html", ui: "ui.html" };
// The design system ships as two chunks instead of one per module: what the
// first screen draws, and the dialogs, forms and panes the other screens add.
// Fewer, larger chunks compress better. The barrel (ui/index.ts) stays out,
// or it would pull every primitive into the first chunk.
const LATER =
  /\/src\/ui\/(Dialog|ActionSheet|ReadEdit|CodeView|CodeBlock|Table|Choice|Disclosure|Field|Tabs|Split)\./;
const FIRST = /\/src\/ui\/(?!index\.)/;

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
          id.includes("/gallery/") || !id.includes("/src/")
            ? undefined
            : id.endsWith(".css")
              ? "styles"
              : LATER.test(id)
                ? "ui-later"
                : FIRST.test(id)
                  ? "ui"
                  : undefined,
      },
    },
  },
}));
