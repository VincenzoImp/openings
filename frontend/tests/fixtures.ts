// The `test` and `expect` of every browser test, in one place so that a
// shared fixture can be added without touching each spec.
//
// Isolation: each worker starts its own synthetic server on a private copy of
// the seeded snapshot (server.ts), and an automatic fixture restores that copy
// before every test. A test may change anything; the next one starts from the
// same seeded workspace, whatever ran before it and in whichever worker.
//
// Every test runs signed in as the owner (`test.use({ signedIn: false })` in
// a describe block opts out) and fails on any uncaught error of the page; a
// test that provokes one on purpose empties `pageErrors` itself.
import { expect, test as base } from "@playwright/test";
import { expectPdfViewer } from "../scripts/capture.mjs";
import { startServer, type Server } from "./server";
import { ownerSession } from "./session";

export { expect } from "@playwright/test";
export type { BrowserContext, Locator, Page } from "@playwright/test";

export type Options = { signedIn: boolean };
// A capture project (screenshots, reel, video) needs the browser's PDF viewer.
export type WorkerOptions = { pdfViewer: boolean };

export const test = base.extend<
  Options & { seededWorkspace: void; pageErrors: string[] },
  WorkerOptions & { server: Server; pdfViewerChecked: void }
>({
  pdfViewer: [false, { option: true, scope: "worker" }],
  pdfViewerChecked: [
    async ({ browser, pdfViewer }, use) => {
      if (pdfViewer) await expectPdfViewer(browser);
      await use();
    },
    { scope: "worker", auto: true },
  ],
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
  signedIn: [true, { option: true }],
  context: async ({ context, signedIn }, use) => {
    if (signedIn) await context.addCookies(ownerSession());
    await use(context);
  },
  pageErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      // The served Content-Security-Policy (backend app.py) must allow the dashboard.
      page.on("console", (message) => {
        if (/Content Security Policy/i.test(message.text()))
          errors.push(message.text());
      });
      await use(errors);
      expect(errors, "uncaught errors of the page").toEqual([]);
    },
    { auto: true },
  ],
});
