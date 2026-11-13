import { test, expect, type Page } from "./fixtures";
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
// hiding jobs that require a language the owner does not speak, and the yield
// of each source in Collection. Each test starts from the seeded workspace (fixtures.ts).
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

test("jobs requiring a language I don't speak are hidden on request, never dismissed", async ({
  page,
}) => {
  const token = await agentToken(page);
  const title = unique("Bergwerk role");
  const url = `https://jobs.example.test/german/${Date.now()}`;
  // An agent collects the job: it stays to review, with its requirement.
  const collected = await call(
    page,
    "/jobs",
    "POST",
    { title, company: "Bergwerk AG", url, posting: GERMAN },
    token,
  );
  expect(collected.triage).toBe("inbox");
  expect(collected.dismissal).toBeNull();
  await go(page, "jobs");
  await settled(page);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(title);
  const german = row(page, title);
  await expect(german).toContainText("Requires German");
  const toggle = page.getByRole("switch", {
    name: "Hide jobs requiring languages I don't speak",
  });
  await expect(toggle).not.toBeChecked();
  const chips = page.locator(".queue-chips").filter({ has: toggle });
  await expect(chips).toContainText("would hide 1 of 1");
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(page).toHaveURL(/hide_unspoken=true/);
  await expect(german).toHaveCount(0);
  await expect(chips).toContainText("hides 1 of 1");
  await expect(page.getByText("No job matches")).toBeVisible();
  // Hiding changes nothing about the job.
  expect((await call(page, `/jobs/${collected.id}`)).triage).toBe("inbox");
  // The setting holds across the tabs, and turns off again.
  await page.getByRole("tab", { name: /^All/ }).click();
  await expect(toggle).toBeChecked();
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(title);
  await expect(german).toHaveCount(0);
  await toggle.click();
  await expect(german).toBeVisible();
  // Without spoken languages there is nothing to hide: Preferences says which.
  const settings = (await call(page, "/preferences")).settings;
  await call(page, "/settings", "PATCH", {
    expected_version: settings.version,
    spoken_languages: [],
  });
  await page.reload();
  await settled(page);
  await expect(toggle).toHaveCount(0);
  await expect(
    page.locator(".queue-chips").getByRole("link", { name: "Preferences" }),
  ).toHaveAttribute("href", "#preferences");
  await fitsViewport(page);
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
  await expect(page.getByText("Dismissed by your rules")).toHaveCount(0);
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
  // Pinned, the note leads the timeline; changes stay listed below it.
  await timeline.getByRole("button", { name: "Pin this note" }).click();
  await expect(timeline.getByRole("listitem").first()).toContainText(
    "Pinned note",
  );
  await expect(timeline).toContainText("Collected");
  // Shortlisted, then started: the review page of the new application opens.
  await actions(page).getByRole("button", { name: "Shortlist" }).click();
  await expect(toast(page)).toContainText("Shortlisted");
  // The job left To review; the Shortlist shows it.
  await expect(page).not.toHaveURL(new RegExp(`job=${kept.id}`));
  await go(page, `jobs?section=shortlist&job=${kept.id}`);
  await settled(page);
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

test("after a triage the next job of the list is shown, or the previous one at the end", async ({
  page,
}) => {
  const tag = unique("Next after triage");
  for (const name of ["A", "B", "C"]) await job(page, `${tag} ${name}`);
  await go(page, "jobs?section=review");
  await settled(page);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(tag);
  const links = page.locator(".job-list > li .title");
  await expect(links).toHaveCount(3);
  const order = await links.allTextContents();
  const id = async (title: string) =>
    (await call(page, `/jobs?q=${encodeURIComponent(tag)}`)).items.find(
      (item: { title: string }) => item.title === title,
    ).id;
  // From the pane: the first job is shortlisted, the second one shows.
  await row(page, order[0]).getByRole("link", { name: order[0] }).click();
  await expect(page.locator("#job-title")).toHaveText(order[0]);
  await actions(page).getByRole("button", { name: "Shortlist" }).click();
  await expect(toast(page)).toContainText("Shortlisted");
  await expect(page).toHaveURL(new RegExp(`job=${await id(order[1])}`));
  await expect(page.locator("#job-title")).toHaveText(order[1]);
  await expect(links).toHaveCount(2);
  // From the last row: it is dismissed, the one before it shows.
  if (isNarrow(page))
    await page.getByRole("button", { name: "List", exact: true }).click();
  await row(page, order[2]).getByRole("link", { name: order[2] }).click();
  await expect(page.locator("#job-title")).toHaveText(order[2]);
  if (isNarrow(page))
    await page.getByRole("button", { name: "List", exact: true }).click();
  await row(page, order[2])
    .getByRole("button", { name: /^Dismiss/ })
    .click();
  await expect(toast(page)).toContainText("Dismissed");
  await expect(page).toHaveURL(new RegExp(`job=${await id(order[1])}`));
  await expect(page.locator("#job-title")).toHaveText(order[1]);
  // The last one left: dismissed from the pane, nothing is selected.
  if (isNarrow(page))
    await page
      .getByRole("button", { name: "Selected job", exact: true })
      .click();
  await actions(page).getByRole("button", { name: "Dismiss…" }).click();
  await dialog(page)
    .getByRole("button", { name: "Dismiss", exact: true })
    .click();
  await expect(toast(page)).toContainText("Dismissed");
  await expect(page).not.toHaveURL(/job=/);
  await expect(links).toHaveCount(0);
});

test("on a phone the job's actions stay above the bottom bar and the toast", async ({
  page,
}) => {
  test.skip(!isNarrow(page), "The fixed action bar is for narrow screens.");
  const tag = unique("Phone actions");
  await job(page, `${tag} A`);
  await job(page, `${tag} B`);
  await go(page, "jobs?section=review");
  await settled(page);
  await page.getByRole("searchbox", { name: "Search jobs" }).fill(tag);
  await expect(page.locator(".job-list > li")).toHaveCount(2);
  await page.locator(".job-list > li .title").first().click();
  await expect(page.locator("#job-title")).toBeVisible();
  const nav = (await page
    .getByRole("navigation", { name: "Main" })
    .boundingBox())!;
  const bar = actions(page);
  const inReach = async () => {
    const box = (await bar.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(nav.y + 1);
    expect(box.y).toBeGreaterThan(0);
    for (const name of ["Shortlist", "Dismiss…"]) {
      const button = (await bar
        .getByRole("button", { name, exact: true })
        .boundingBox())!;
      expect(button.y + button.height).toBeLessThanOrEqual(nav.y + 1);
    }
    return box;
  };
  await inReach();
  await bar.getByRole("button", { name: "Shortlist", exact: true }).click();
  await expect(toast(page)).toContainText("Shortlisted");
  // The next job shows; the toast sits above its action bar, covering nothing.
  const box = await inReach();
  const message = (await toast(page).boundingBox())!;
  expect(message.y + message.height).toBeLessThanOrEqual(box.y + 1);
  await expect(page.getByRole("button", { name: "Add a note" })).toBeVisible();
  await fitsViewport(page);
});

test("the tab strip scrolls on a phone and keeps the selected tab in view", async ({
  page,
}) => {
  await go(page, "jobs");
  await settled(page);
  const strip = page.getByRole("tablist", { name: "Jobs by triage state" });
  const all = strip.getByRole("tab", { name: /^All/ });
  await all.click();
  await expect(all).toHaveAttribute("aria-selected", "true");
  const width = page.viewportSize()!.width;
  await expect
    .poll(async () => {
      const box = (await all.boundingBox())!;
      return box.x >= 0 && box.x + box.width <= width;
    })
    .toBe(true);
  await fitsViewport(page);
});
