import { defineConfig, devices } from "@playwright/test";

/**
 * Two servers: one open, one behind an API token. Both run from a temporary
 * data directory (see e2e/serve.sh) and serve the built dashboard.
 */
export const PLAIN_PORT = 18660;
export const TOKEN_PORT = 18661;
export const PLAIN_URL = `http://127.0.0.1:${PLAIN_PORT}`;
export const TOKEN_URL = `http://127.0.0.1:${TOKEN_PORT}`;
export const API_TOKEN = "e2e-token";

const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: isCI ? 1 : 0,
  forbidOnly: isCI,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: isCI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: PLAIN_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      testIgnore: /token\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "desktop-dark",
      testMatch: /(a11y|system|responsive)\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
        colorScheme: "dark",
      },
    },
    {
      name: "phone",
      testMatch: /(a11y|responsive|inbox|pipeline|job)\.spec\.ts/,
      use: { ...devices["iPhone 12"], browserName: "chromium" },
    },
    {
      name: "tablet",
      testMatch: /(a11y|responsive)\.spec\.ts/,
      use: { ...devices["iPad (gen 7)"], browserName: "chromium" },
    },
    {
      name: "token",
      testMatch: /token\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
        baseURL: TOKEN_URL,
      },
    },
  ],
  webServer: [
    {
      command: `sh e2e/serve.sh ${PLAIN_PORT}`,
      url: `${PLAIN_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: `sh e2e/serve.sh ${TOKEN_PORT} ${API_TOKEN}`,
      url: `${TOKEN_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
