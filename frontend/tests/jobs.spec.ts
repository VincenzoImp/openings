import { test, expect, type Page } from "@playwright/test";
import {
  call,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  type Cookies,
} from "./session";

// Jobs (stage 4 of #135): the tabs To review, Shortlist, Dismissed and All
// beside the selected job, its signals, the duplicate decision inside the job,
// rule dismissals that name their rule, and the yield of each source in
// Collection. The four projects share one server, so every test makes its own
// jobs, named after the project.
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
const toast = (page: Page) => page.locator(".app-toast").last();
const dialog = (page: Page) => page.locator("dialog[open]").last();
const detail = (page: Page) => page.locator(".job-detail");
const actions = (page: Page) =>
  page.getByRole("group", { name: "Actions on this job" });
// Safari moves through links with Option+Tab; the other browsers with Tab.
const tabKey = (page: Page) =>
  page.context().browser()?.browserType().name() === "webkit"
    ? "Alt+Tab"
    : "Tab";
const LONG =
  "Northwind Data builds forecasting tools for regional water networks. You will build and " +
  "run the pipelines that feed our demand forecasts, model sensor data in PostgreSQL and " +
  "work with analysts on data quality every week. We look for three years of data " +
  "engineering with Python and SQL, experience with a workflow scheduler and clear written " +
  "English. We offer a yearly learning budget, flexible hours and a quiet office near the " +
  "lake, with two days a week from home.";
const GERMAN =
  "Wir suchen eine Person für unser Team in Bern. Du entwickelst neue Funktionen in Python " +
  "und arbeitest eng mit unseren Kunden. Dein Profil: fließend Deutsch (C1) und gute " +
  "Englischkenntnisse. Wir bieten flexible Arbeitszeiten.";

async function settled(page: Page) {
  await page.waitForLoadState("load");
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.waitForTimeout(200);
  await expect(page.locator(".loading")).toHaveCount(0);
}
/** Press Tab until the focused element's text or label matches. */
async function tabTo(page: Page, name: RegExp, limit = 80) {
  for (let index = 0; index < limit; index++) {
    const text = await page.evaluate(
      () =>
        document.activeElement?.getAttribute("aria-label") ||
        document.activeElement?.textContent ||
        "",
    );
    if (name.test(text.trim())) return true;
    await page.keyboard.press(tabKey(page));
  }
  return false;
}
async function job(page: Page, title: string, fields: object = {}) {
  return call(page, "/jobs", "POST", {
    title,
    company: "Northwind Data",
    location: "Zurich, Switzerland",
    posting: `${title}. Build reliable services with a small team in Zurich.`,
    ...fields,
  });
}
async function agentToken(page: Page) {
  const token = await call(page, "/tokens", "POST", {
    name: unique("Jobs agent"),
    kind: "agent",
  });
  return token.token as string;
}
const row = (page: Page, title: string) =>
  page
    .locator(".job-list > li")
    .filter({ has: page.getByRole("link", { name: title, exact: true }) });

test("keyboard only: a job is shortlisted, another dismissed with a reason and restored", async ({
  page,
}) => {
  const tag = unique("Keyboard triage");
  const first = await job(page, `${tag} A`);
  const second = await job(page, `${tag} B`);
  await go(page, "jobs");
  await settled(page);
  const search = page.getByRole("searchbox", { name: "Search jobs" });
  await search.focus();
  await page.keyboard.type(tag);
  await expect(page.locator(".job-list > li")).toHaveCount(2);
  // From the search to the second job's title, then its page.
  expect(await tabTo(page, new RegExp(`^${tag} B$`))).toBe(true);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`job=${second.id}`));
  await expect(page.locator("#job-title")).toHaveText(`${tag} B`);
  expect(await tabTo(page, /^Shortlist$/)).toBe(true);
  await page.keyboard.press("Enter");
  await expect(toast(page)).toContainText("Shortlisted");
  await expect
    .poll(async () => (await call(page, `/jobs/${second.id}`)).triage)
    .toBe("saved");
  // The first job: dismissed from its page with a reason.
  await go(page, `jobs?job=${first.id}`);
  await settled(page);
  await actions(page).getByRole("button", { name: "Dismiss…" }).focus();
  await page.keyboard.press("Enter");
  await expect(dialog(page)).toBeVisible();
  await page.keyboard.type("Too far from home.");
  expect(await tabTo(page, /^Dismiss$/, 6)).toBe(true);
  await page.keyboard.press("Enter");
  await expect(toast(page)).toContainText("Dismissed");
  const dismissed = await call(page, `/jobs/${first.id}`);
  expect(dismissed.triage).toBe("dismissed");
  expect(dismissed.dismissal.reason).toBe("Too far from home.");
  expect(dismissed.dismissal.category).toBe("owner");
  // The Dismissed tab, by keyboard from the selected tab.
  await go(page, "jobs");
  await settled(page);
  await page.getByRole("tab", { name: /^To review/ }).focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /^Dismissed/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await search.fill(tag);
  const gone = row(page, `${tag} A`);
  await expect(gone).toContainText("Dismissed by you");
  await expect(gone).toContainText("Too far from home.");
  await gone.getByRole("button", { name: /^Restore/ }).focus();
  await page.keyboard.press("Enter");
  await expect(toast(page)).toContainText("Restored");
  const restored = await call(page, `/jobs/${first.id}`);
  expect(restored.triage).toBe("inbox");
  expect(restored.dismissal).toBeNull();
  await fitsViewport(page);
});

test("an enabled rule dismisses a collected job, names itself and the job can be restored", async ({
  page,
}) => {
  const token = await agentToken(page);
  const title = unique("Ruled out");
  const url = `https://jobs.example.test/ruled/${Date.now()}`;
  // An agent collects the job: the owner's language rule dismisses it at once.
  const collected = await call(
    page,
    "/jobs",
    "POST",
    { title, company: "Bergwerk AG", url, posting: GERMAN },
    token,
  );
  expect(collected.triage).toBe("dismissed");
  expect(collected.dismissal.rule.label).toBe("Languages outside my list");
  await go(page, "jobs?section=dismissed&dismissed_by=rule");
  await settled(page);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(title);
  const ruled = row(page, title);
  await expect(ruled).toContainText(
    "Dismissed by the rule “Languages outside my list”",
  );
  await expect(ruled).toContainText("Requires German");
  await ruled.getByRole("link", { name: title }).click();
  await expect(detail(page).locator(".banner")).toContainText(
    "Dismissed by the rule “Languages outside my list”",
  );
  // The rule in Policy says what it did and links to its dismissals.
  await go(page, "policy");
  await settled(page);
  const item = page
    .locator("li")
    .filter({ hasText: "Languages outside my list" })
    .first();
  await expect(item).toContainText(
    /It matches \d+ of the \d+ jobs? to review now/,
  );
  await item.getByRole("link", { name: /jobs? dismissed by it$/ }).click();
  await expect(page).toHaveURL(/#jobs\?section=dismissed&rule_id=/);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(title);
  await row(page, title)
    .getByRole("button", { name: /^Restore/ })
    .click();
  await expect(toast(page)).toContainText("Restored");
  // Restored stays restored when the source sees the posting again.
  const again = await call(
    page,
    "/jobs",
    "POST",
    { title, company: "Bergwerk AG", url, posting: GERMAN },
    token,
  );
  expect(again.triage).toBe("inbox");
  expect(again.dismissal).toBeNull();
});

test("a likely duplicate is decided inside the job: different, then merged", async ({
  page,
}) => {
  const tag = unique("Duplicate");
  const earlier = await job(page, `${tag} Data Engineer`, {
    posting: LONG,
    url: `https://jobs.example.test/dup/${Date.now()}/a`,
  });
  const copy = await job(page, `${tag} Data Engineer`, {
    posting: LONG,
    url: `https://jobs.example.test/dup/${Date.now()}/b`,
  });
  expect(copy.signals.duplicate.job_id).toBe(earlier.id);
  await go(page, `jobs?signal=likely_duplicate&job=${copy.id}`);
  await settled(page);
  // On a phone the selected job replaces the list.
  if (!isNarrow(page))
    await expect(row(page, copy.title)).toContainText("Likely duplicate");
  const box = detail(page).locator(".duplicate");
  await expect(box).toContainText(earlier.title);
  await expect(box).toContainText("identical posting text");
  await box.getByRole("button", { name: "Different", exact: true }).click();
  await expect(toast(page)).toContainText("different vacancy");
  await expect(box).toHaveCount(0);
  expect((await call(page, `/jobs/${copy.id}`)).signals.duplicate).toBeNull();
  // A third copy: merged into the earlier record, which stays.
  const third = await job(page, `${tag} Data Engineer`, {
    posting: LONG,
    url: `https://jobs.example.test/dup/${Date.now()}/c`,
  });
  await go(page, `jobs?job=${third.id}`);
  await settled(page);
  await detail(page)
    .getByRole("button", { name: "Same vacancy: merge", exact: true })
    .click();
  await expect(dialog(page)).toContainText("Which record stays?");
  await dialog(page)
    .getByRole("button", { name: "Merge", exact: true })
    .click();
  await expect(toast(page)).toContainText("Merged");
  await expect(page).toHaveURL(new RegExp(`job=${earlier.id}`));
  await expect(page.locator("#job-title")).toHaveText(earlier.title);
  const kept = await call(page, `/jobs/${earlier.id}`);
  expect(kept.postings).toHaveLength(2);
  const lookup = await call(
    page,
    `/jobs?q=${encodeURIComponent(tag)}&limit=10`,
  );
  expect(lookup.items.map((item: { id: string }) => item.id).sort()).toEqual(
    [copy.id, earlier.id].sort(),
  );
});

test("adding a job by its address finds the one already in the workspace", async ({
  page,
}) => {
  const url = `https://jobs.example.test/known/${Date.now()}`;
  const known = await job(page, unique("Known role"), { url });
  await go(page, "jobs");
  await page.getByRole("button", { name: "Add a job" }).click();
  await dialog(page).getByLabel("Address of the posting").fill(url);
  await dialog(page).getByLabel("Role").focus();
  await expect(dialog(page).locator(".banner")).toContainText(
    "Already in your workspace",
  );
  await dialog(page).getByRole("button", { name: "Open it" }).click();
  await expect(page.locator("#job-title")).toHaveText(known.title);
  // A new posting, pasted: it opens beside the list.
  const title = unique("Pasted role");
  await page.getByRole("button", { name: "Add a job" }).click();
  await dialog(page).getByLabel("Role").fill(title);
  await dialog(page).getByLabel("Company").fill("Northwind Data");
  await dialog(page)
    .getByLabel("Posting text")
    .fill("Build reliable services with a small team in Zurich.");
  await dialog(page).getByRole("button", { name: "Add the job" }).click();
  await expect(toast(page)).toContainText("Job added");
  await expect(page.locator("#job-title")).toHaveText(title);
  await expect(page.locator("dialog[open]")).toHaveCount(0);
});

test("bulk actions shortlist, return and forget selected jobs after asking", async ({
  page,
}) => {
  const tag = unique("Bulk");
  const jobs = [
    await job(page, `${tag} one`),
    await job(page, `${tag} two`),
    await job(page, `${tag} three`),
  ];
  await go(page, "jobs");
  await settled(page);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(tag);
  await expect(page.locator(".job-list > li")).toHaveCount(3);
  await page.getByRole("checkbox", { name: "Select every job shown" }).check();
  const bar = page.getByRole("group", { name: "Selected jobs" });
  await expect(bar).toContainText("3 selected");
  await bar.getByRole("button", { name: "Shortlist", exact: true }).click();
  await expect(toast(page)).toContainText("Jobs updated");
  await expect(page.locator(".job-list > li")).toHaveCount(0);
  await page.getByRole("tab", { name: /^Shortlist/ }).click();
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(tag);
  await expect(page.locator(".job-list > li")).toHaveCount(3);
  await row(page, `${tag} one`).getByRole("checkbox").check();
  await bar.getByRole("button", { name: "Forget…", exact: true }).click();
  await expect(dialog(page)).toContainText("removed for good");
  await dialog(page).getByRole("button", { name: "Keep them" }).click();
  await bar.getByRole("button", { name: "Forget…", exact: true }).click();
  await dialog(page).getByRole("button", { name: "Forget 1 job" }).click();
  await expect(toast(page)).toContainText("Jobs forgotten");
  await expect(page.locator(".job-list > li")).toHaveCount(2);
  await page.getByRole("checkbox", { name: "Select every job shown" }).check();
  await bar.getByRole("button", { name: "Return to review" }).click();
  await expect(page.locator(".job-list > li")).toHaveCount(0);
  for (const item of jobs.slice(1))
    expect((await call(page, `/jobs/${item.id}`)).triage).toBe("inbox");
});

test("signals filter the list and Collection shows what each source yielded", async ({
  page,
}) => {
  await go(page, "jobs");
  await settled(page);
  await page
    .getByRole("combobox", { name: "Filter by signal" })
    .selectOption("no_longer_listed");
  const rows = page.locator(".job-list > li");
  await expect(rows.first()).toContainText("No longer listed");
  const listed = await call(page, "/jobs?queue=inbox&signal=no_longer_listed");
  await expect(rows).toHaveCount(listed.total);
  // The tabs keep their counts from the workspace.
  const counts = (await call(page, "/jobs?limit=1&include_counts=true")).counts;
  await expect(page.getByRole("tab", { name: /^To review/ })).toContainText(
    String(counts.inbox),
  );
  await go(page, "collection?section=yield");
  await settled(page);
  const table = page.getByRole("table", { name: "Yield by source" });
  await expect(table).toContainText("Python engineer Zurich");
  const yieldNow = await call(
    page,
    "/collection/yield?since=" +
      new Date(Date.now() - 90 * 86_400_000).toISOString().slice(0, 10),
  );
  await expect(table.getByRole("row").last()).toContainText(
    String(yieldNow.total.collected),
  );
  await page.getByRole("button", { name: "All time" }).click();
  await settled(page);
  await expect(table).toBeVisible();
  const dismissedByRule = page
    .getByRole("list", { name: "Jobs each rule dismissed" })
    .getByRole("link")
    .first();
  // Clear of the bottom bar of a phone before the click.
  await dismissedByRule.evaluate((link) =>
    link.scrollIntoView({ block: "center" }),
  );
  await dismissedByRule.click();
  await expect(page).toHaveURL(/#jobs\?section=dismissed&rule_id=/);
  await expect(page.locator(".job-list > li").first()).toContainText(
    "Dismissed by the rule",
  );
  await fitsViewport(page);
});

test("on a phone the selected job replaces the list until the switch shows it", async ({
  page,
}) => {
  test.skip(!isNarrow(page), "The switch exists on narrow screens.");
  const title = unique("Phone role");
  await job(page, title);
  await go(page, "jobs");
  await settled(page);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(title);
  await row(page, title).getByRole("link", { name: title }).click();
  await expect(page.locator("#job-title")).toBeFocused();
  await expect(page.locator(".job-list")).toBeHidden();
  await page.getByRole("button", { name: "List", exact: true }).click();
  await expect(page.locator(".job-list")).toBeVisible();
  await expect(page.locator(".job-detail")).toBeHidden();
  await fitsViewport(page);
});

test("a note is edited, an application started and a job forgotten from its page", async ({
  page,
}) => {
  const tag = unique("Own page");
  const kept = await job(page, `${tag} kept`);
  const gone = await job(page, `${tag} gone`);
  await go(page, `jobs?job=${kept.id}`);
  await settled(page);
  await detail(page).getByLabel("A note on this job").fill("First thought.");
  await detail(page)
    .getByRole("button", { name: "Add the note", exact: true })
    .click();
  const timeline = detail(page).getByRole("list", {
    name: "Timeline of this job",
  });
  await timeline.getByRole("button", { name: "Edit this note" }).click();
  await dialog(page).getByLabel("Note").fill("Second thought.");
  await dialog(page).getByRole("button", { name: "Save the note" }).click();
  await expect(timeline).toContainText("Second thought.");
  // Shortlisted, then started: the review page of the new application opens.
  await actions(page).getByRole("button", { name: "Shortlist" }).click();
  await expect(toast(page)).toContainText("Shortlisted");
  await actions(page)
    .getByRole("button", { name: "Start application", exact: true })
    .click();
  await expect(page).toHaveURL(/#review\?application=/);
  await expect(page.locator(".main h1")).toHaveText(kept.title);
  // Forgetting asks first and removes the job for good.
  await go(page, `jobs?section=all&job=${gone.id}`);
  await settled(page);
  await detail(page)
    .getByRole("button", { name: "Forget this job permanently" })
    .click();
  await expect(dialog(page)).toContainText("removed for good");
  await dialog(page).getByRole("button", { name: "Forget the job" }).click();
  await expect(toast(page)).toContainText("removed");
  await expect(page).not.toHaveURL(/job=/);
  const left = await call(page, `/jobs?q=${encodeURIComponent(tag)}`);
  expect(left.items.map((item: { id: string }) => item.id)).toEqual([kept.id]);
});
