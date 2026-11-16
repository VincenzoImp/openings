import { defineConfig } from "@playwright/test";
import type { Options } from "./tests/fixtures";

// The global setup seeds one synthetic workspace; every worker serves its own
// copy and restores it before each test (tests/server.ts, tests/fixtures.ts),
// so tests run in parallel and in any order. In CI a retried test that then
// passes still fails the run: a flaky test is reported, never hidden.
const CI = !!process.env.CI;
const PERFORMANCE = "performance.spec.ts";
const SCREENSHOTS = "screenshots.spec.ts";
const REEL = "reel.spec.ts";
const VIDEO = "video.spec.ts";
const desktop = { width: 1440, height: 1000 };
const mobile = { width: 390, height: 844 };

export default defineConfig<Options>({
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
      testIgnore: [PERFORMANCE, SCREENSHOTS, REEL, VIDEO],
      use: { browserName: "chromium", viewport: desktop },
    },
    {
      name: "chromium-mobile",
      testIgnore: [PERFORMANCE, SCREENSHOTS, REEL, VIDEO],
      use: { browserName: "chromium", viewport: mobile },
    },
    {
      name: "webkit",
      testIgnore: [PERFORMANCE, SCREENSHOTS, REEL, VIDEO],
      use: { browserName: "webkit", viewport: desktop },
    },
    {
      name: "webkit-mobile",
      testIgnore: [PERFORMANCE, SCREENSHOTS, REEL, VIDEO],
      use: { browserName: "webkit", viewport: mobile },
    },
    // The performance budget starts its own large workspace (25,000 jobs).
    {
      name: "chromium-performance",
      testMatch: PERFORMANCE,
      timeout: 300000,
      use: { browserName: "chromium", viewport: desktop },
    },
    // Images of every screen for visual review (`npm run screenshots`);
    // each screen adds the owner cookie itself unless it shows sign-in.
    {
      name: "screenshots",
      testMatch: SCREENSHOTS,
      use: { browserName: "chromium", signedIn: false },
    },
    // The README's demo reel (`npm run reel`), never run in CI.
    {
      name: "reel",
      testMatch: REEL,
      use: { browserName: "chromium" },
    },
    // Dashboard footage for a video, against a running demo (video.spec.ts).
    {
      name: "video",
      testMatch: VIDEO,
      use: { browserName: "chromium" },
    },
  ],
});
