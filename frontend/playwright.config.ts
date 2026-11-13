import { randomUUID } from "node:crypto";
import { createServer } from "node:net";
import { defineConfig } from "@playwright/test";

// One run, one server: OPENINGS_E2E_PORT selects the port (default: a free one
// chosen here) and OPENINGS_E2E_TOKEN identifies the server this run starts.
// Both are exported so the server, the global setup and the workers share them.
function freePort() {
  return new Promise<number>((resolve, reject) => {
    const probe = createServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address() as { port: number };
      probe.close(() => resolve(port));
    });
  });
}
const port = Number(
  (process.env.OPENINGS_E2E_PORT ||= String(await freePort())),
);
if (!Number.isInteger(port) || port < 1 || port > 65535)
  throw Error(
    `OPENINGS_E2E_PORT must be a TCP port, got "${process.env.OPENINGS_E2E_PORT}".`,
  );
process.env.OPENINGS_E2E_TOKEN ||= randomUUID();
const baseURL = `http://127.0.0.1:${port}`;
const PERFORMANCE = "performance.spec.ts";

export default defineConfig({
  testDir: "./tests",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  reporter: "list",
  globalSetup: "./tests/e2e-server.ts",
  use: { baseURL, trace: "retain-on-failure" },
  webServer: {
    command: "uv run --project .. python ../backend/tests/dashboard_server.py",
    url: `${baseURL}/health`,
    reuseExistingServer: false,
    timeout: 30000,
  },
  projects: [
    {
      name: "chromium",
      testIgnore: PERFORMANCE,
      use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "chromium-mobile",
      testIgnore: PERFORMANCE,
      use: { browserName: "chromium", viewport: { width: 390, height: 844 } },
    },
    {
      name: "webkit",
      testIgnore: PERFORMANCE,
      use: { browserName: "webkit", viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "webkit-mobile",
      testIgnore: PERFORMANCE,
      use: { browserName: "webkit", viewport: { width: 390, height: 844 } },
    },
    // The performance budget starts its own large workspace (25,000 jobs).
    {
      name: "chromium-performance",
      testMatch: PERFORMANCE,
      timeout: 300000,
      use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } },
    },
  ],
});
