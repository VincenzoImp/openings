import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8501",
      "/mcp": "http://127.0.0.1:8501",
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Markdown rendering is the largest dependency and only the job page
        // needs it; keep it in its own chunk so the shell loads faster.
        manualChunks: {
          markdown: ["react-markdown", "remark-gfm"],
          vendor: ["react", "react-dom", "@tanstack/react-query", "@tanstack/react-virtual"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
