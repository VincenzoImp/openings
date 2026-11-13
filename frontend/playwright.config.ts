import { defineConfig } from "@playwright/test";

// The global setup seeds one synthetic workspace; every worker serves its own
// copy and restores it before each test (tests/server.ts, tests/fixtures.ts),
// so tests run in parallel and in any order. In CI a retried test that then
// passes still fails the run: a flaky test is reported, never hidden.
const CI = !!process.env.CI;
const PERFORMANCE = "performance.spec.ts";
const SCREENSHOTS = "screenshots.spec.ts";
const desktop = { width: 1440, height: 1000 };
const mobile = { width: 390, height: 844 };

export default defineConfig({
  testDir: "./tests",
  testMatch: "*.spec.ts",
  fullyParallel: true,
  workers: CI ? 4 : undefined,
  retries: CI ? 1 : 0,
  failOnFlakyTests: CI,
  timeout: 30000,
  reporter: "list",
  globalSetup: "./tests/server.ts",
  use: { trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      testIgnore: [PERFORMANCE, SCREENSHOTS],
      use: { browserName: "chromium", viewport: desktop },
    },
    {
      name: "chromium-mobile",
      testIgnore: [PERFORMANCE, SCREENSHOTS],
      use: { browserName: "chromium", viewport: mobile },
    },
    {
      name: "webkit",
      testIgnore: [PERFORMANCE, SCREENSHOTS],
      use: { browserName: "webkit", viewport: desktop },
    },
    {
      name: "webkit-mobile",
      testIgnore: [PERFORMANCE, SCREENSHOTS],
      use: { browserName: "webkit", viewport: mobile },
    },
    // The performance budget starts its own large workspace (25,000 jobs).
    {
      name: "chromium-performance",
      testMatch: PERFORMANCE,
      timeout: 300000,
      use: { browserName: "chromium", viewport: desktop },
    },
    // Images of every screen for visual review (`npm run screenshots`).
    {
      name: "screenshots",
      testMatch: SCREENSHOTS,
      use: { browserName: "chromium" },
    },
  ],
});
