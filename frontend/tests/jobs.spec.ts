import { test, expect, type Page } from "./fixtures";
import { call, go, isPhone, ownerSession, type Cookies } from "./session";

// Jobs (#223): the triage flow. A decision moves on to the next job, every
// decision has Undo, the keyboard does it all, Dismissed shows who dismissed
// a job and restores it, a possible duplicate is decided inside the job, and
// a phone pushes the job full screen with its decision at the bottom. Each
// test starts from the seeded workspace (fixtures.ts).
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
  await go(page, "today");
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const rows = (page: Page) => page.locator(".jobs-list .ui-row");
const row = (page: Page, title: string) =>
  rows(page).filter({ hasText: title });
const title = (page: Page) => page.locator("#job-title");
const toast = (page: Page) => page.locator(".ui-toast").last();
const dialog = (page: Page) => page.locator("dialog[open]").last();
const LONG =
  "Northwind Data builds forecasting tools for regional water networks. You will build and " +
  "run the pipelines that feed our demand forecasts, model sensor data in PostgreSQL and " +
  "work with analysts on data quality every week. We look for three years of data " +
  "engineering with Python and SQL, experience with a workflow scheduler and clear written " +
  "English.";

async function job(page: Page, name: string, fields: object = {}) {
  return call(page, "/jobs", "POST", {
    title: name,
    company: "Northwind Data",
    location: "Zurich, Switzerland",
    posting: `${name}. Build reliable services with a small team in Zurich.`,
    ...fields,
  });
}
/** Jobs made for one test, in the order the list shows them. */
async function jobs(page: Page, tag: string, count: number) {
  for (let index = 0; index < count; index++)
    await job(page, `${tag} ${String(index).padStart(2, "0")}`);
  const list = await call(
    page,
    `/jobs?triage=new&sort=newest&limit=50&q=${encodeURIComponent(tag)}`,
  );
  return list.items as { id: string; title: string; version: number }[];
}
const triageOf = async (page: Page, id: string) =>
  (await call(page, `/jobs/${id}`)).triage as string;

test("twenty jobs are triaged by keyboard in at most 25 keys, each with its next job and Undo", async ({
  page,
}) => {
  test.skip(isPhone(page), "The keyboard flow is the desktop's.");
  const tag = unique("Keys");
  const made = await jobs(page, tag, 20);
  await go(page, `jobs?q=${encodeURIComponent(tag)}`);
  await expect(rows(page)).toHaveCount(20);
  // The first job is shown at once; rows at rest show no buttons.
  await expect(title(page)).toHaveText(
    (await rows(page).first().locator(".ui-row-title").textContent())!,
  );
  const atRest = rows(page).nth(5).locator("button:visible");
  await expect(atRest).toHaveCount(1); // the row itself
  let keys = 0;
  const press = async (key: string) => {
    keys += 1;
    await page.keyboard.press(key);
  };
  // Read, decide, next: s and d alternate; one is undone and decided again.
  const decided = new Map<string, string>();
  for (let index = 0; index < 20; index++) {
    const shown = (await title(page).textContent())!;
    expect(decided.has(shown)).toBe(false);
    await press(index % 2 ? "d" : "s");
    decided.set(shown, index % 2 ? "dismissed" : "shortlisted");
    if (index === 3) {
      await expect(toast(page)).toContainText("Dismissed");
      await press("z");
      await expect(title(page)).toHaveText(shown);
      await expect(row(page, shown)).toHaveCount(1);
      await press("d");
    }
    if (index < 19) await expect(title(page)).not.toHaveText(shown);
  }
  await expect(page.getByText("No jobs match")).toBeVisible();
  expect(keys).toBeLessThanOrEqual(25);
  for (const item of made)
    await expect
      .poll(() => triageOf(page, item.id))
      .toBe(decided.get(item.title));
  // A shortlist started the job's application.
  const shortlisted = made.find(
    (item) => decided.get(item.title) === "shortlisted",
  )!;
  expect(
    (await call(page, `/jobs/${shortlisted.id}`)).application,
  ).not.toBeNull();
});

test("j and k move, x and shift+j pick, and the bulk bar dismisses with Undo", async ({
  page,
}) => {
  test.skip(isPhone(page), "The keyboard flow is the desktop's.");
  const tag = unique("Pick");
  const made = await jobs(page, tag, 4);
  await go(page, `jobs?q=${encodeURIComponent(tag)}`);
  await expect(rows(page)).toHaveCount(4);
  await page.keyboard.press("j");
  await expect(title(page)).toHaveText(made[1].title);
  await page.keyboard.press("k");
  await expect(title(page)).toHaveText(made[0].title);
  await page.keyboard.press("x");
  await page.keyboard.press("Shift+J");
  await page.keyboard.press("Shift+J");
  const bar = page.getByRole("toolbar", { name: "3 selected" });
  await expect(bar).toBeVisible();
  await bar.getByRole("button", { name: "Dismiss" }).click();
  await expect(toast(page)).toContainText("Dismissed 3 jobs");
  await expect(rows(page)).toHaveCount(1);
  await expect(title(page)).toHaveText(made[3].title);
  for (const item of made.slice(0, 3))
    await expect.poll(() => triageOf(page, item.id)).toBe("dismissed");
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect(rows(page)).toHaveCount(4);
  for (const item of made.slice(0, 3))
    await expect.poll(() => triageOf(page, item.id)).toBe("new");
});

test("mouse triage: row and pane actions, a reason typed in the toast, and Undo", async ({
  page,
}) => {
  test.skip(isPhone(page), "A phone swipes instead (see below).");
  const tag = unique("Mouse");
  const made = await jobs(page, tag, 3);
  await go(page, `jobs?q=${encodeURIComponent(tag)}`);
  await expect(rows(page)).toHaveCount(3);
  // The row's hover action shortlists; the toast offers Undo only.
  await row(page, made[0].title).hover();
  await row(page, made[0].title)
    .getByRole("button", { name: "Shortlist" })
    .click();
  await expect(toast(page)).toContainText(`Shortlisted “${made[0].title}”`);
  await expect(toast(page).getByRole("button", { name: "Open" })).toHaveCount(
    0,
  );
  await expect(title(page)).toHaveText(made[1].title);
  // The pane's Dismiss is immediate; the reason is added from the toast.
  await page
    .locator(".jobs-decision")
    .getByRole("button", { name: /^Dismiss/ })
    .click();
  await expect(toast(page)).toContainText(`Dismissed “${made[1].title}”`);
  await toast(page).getByRole("button", { name: "Add reason" }).click();
  await page.getByLabel("Why did you dismiss it?").fill("Too far from home.");
  await page.keyboard.press("Enter");
  await expect(toast(page)).toContainText("Saved the reason");
  const dismissed = await call(page, `/jobs/${made[1].id}`);
  expect(dismissed.triage).toBe("dismissed");
  expect(dismissed.dismissal.reason).toBe("Too far from home.");
  expect(dismissed.dismissal.by).toBe("owner");
  // The … menu holds no copy of the visible decisions.
  await expect(title(page)).toHaveText(made[2].title);
  await page.getByRole("button", { name: "More actions" }).click();
  await expect(
    page.getByRole("menuitem", { name: /^Correct details/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("menuitem", { name: /^(Shortlist|Dismiss)/ }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  // Undo brings the job back where it was.
  await page
    .locator(".jobs-decision")
    .getByRole("button", { name: /^Dismiss/ })
    .click();
  await expect(page.getByText("No jobs match")).toBeVisible();
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect(title(page)).toHaveText(made[2].title);
  await expect.poll(() => triageOf(page, made[2].id)).toBe("new");
});

test("Dismissed shows who and why; r restores one, the agent filter and the bulk bar restore a batch", async ({
  page,
}) => {
  test.skip(isPhone(page), "The keyboard flow is the desktop's.");
  const tag = unique("Agent batch");
  const agent = await call(page, "/tokens", "POST", {
    name: unique("Triage agent"),
    kind: "agent",
  });
  const made = await jobs(page, tag, 3);
  const result = await call(
    page,
    "/jobs/bulk",
    "POST",
    {
      action: "dismissed",
      reason: "Synthetic: outside the preferences.",
      items: made.map((item) => ({
        id: item.id,
        expected_version: item.version,
      })),
    },
    agent.token,
  );
  expect(result.succeeded).toBe(3);
  await go(page, `jobs?section=dismissed&q=${encodeURIComponent(tag)}`);
  await expect(rows(page)).toHaveCount(3);
  await expect(rows(page).first()).toContainText(
    `by ${agent.name}: Synthetic: outside the preferences.`,
  );
  // One job back with r.
  await page.keyboard.press("r");
  await expect(toast(page)).toContainText("Restored");
  await expect(rows(page)).toHaveCount(2);
  // The agent's batch, through the filter: pick both and Restore.
  await page.getByRole("button", { name: "Filter" }).click();
  await page.getByRole("button", { name: /^Dismissed by/ }).click();
  await page.getByRole("button", { name: /^An agent/ }).click();
  await expect(page).toHaveURL(/dismissed_by=agent/);
  await expect(
    page.getByRole("group", { name: "Active filters" }),
  ).toContainText("An agent");
  await page.keyboard.press("Escape");
  await expect(rows(page)).toHaveCount(2);
  await rows(page).first().locator(".ui-row-main").click();
  await page.keyboard.press("x");
  await page.keyboard.press("Shift+J");
  await page
    .getByRole("toolbar", { name: "2 selected" })
    .getByRole("button", { name: "Restore" })
    .click();
  await expect(rows(page)).toHaveCount(0);
  for (const item of made)
    await expect.poll(() => triageOf(page, item.id)).toBe("new");
  await call(page, `/tokens/${agent.id}`, "DELETE");
});

test("a possible duplicate is decided inside the job: kept apart, then merged", async ({
  page,
}) => {
  const tag = unique("Duplicate");
  const url = `https://jobs.example.test/dup/${Date.now()}`;
  const earlier = await job(page, `${tag} Data Engineer`, {
    posting: LONG,
    url: `${url}/a`,
  });
  const copy = await job(page, `${tag} Data Engineer`, {
    posting: LONG,
    url: `${url}/b`,
  });
  expect(copy.signals.duplicate.job_id).toBe(earlier.id);
  await go(page, `jobs?job=${copy.id}`);
  const callout = page.locator(".jobs-callout");
  await expect(callout).toContainText("Possibly the same job as");
  await expect(callout).toContainText("Both have the same company");
  await expect(callout).not.toContainText(/\d\.\d\d/);
  await callout.getByRole("button", { name: "Keep both" }).click();
  await expect(toast(page)).toContainText("as two jobs");
  await expect(callout).toHaveCount(0);
  expect((await call(page, `/jobs/${copy.id}`)).signals.duplicate).toBeNull();
  // A third copy merges into the earlier record, which stays.
  const third = await job(page, `${tag} Data Engineer`, {
    posting: LONG,
    url: `${url}/c`,
  });
  await go(page, `jobs?job=${third.id}`);
  await callout.getByRole("button", { name: "Merge into one job" }).click();
  await expect(toast(page)).toContainText(/^Merged “.+” into “.+”/);
  const kept = await call(page, `/jobs/${earlier.id}`);
  expect(kept.postings).toHaveLength(2);
  const left = await call(page, `/jobs?q=${encodeURIComponent(tag)}&limit=10`);
  expect(left.items.map((item: { id: string }) => item.id).sort()).toEqual(
    [copy.id, earlier.id].sort(),
  );
});

test("a job is added by its address, and the one already there is found", async ({
  page,
}) => {
  const url = `https://jobs.example.test/known/${Date.now()}`;
  const known = await job(page, unique("Known role"), { url });
  await go(page, "jobs");
  await page
    .getByRole("button", { name: "Add job" })
    .filter({ visible: true })
    .first()
    .click();
  const field = dialog(page).getByLabel("Address or posting text");
  await field.fill(url);
  await field.blur();
  await expect(dialog(page)).toContainText("Already in your workspace");
  await dialog(page).getByRole("button", { name: "Open it" }).click();
  await expect(title(page)).toHaveText(known.title);
});

test("forgetting a job asks first and names what is lost", async ({ page }) => {
  const made = await job(page, unique("Forget me"));
  await go(page, `jobs?job=${made.id}`);
  await expect(title(page)).toHaveText(made.title);
  await page
    .getByRole("button", { name: "More actions" })
    .filter({ visible: true })
    .click();
  await page.getByRole("menuitem", { name: "Forget permanently…" }).click();
  await expect(dialog(page)).toContainText("applications, notes and files");
  await dialog(page).getByRole("button", { name: "Forget job" }).click();
  await expect(toast(page)).toContainText("Forgot");
  await expect
    .poll(async () => (await call(page, `/jobs?q=${made.title}`)).total)
    .toBe(0);
});

test("on a phone the job is pushed full screen, its decision stays at the bottom, and a swipe decides", async ({
  page,
}) => {
  test.skip(!isPhone(page), "The phone's layout.");
  const tag = unique("Phone");
  const made = await jobs(page, tag, 3);
  await go(page, `jobs?q=${encodeURIComponent(tag)}`);
  await expect(rows(page)).toHaveCount(3);
  // The first row starts high on the screen.
  const top = (await rows(page).first().boundingBox())!.y;
  expect(top).toBeLessThanOrEqual(260);
  // Tapping pushes the job: the shell's bars step aside.
  await rows(page).first().locator(".ui-row-main").click();
  await expect(title(page)).toHaveText(made[0].title);
  await expect(page.locator(".ui-bottombar")).toBeHidden();
  const bar = page.locator(".ui-actionbar");
  await expect(bar).toBeVisible();
  const box = (await bar.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(844 + 1);
  // Shortlist from the bar: the next job slides in.
  await bar.getByRole("button", { name: "Shortlist" }).click();
  await expect(title(page)).toHaveText(made[1].title);
  await expect.poll(() => triageOf(page, made[0].id)).toBe("shortlisted");
  // Back to the list, then a swipe left dismisses with Undo.
  await page.getByRole("button", { name: "Back to list" }).click();
  await expect(page.locator(".ui-bottombar")).toBeVisible();
  await expect(rows(page)).toHaveCount(2);
  const target = row(page, made[2].title);
  const { x, y, width, height } = (await target.boundingBox())!;
  const at = { x: x + width - 30, y: y + height / 2 };
  const pointer = (type: string, clientX: number) =>
    target.dispatchEvent(type, {
      pointerType: "touch",
      isPrimary: true,
      clientX,
      clientY: at.y,
    });
  await pointer("pointerdown", at.x);
  await pointer("pointermove", at.x - 120);
  await pointer("pointermove", at.x - 240);
  await pointer("pointerup", at.x - 240);
  await expect(toast(page)).toContainText("Dismissed");
  await expect.poll(() => triageOf(page, made[2].id)).toBe("dismissed");
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect.poll(() => triageOf(page, made[2].id)).toBe("new");
});
