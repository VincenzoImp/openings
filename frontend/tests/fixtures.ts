// The `test` and `expect` of every browser test, in one place so that a
// shared fixture can be added without touching each spec.
//
// Isolation: each worker starts its own synthetic server on a private copy of
// the seeded snapshot (server.ts), and an automatic fixture restores that copy
// before every test. A test may change anything; the next one starts from the
// same seeded workspace, whatever ran before it and in whichever worker.
import { test as base } from "@playwright/test";
import { startServer, type Server } from "./server";

export { expect } from "@playwright/test";
export type { BrowserContext, Locator, Page } from "@playwright/test";

export const test = base.extend<{ seededWorkspace: void }, { server: Server }>({
  server: [
    async ({}, use) => {
      const snapshot = process.env.OPENINGS_E2E_SNAPSHOT;
      if (!snapshot) throw Error("The global setup did not seed a workspace.");
      const server = await startServer({ snapshot });
      await use(server);
      await server.stop();
    },
    { scope: "worker", timeout: 90_000 },
  ],
  baseURL: async ({ server }, use) => use(server.url),
  seededWorkspace: [
    async ({ server }, use) => {
      const response = await fetch(server.url + "/__e2e__/reset", {
        method: "POST",
      });
      if (response.status !== 204)
        throw Error(`The workspace was not reset (${response.status}).`);
      await use();
    },
    { auto: true },
  ],
});
