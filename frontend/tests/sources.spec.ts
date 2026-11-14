import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "./fixtures";
import {
  call,
  fitsViewport,
  go,
  isPhone,
  ownerSession,
  type Cookies,
} from "./session";

// Job sources (#227): the schedule line, the source rows with their menu,
// the source editor with Test, and Recent checks. The browser-test server
// runs no collection worker, so a check stays queued until it is stopped,
// and Test answers come from a route: the tests never reach a job board.
// Each test starts from the seeded workspace (fixtures.ts).
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const toast = (page: Page) => page.locator(".ui-toast").last();
const list = (page: Page) => page.getByRole("region", { name: "Job sources" });
const row = (page: Page, name: string) =>
  list(page).locator(".src-row").filter({ hasText: name });
const editor = (page: Page) => page.getByRole("dialog", { name: /source/ });

async function menu(page: Page, name: string, item: string) {
  const target = row(page, name);
  await target.hover();
  await target
    .getByRole("button", { name: `More actions for ${name}` })
    .click();
  await page
    .getByRole("menu", { name: `Actions for ${name}` })
    .getByRole("menuitem", { name: item })
    .click();
}

async function sourceNamed(page: Page, name: string) {
  return (await call(page, "/sources?limit=500")).items.find(
    (item: { name: string }) => item.name === name,
  );
}

const PREVIEW = {
  kind: "jobspy",
  total: 12,
  preview_limit: 20,
  items: Array.from({ length: 12 }, (_, index) => ({
    title: `Synthetic data engineer ${index + 1}`,
    company: "Example Labs",
    location: "Zurich",
  })),
  diagnostics: [{ provider: "indeed", message: "Waited for the request gap." }],
};

test("add a search: Test shows the first ten results, then Save adds it", async ({
  page,
}) => {
  const asked: unknown[] = [];
  await page.route("**/api/v1/sources/preview", (route) => {
    asked.push(route.request().postDataJSON());
    return route.fulfill({ json: PREVIEW });
  });
  const name = unique("Synthetic search");
  await go(page, "sources");
  const before = (await call(page, "/sources?limit=1")).total;
  // Rows show content only: no button is visible at rest.
  if (!isPhone(page)) {
    await page.mouse.move(0, 0);
    await expect(
      list(page).locator(".src-row-actions button:visible"),
    ).toHaveCount(0);
  }
  await page.getByRole("button", { name: "Add source" }).first().click();
  const form = editor(page);
  await expect(form.getByLabel("Keywords")).toBeFocused();
  // Indeed needs a country; the form says so on Test, before asking.
  await form.getByLabel("Keywords").fill("synthetic engineer");
  await form.getByRole("button", { name: "Test" }).click();
  await expect(form.getByText("Indeed and Glassdoor search one")).toBeVisible();
  expect(asked).toEqual([]);
  await form.getByLabel("Country").fill("switzerland");
  await form.getByLabel(/^Location/).fill("Zurich");
  await form.getByLabel(/^Title must include/).fill("engineer, developer");
  await form.getByLabel(/^Name/).fill(name);
  await form.getByRole("button", { name: "Test" }).click();
  const results = form.getByRole("region", { name: /jobs found/ });
  await expect(results).toContainText("12 jobs found · the first 10");
  await expect(results.getByRole("listitem")).toHaveCount(10);
  await expect(results).toContainText("Indeed: Waited for the request gap.");
  expect(asked[0]).toMatchObject({
    kind: "jobspy",
    config: {
      query: "synthetic engineer",
      location: "Zurich",
      country: "switzerland",
      providers: ["linkedin", "indeed"],
    },
    filters: { titles: ["engineer", "developer"] },
  });
  // Nothing was saved by the test.
  expect((await call(page, "/sources?limit=1")).total).toBe(before);
  await fitsViewport(page);
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await expect(toast(page)).toContainText(`Added “${name}”`);
  await expect(form).toBeHidden();
  const saved = await sourceNamed(page, name);
  expect(saved).toMatchObject({
    kind: "jobspy",
    enabled: true,
    config: { query: "synthetic engineer", country: "switzerland" },
  });
  await expect(row(page, name)).toContainText(
    "synthetic engineer · Zurich · LinkedIn, Indeed",
  );
});

test("a company page names its job board from the address", async ({
  page,
}) => {
  await go(page, "sources");
  await page.getByRole("button", { name: "Add source" }).first().click();
  const form = editor(page);
  await form.getByLabel("Kind").selectOption("company");
  const address = form.getByLabel("Careers page address");
  await address.fill("https://boards.greenhouse.io/syntheticlabs");
  await expect(form).toContainText("Detected: Greenhouse · syntheticlabs");
  await address.fill("https://careers.example.test/jobs");
  await expect(form).toContainText("looks for a supported job board");
  await address.fill("https://jobs.lever.co/syntheticlabs");
  await expect(form).toContainText("Detected: Lever · syntheticlabs");
  // Saved, the server detects the same board; unnamed, it is named after it.
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await expect(toast(page)).toContainText("Added “Syntheticlabs”");
  const saved = await sourceNamed(page, "Syntheticlabs");
  expect(saved).toMatchObject({
    kind: "lever",
    config: { board: "syntheticlabs" },
  });
  await expect(row(page, "Syntheticlabs")).toContainText("Lever");
});

test("check now, stop, pause with undo, and delete for good", async ({
  page,
}) => {
  const name = unique("Synthetic company");
  await go(page, "today");
  await call(page, "/sources", "POST", {
    name,
    kind: "greenhouse",
    url: "https://boards.greenhouse.io/synthetic",
    enabled: true,
  });
  await go(page, "sources");
  // Check now: from the hover action on a wide screen, the menu on a phone.
  if (isPhone(page)) await menu(page, name, "Check now");
  else {
    await row(page, name).hover();
    await row(page, name)
      .getByRole("button", { name: `Check ${name} now` })
      .click();
  }
  await expect(toast(page)).toContainText(`Checking “${name}” now`);
  await expect(row(page, name)).toContainText("Checking now…");
  await menu(page, name, "Stop this check");
  await expect(toast(page)).toContainText(`Stopped the check of “${name}”`);
  await expect(row(page, name)).not.toContainText("Checking now…");

  // Pause greys the row; Undo resumes it.
  await menu(page, name, "Pause");
  await expect(toast(page)).toContainText(`Paused “${name}”`);
  await expect(row(page, name)).toHaveAttribute("data-paused", "true");
  expect((await sourceNamed(page, name)).enabled).toBe(false);
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect
    .poll(async () => (await sourceNamed(page, name)).enabled)
    .toBe(true);
  await expect(row(page, name)).not.toHaveAttribute("data-paused");
  await menu(page, name, "Pause");
  await expect(row(page, name)).toHaveAttribute("data-paused", "true");
  await menu(page, name, "Resume");
  await expect(toast(page)).toContainText(`Resumed “${name}”`);

  // Delete asks first; the jobs it found stay.
  await menu(page, name, "Delete permanently…");
  const confirm = page.getByRole("dialog", { name: `Delete “${name}”?` });
  await expect(confirm).toContainText("The jobs it already found stay");
  await confirm.getByRole("button", { name: "Delete source" }).click();
  await expect(toast(page)).toContainText(`Deleted “${name}”`);
  await expect(row(page, name)).toHaveCount(0);
  expect(await sourceNamed(page, name)).toBeUndefined();
  await fitsViewport(page);
});

test("a failing source says so in red, with Details; Recent checks retry", async ({
  page,
}) => {
  await page.route(
    (url) => url.pathname === "/api/v1/sources",
    async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const response = await route.fetch();
      const body = await response.json();
      body.items[0] = {
        ...body.items[0],
        last_outcome: "failed",
        last_error:
          "Blocked by the site (HTTP 403). It may allow requests later.",
        last_run: {
          id: "R-1",
          state: "failed",
          started_at: new Date().toISOString(),
        },
      };
      await route.fulfill({ response, json: body });
    },
  );
  await go(page, "today");
  const name = unique("Synthetic board");
  await call(page, "/sources", "POST", {
    name,
    kind: "greenhouse",
    url: "https://boards.greenhouse.io/synthetic",
    enabled: true,
  });
  await go(page, "sources");
  const first = list(page).locator(".src-row").first();
  await expect(first).toHaveAttribute("data-failed", "true");
  await expect(first.locator(".src-danger")).toHaveText(
    "Last check failed: blocked by the site (HTTP 403)",
  );
  await first.getByRole("button", { name: "Details" }).click();
  const details = page.getByRole("dialog", { name: /^Last check of/ });
  await expect(details).toContainText(
    "Blocked by the site (HTTP 403). It may allow requests later.",
  );
  await details.getByRole("button", { name: "Close" }).click();
  await expect(details).toBeHidden();

  // Recent checks, collapsed: the seeded failed check says why; its source
  // is gone, so there is nothing to retry.
  const checks = page.getByRole("list", { name: "Recent checks" });
  await expect(checks).toHaveCount(0);
  await page.getByText("Recent checks", { exact: true }).click();
  const failed = checks.getByRole("listitem").filter({
    hasText: "Failed: the board did not answer",
  });
  await expect(failed).toHaveCount(1);
  await expect(failed.getByRole("button")).toHaveCount(0);
  // A check in progress can be stopped from there.
  await menu(page, name, "Check now");
  const running = checks.getByRole("listitem").filter({ hasText: name });
  await expect(running).toContainText("Waiting to start");
  await running
    .getByRole("button", { name: `Stop the check of ${name}` })
    .click();
  await expect(toast(page)).toContainText(`Stopped the check of “${name}”`);
  await expect(running).toContainText("Stopped");
  await fitsViewport(page);
});

test("the schedule line sets one interval and pauses every check", async ({
  page,
}) => {
  await go(page, "sources");
  const interval = page.getByLabel("How often sources are checked");
  await expect(interval).toHaveValue("1440");
  await interval.selectOption("360");
  await expect(toast(page)).toContainText("Sources are checked every 6 h");
  const items = (await call(page, "/sources?limit=500")).items as {
    schedule: { minutes?: number };
  }[];
  expect(items.every((item) => item.schedule.minutes === 360)).toBe(true);
  await expect(page.locator(".src-topline")).toContainText("next check");
  // The switch of every automatic check is in `…`.
  await page
    .getByRole("button", { name: "More about automatic checks" })
    .click();
  await page.getByRole("menuitem", { name: "Pause automatic checks" }).click();
  await expect(page.locator(".src-topline")).toContainText(
    "Automatic checks are paused",
  );
  expect((await call(page, "/collection")).enabled).toBe(false);
  await page
    .locator(".src-topline")
    .getByRole("button", { name: "Resume" })
    .click();
  await expect
    .poll(async () => (await call(page, "/collection")).enabled)
    .toBe(true);
  // Check all now queues every source that is on. (The seeded sources are
  // records without a query, which the server refuses to run.)
  const run: { action?: string; items?: unknown[] }[] = [];
  await page.route("**/api/v1/sources/bulk", (route) => {
    run.push(route.request().postDataJSON());
    return route.fulfill({
      json: { items: [], total: 0, succeeded: 0, failed: 0 },
    });
  });
  await page.getByRole("button", { name: "Check all now" }).click();
  await expect(toast(page)).toContainText(/Checking \d+ sources now/);
  expect(run[0]).toMatchObject({ action: "run" });
  expect(run[0].items).toHaveLength(items.length);
});

test("keyboard: move through sources, edit with e, keep a draft on Esc", async ({
  page,
}) => {
  test.skip(isPhone(page), "Row letters are for a keyboard.");
  await go(page, "sources");
  const rows = list(page).locator(".src-row-open");
  await rows.first().focus();
  await page.keyboard.press("j");
  await expect(rows.nth(1)).toBeFocused();
  await page.keyboard.press("k");
  await expect(rows.first()).toBeFocused();
  await page.keyboard.press("j");
  const name = (await rows.nth(1).textContent())!.replace(" · Paused", "");
  await page.keyboard.press("e");
  const form = page.getByRole("dialog", { name: `Edit ${name}` });
  await expect(form).toBeVisible();
  const field = form.getByLabel(/^Name/);
  await field.fill(`${name} draft`);
  await page.keyboard.press("Escape");
  const leave = page.getByRole("dialog", { name: "Discard unsaved changes?" });
  await expect(leave).toBeVisible();
  await leave.getByRole("button", { name: "Keep editing" }).click();
  await expect(field).toHaveValue(`${name} draft`);
  await field.fill(name);
  await page.keyboard.press("Escape");
  await expect(form).toBeHidden();
  await expect(rows.nth(1)).toBeFocused();
});

test("the empty state offers a search and a company page", async ({ page }) => {
  await page.route(
    (url) => url.pathname === "/api/v1/sources",
    (route) =>
      route.request().method() === "GET"
        ? route.fulfill({
            json: { items: [], total: 0, limit: 500, offset: 0 },
          })
        : route.fallback(),
  );
  await go(page, "sources");
  await expect(page.getByText("No job sources yet")).toBeVisible();
  await expect(
    page.getByText("Add a search to get new jobs every few hours."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add a company page" }).click();
  await expect(editor(page).getByLabel("Kind")).toHaveValue("company");
});

test("Sources with its menu and editor open has no serious accessibility finding", async ({
  page,
}) => {
  await page.route("**/api/v1/sources/preview", (route) =>
    route.fulfill({ json: PREVIEW }),
  );
  const check = async () => {
    // A dialog or menu still fading in would be measured half blended.
    await page.evaluate(() =>
      Promise.all(
        document
          .getAnimations()
          .map((animation) => animation.finished.catch(() => undefined)),
      ),
    );
    const { violations } = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      violations
        .filter((item) => ["serious", "critical"].includes(item.impact ?? ""))
        .map(
          (item) => `${item.id}: ${item.nodes.map((n) => n.target).join(" ")}`,
        ),
    ).toEqual([]);
  };
  for (const theme of ["light", "dark"]) {
    await page.emulateMedia({ colorScheme: theme as "light" | "dark" });
    await go(page, "sources");
    await page.reload();
    await page.getByText("Recent checks", { exact: true }).click();
    await expect(
      page.getByRole("list", { name: "Recent checks" }),
    ).toBeVisible();
    await check();
    const name = (await list(page)
      .locator(".src-row-open")
      .first()
      .textContent())!;
    await row(page, name).hover();
    await row(page, name)
      .getByRole("button", { name: /^More actions/ })
      .click();
    await expect(page.getByRole("menu")).toBeVisible();
    await check();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Add source" }).first().click();
    await editor(page).getByLabel("Keywords").fill("synthetic");
    await editor(page).getByLabel("Country").fill("switzerland");
    await editor(page).getByRole("button", { name: "Test" }).click();
    await expect(editor(page).getByText("12 jobs found")).toBeVisible();
    await check();
  }
});
