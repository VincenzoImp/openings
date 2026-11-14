import { test, expect, type Page } from "./fixtures";
import {
  call,
  fitsViewport,
  go,
  isPhone,
  ownerSession,
  type Cookies,
} from "./session";

// Today, the first screen, on the synthetic workspace of
// backend/tests/today_fixtures.py: Ready applications with deadlines, sent
// ones of different ages and new jobs. Each test starts from the seeded
// workspace (fixtures.ts).
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

/** A section of Today, by its heading (which ends with its count). */
const section = (page: Page, name: string) =>
  page.getByRole("region", { name: new RegExp(`^${name}`) });
const rows = (page: Page, list: string) =>
  page.getByRole("region", { name: list }).getByRole("listitem");
const toast = (page: Page) => page.locator(".ui-toast").last();
const localDay = (offset = 0) => {
  const day = new Date();
  day.setDate(day.getDate() + offset);
  return [
    day.getFullYear(),
    String(day.getMonth() + 1).padStart(2, "0"),
    String(day.getDate()).padStart(2, "0"),
  ].join("-");
};
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
}

test("Today says what to do now, with one filled button, and Start applying opens the first Ready application", async ({
  page,
}) => {
  await go(page, "today");
  await expect(page).toHaveTitle("Today · Openings");
  await settled(page);
  const ready = await call(
    page,
    "/applications?stage=ready&sort=deadline&limit=5",
  );
  const jobs = await call(page, "/jobs?triage=new&limit=1");
  expect(ready.total).toBeGreaterThan(5);

  // One line under the title: only what is not zero.
  const summary = page.locator(".today-summary");
  await expect(summary).toContainText(`${ready.total} ready to apply`);
  await expect(summary).toContainText(`${jobs.total} new jobs`);

  // Ready to apply: closest deadline first, five rows, the rest behind a link.
  const readyRows = rows(page, "Ready applications");
  await expect(readyRows).toHaveCount(5);
  for (const [index, application] of ready.items.entries())
    await expect(readyRows.nth(index)).toContainText(application.job.title);
  await expect(
    readyRows.filter({ hasText: "Python Engineer" }).locator(".ui-tone"),
  ).toHaveText("Closes tomorrow");
  await expect(
    readyRows.filter({ hasText: "Python Engineer" }).getByRole("img", {
      name: "Priority 1",
    }),
  ).toBeVisible();
  await expect(
    section(page, "Ready to apply").getByRole("link", {
      name: `All ${ready.total} ready applications`,
    }),
  ).toHaveAttribute("href", "#applications?stage=ready");
  // At most one filled button, and no button on a row at rest.
  await expect(
    page.locator("#content .ui-btn[data-variant=primary]:visible"),
  ).toHaveCount(1);
  await expect(page.locator("#content .ui-row-actions:visible")).toHaveCount(0);

  // The stage strip: a count per stage, each a link to its list.
  const counts = ready.stage_counts;
  const strip = page.getByRole("navigation", {
    name: "Applications by stage",
  });
  await expect(strip.getByRole("link")).toHaveText([
    `${counts.shortlisted - counts.ready}Shortlisted`,
    `${counts.ready}Ready`,
    `${counts.applied}Applied`,
    `${counts.interview}Interview`,
    `${counts.offer}Offer`,
  ]);
  await expect(strip.getByRole("link", { name: /Interview$/ })).toHaveAttribute(
    "href",
    "#applications?stage=interview",
  );

  // New jobs: the first three, and the way to go through them.
  await expect(
    page.getByRole("list", { name: "Newest jobs" }).getByRole("listitem"),
  ).toHaveCount(3);
  await fitsViewport(page);

  await page.getByRole("button", { name: "Start applying" }).click();
  await expect(page).toHaveURL(
    new RegExp(`#applications/${ready.items[0].id}$`),
  );
  await go(page, "today");
  await section(page, "New jobs")
    .getByRole("button", { name: "Go through them" })
    .click();
  await expect(page).toHaveURL(/#jobs$/);
});

test("a shortlisted application due this week names what it still needs", async ({
  page,
}) => {
  await go(page, "today");
  const title = `Attention ${test.info().project.name} ${Date.now()}`;
  const job = await call(page, "/jobs", "POST", {
    title,
    company: "Example Labs",
    location: "Zurich",
    posting: `${title} at Example Labs.`,
  });
  const application = await call(page, "/applications", "POST", {
    job_id: job.id,
    deadline: localDay(3),
    required_documents: ["cv", "letter"],
  });
  await page.reload();
  await settled(page);
  const row = rows(page, "Applications that need attention").filter({
    hasText: title,
  });
  await expect(row.locator(".ui-tone-warning")).toHaveText(
    "Missing: CV and letter",
  );
  await row.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`#applications/${application.id}$`));
});

test("waiting for a reply: close one with c, undo, record a reply with r, close all and undo", async ({
  page,
}) => {
  await go(page, "today");
  await settled(page);
  const waiting = await call(
    page,
    "/applications?needs=reply_overdue&sort=applied&limit=200",
  );
  expect(waiting.total).toBeGreaterThanOrEqual(3);
  const overdue = async () =>
    (await call(page, "/applications?needs=reply_overdue&limit=1")).total;
  const list = rows(page, "Applications waiting for a reply");
  await expect(list).toHaveCount(Math.min(waiting.total, 5));
  await expect(page.locator(".today-note")).toContainText(
    `No reply after ${waiting.no_reply.days} days`,
  );

  // The first row is the list's Tab stop; c closes it as no reply.
  const first = waiting.items[0];
  await list.first().getByRole("link").focus();
  await page.keyboard.press("c");
  await expect(toast(page)).toContainText(
    `Closed “${first.job.title}” as no reply`,
  );
  await expect.poll(overdue).toBe(waiting.total - 1);
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect.poll(overdue).toBe(waiting.total);

  // r records the employer's reply; an invitation moves it to Interview.
  await expect(list).toHaveCount(Math.min(waiting.total, 5));
  await list.first().getByRole("link").focus();
  await page.keyboard.press("r");
  const dialog = page.getByRole("dialog", { name: "Record reply" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("What happened")).toHaveValue("interview");
  await dialog.getByLabel("Note").fill("A synthetic first call.");
  await dialog.getByRole("button", { name: "Record reply" }).click();
  await expect(dialog).toBeHidden();
  await expect(toast(page)).toContainText("Recorded the reply");
  await expect
    .poll(async () => (await call(page, `/applications/${first.id}`)).status)
    .toBe("interview");
  await expect.poll(overdue).toBe(waiting.total - 1);

  // Close all of them as no reply, then undo.
  const left = waiting.total - 1;
  await section(page, "Waiting for a reply")
    .getByRole("button", { name: `Close all ${left} as no reply` })
    .click();
  await expect(toast(page)).toContainText(
    `Closed ${left} applications as no reply`,
  );
  await expect.poll(overdue).toBe(0);
  await expect(section(page, "Waiting for a reply")).toHaveCount(0);
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect.poll(overdue).toBe(left);
  await expect(list).toHaveCount(Math.min(left, 5));
  await fitsViewport(page);
});

test("the setup checklist comes from server facts: two browsers agree", async ({
  page,
  browser,
  baseURL,
}) => {
  await go(page, "today");
  // Take what the person looks for out of the workspace: no name, no
  // Preferences. Jobs and career entries stay, so 2 of 3 are done.
  const profile = await call(page, "/career/profile");
  await call(page, "/career/profile", "PATCH", {
    expected_version: profile.version,
    name: "",
  });
  const preferences = await call(page, "/preferences");
  for (const item of preferences.sections)
    await call(page, `/preferences/${item.section}`, "PUT", {
      expected_version: item.version,
      items: [],
    });

  const other = await browser.newContext({
    baseURL,
    viewport: page.viewportSize()!,
  });
  await other.addCookies(cookies);
  const second = await other.newPage();
  for (const view of [page, second]) {
    await go(view, "today");
    const checklist = section(view, "Set up your workspace");
    await expect(checklist).toContainText("2 of 3 done");
    await expect(
      checklist.getByRole("listitem").filter({ hasText: "Add your CV" }),
    ).toContainText("Done");
    // Beside applications the checklist is secondary: Start applying leads.
    await expect(
      view.locator("#content .ui-btn[data-variant=primary]:visible"),
    ).toHaveCount(1);
  }
  if (!isPhone(page))
    await expect(
      page.getByRole("navigation", { name: "Main" }).getByRole("link", {
        name: "Finish setup",
      }),
    ).toBeVisible();

  // The first item opens the guide on About you; finishing it is enough.
  await section(page, "Set up your workspace")
    .getByRole("button", { name: "Start" })
    .click();
  await expect(page).toHaveURL(/#setup\?step=about$/);
  await page.getByLabel("Your name").fill("Alex Example");
  await page.getByLabel("Roles you're after").fill("data engineer");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/#setup\?step=jobs$/);

  for (const view of [page, second]) {
    await go(view, "today");
    await expect(section(view, "Set up your workspace")).toHaveCount(0);
    await expect(view.getByRole("link", { name: "Finish setup" })).toHaveCount(
      0,
    );
  }
  await other.close();
});
