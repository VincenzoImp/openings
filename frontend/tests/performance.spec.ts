import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { test, expect } from "@playwright/test";

// The performance budget of docs/developer/dashboard-design.md: on a synthetic
// workspace of 5,000 jobs and 500 applications, the Applications list of 200
// rows is interactive in under 300 ms after navigation. This project starts
// its own large workspace (backend/tests/large_fixtures.py), so the other
// projects keep their small, fast one.
const BUDGET_MS = 300;
const RUNS = 7;
let server: ChildProcess | undefined;
let base = "";

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

test.beforeAll(async () => {
  test.setTimeout(240_000);
  const port = await freePort();
  base = `http://127.0.0.1:${port}`;
  server = spawn(
    "uv",
    [
      "run",
      "--project",
      "..",
      "python",
      "../backend/tests/dashboard_server.py",
    ],
    {
      env: {
        ...process.env,
        OPENINGS_E2E_PORT: String(port),
        OPENINGS_E2E_TOKEN: "performance",
        OPENINGS_E2E_JOBS: "5000",
        OPENINGS_E2E_APPLICATIONS: "500",
      },
      stdio: "ignore",
    },
  );
  const started = Date.now();
  while (Date.now() - started < 220_000) {
    try {
      if ((await fetch(base + "/health")).ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw Error("The large synthetic workspace did not start.");
});

test.afterAll(() => {
  server?.kill();
});

test("the Applications list of 200 rows is interactive in under 300 ms", async ({
  page,
}) => {
  await page.goto(base + "/");
  await page.locator("input[name=password]").fill("synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".main h1")).toHaveText("Today");
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
  ).toBeGreaterThanOrEqual(5000);

  const timings: number[] = [];
  for (let run = 0; run < RUNS; run++) {
    await page.goto(base + "/#today");
    await expect(page.locator(".main h1")).toHaveText("Today");
    await page.waitForLoadState("networkidle");
    // From the click on Applications in the navigation to 200 rows on screen,
    // with the main thread free again to take the next click.
    const elapsed = await page.evaluate(
      () =>
        new Promise<number>((resolve, reject) => {
          const link = [
            ...document.querySelectorAll<HTMLAnchorElement>(
              "a[href='#applications']",
            ),
          ].find((item) => item.offsetParent !== null);
          if (!link) return reject(Error("No Applications link."));
          const start = performance.now();
          const done = () => {
            const rows = document.querySelectorAll(
              "[role=table][aria-label=Applications] [role=rowgroup]:last-child > [role=row]",
            );
            if (rows.length < 200) return false;
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
    );
    // The rows are real and usable: the last one can be selected.
    const boxes = page.locator(
      "[role=table][aria-label=Applications] input[type=checkbox]",
    );
    await expect(boxes).toHaveCount(201);
    timings.push(Math.round(elapsed));
  }
  const sorted = [...timings].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  test.info().annotations.push({
    type: "timings",
    description: `Applications list, 200 rows: ${timings.join(", ")} ms; median ${median} ms (budget ${BUDGET_MS} ms)`,
  });
  console.log(
    `Applications list, 200 rows: ${timings.join(", ")} ms; median ${median} ms`,
  );
  expect(median).toBeLessThan(BUDGET_MS);
});
