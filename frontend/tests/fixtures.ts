// The `test` of every browser test. With OPENINGS_PARITY_EVIDENCE set to a
// directory, the Chromium desktop project writes there, per test, the REST
// requests the dashboard itself sent and the status of each answer. The parity
// gate (scripts/parity_matrix.py --gate) reads them: every operation needs a
// dashboard path that a test exercised, and the dashboard may call no route
// outside the operation inventory. Requests the helpers in session.ts make for
// a test's own setup carry the setup header and are left out; answers a test
// gives itself are marked.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test as base, type Request } from "@playwright/test";

export { expect } from "@playwright/test";
export type { BrowserContext, Locator, Page } from "@playwright/test";

const SETUP_HEADER = "x-openings-e2e-setup";
const PROJECT = "chromium";

export const test = base.extend<{ parityEvidence: void }>({
  parityEvidence: [
    async ({ context }, use, info) => {
      const directory = process.env.OPENINGS_PARITY_EVIDENCE;
      if (!directory || info.project.name !== PROJECT) return use();
      const requests = new Map<
        string,
        { method: string; path: string; status: number; answered: boolean }
      >();
      const pending: Promise<void>[] = [];
      const record = (request: Request) =>
        pending.push(
          (async () => {
            const { pathname } = new URL(request.url());
            if (!pathname.startsWith("/api/") && pathname !== "/health") return;
            const headers = await request.allHeaders().catch(() => ({}));
            if (SETUP_HEADER in headers) return;
            // A request cut short before its answer (a navigation, a
            // download) has status -1.
            const response = await request.response().catch(() => null);
            const status = response?.status() ?? -1;
            // A test that answers a request itself (page.route) leaves no
            // server address: the matrix counts that only where it says why.
            const answered = !!response && !(await response.serverAddr());
            const entry = {
              method: request.method(),
              path: pathname,
              status,
              answered,
            };
            requests.set(
              `${entry.method} ${pathname} ${status} ${answered}`,
              entry,
            );
          })().catch(() => {}),
        );
      context.on("requestfinished", record);
      context.on("requestfailed", record);
      await use();
      await Promise.all(pending);
      mkdirSync(directory, { recursive: true });
      writeFileSync(
        join(directory, `${info.testId}.json`),
        JSON.stringify({
          title: info.title,
          file: info.file.split(/[\\/]/).pop(),
          requests: [...requests.values()],
        }),
      );
    },
    { auto: true },
  ],
});
