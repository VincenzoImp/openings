import { test, expect, type Page } from "@playwright/test";
import { startServer, type Server } from "./server";

// The performance budget of the dashboard: on a synthetic
// workspace of 25,000 jobs (with their ingest signals) and 500 applications,
// the Applications list and the jobs to review, 200 rows each, are interactive
// in under 300 ms after navigation. This project starts its own large
// workspace (backend/tests/large_fixtures.py), so the other projects keep
// their small, fast one.
const BUDGET_MS = 300;
const RUNS = 7;
const JOBS = 25000;
let server: Server | undefined;
let base = "";

test.beforeAll(async () => {
  test.setTimeout(300_000);
  server = await startServer({
    env: { OPENINGS_E2E_JOBS: String(JOBS), OPENINGS_E2E_APPLICATIONS: "500" },
    timeout: 280_000,
  });
  base = server.url;
});

test.afterAll(async () => {
  await server?.stop();
});

async function signIn(page: Page) {
  await page.goto(base + "/");
  await page.locator("input[name=password]").fill("synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("h1:visible")).toHaveText("Today");
}

/**
 * The median time from a click on a navigation link to `rows` rows of the
 * list on screen, with the main thread free again to take the next click.
 */
async function median(page: Page, href: string, rows: string, label: string) {
  const timings: number[] = [];
  for (let run = 0; run < RUNS; run++) {
    await page.goto(base + "/#today");
    await expect(page.locator("h1:visible")).toHaveText("Today");
    await page.waitForLoadState("networkidle");
    const elapsed = await page.evaluate(
      ({ href, rows }) =>
        new Promise<number>((resolve, reject) => {
          const link = [
            ...document.querySelectorAll<HTMLAnchorElement>(
              `a[href='${href}']`,
            ),
          ].find((item) => item.offsetParent !== null);
          if (!link) return reject(Error(`No link to ${href}.`));
          const start = performance.now();
          const done = () => {
            if (document.querySelectorAll(rows).length < 200) return false;
            // Wait for the browser to paint, then for a free task.
            requestAnimationFrame(() =>
              setTimeout(() => resolve(performance.now() - start), 0),
            );
            return true;
          };
          const observer = new MutationObserver(() => {
            if (done()) observer.disconnect();
          });
          observer.observe(document.body, { childList: true, subtree: true });
          setTimeout(() => reject(Error("The list did not appear.")), 10_000);
          link.click();
        }),
      { href, rows },
    );
    timings.push(Math.round(elapsed));
  }
  const sorted = [...timings].sort((a, b) => a - b);
  const middle = sorted[Math.floor(sorted.length / 2)];
  const line = `${label}, 200 rows: ${timings.join(", ")} ms; median ${middle} ms (budget ${BUDGET_MS} ms)`;
  test.info().annotations.push({ type: "timings", description: line });
  console.log(line);
  return middle;
}

test("the Applications list of 200 rows is interactive in under 300 ms", async ({
  page,
}) => {
  await signIn(page);
  const counts = await page.evaluate(() =>
    fetch("/api/v1/applications?limit=1").then((response) => response.json()),
  );
  expect(counts.total).toBeGreaterThanOrEqual(500);
  expect(
    (
      await page.evaluate(() =>
        fetch("/api/v1/jobs?limit=1").then((response) => response.json()),
      )
    ).total,
  ).toBeGreaterThanOrEqual(JOBS);
  const time = await median(
    page,
    "#applications",
    ".ui-list[aria-label=Applications] [data-row-id]",
    "Applications list",
  );
  // The rows are real and usable: the first page of 200 is drawn at once.
  expect(
    await page.locator(".ui-list[aria-label=Applications] [data-row-id]").count(),
  ).toBeGreaterThanOrEqual(200);
  expect(time).toBeLessThan(BUDGET_MS);
});

test("the jobs to review, 200 rows with their signals, are interactive in under 300 ms", async ({
  page,
}) => {
  await signIn(page);
  const inbox = await page.evaluate(() =>
    fetch("/api/v1/jobs?triage=new&limit=1").then((response) =>
      response.json(),
    ),
  );
  expect(inbox.total).toBeGreaterThanOrEqual(200);
  expect(inbox.items[0].signals.computed).toBe(true);
  const time = await median(page, "#jobs", ".job-list > li", "Jobs to review");
  await expect(page.locator(".job-list input[type=checkbox]")).toHaveCount(200);
  expect(time).toBeLessThan(BUDGET_MS);
});
