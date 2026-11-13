import { test, expect, type Page } from "./fixtures";
import {
  attachSource,
  call,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  syntheticPdf,
  syntheticTex,
  type Cookies,
} from "./session";

// Applications (stage 3 of #135): the pipeline as a list and a board, the
// employer's responses, bulk actions, Insights and the review page with its
// tabs. Each test starts from the seeded workspace (fixtures.ts).
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
const localDay = (offset = 0) => {
  const day = new Date(Date.now() + offset * 86_400_000);
  return [
    day.getFullYear(),
    String(day.getMonth() + 1).padStart(2, "0"),
    String(day.getDate()).padStart(2, "0"),
  ].join("-");
};
const toast = (page: Page) => page.locator(".app-toast").last();
/** The Ready applications in Today's order, as the review page reads them. */
const READY_QUEUE =
  "/applications?status=draft&ready=true&sort=deadline&limit=200";
/** The one opened after `id` is marked applied. */
const nextOf = (queue: { id: string }[], id: string) => {
  const index = queue.findIndex((item) => item.id === id);
  const others = queue.filter((item) => item.id !== id);
  return index < 0 ? others[0] : queue[index + 1] || others[0];
};
const dialog = (page: Page) => page.locator("dialog[open]").last();
// Safari moves through links with Option+Tab; the other browsers with Tab.
const tabKey = (page: Page) =>
  page.context().browser()?.browserType().name() === "webkit"
    ? "Alt+Tab"
    : "Tab";

interface Options {
  company?: string;
  status?: string;
  ready?: boolean;
  questions?: unknown[];
  requirements?: unknown[];
  priority?: number;
  deadline?: string;
  appliedDaysAgo?: number;
}
/** A job and its application, set up through the API as the test's own data. */
async function make(page: Page, title: string, options: Options = {}) {
  const job = await call(page, "/jobs", "POST", {
    title,
    company: options.company || "Example Labs",
    location: "Zurich, Switzerland",
    posting: `${title} at Example Labs.\n\nBuild reliable services with a small team.`,
  });
  let application = await call(page, "/applications", "POST", {
    job_id: job.id,
    questions: options.questions || [],
    requirements: options.requirements || [],
    priority: options.priority,
    deadline: options.deadline,
  });
  if (options.ready) {
    for (const kind of ["resume", "cover_letter"]) {
      const document = await call(page, "/documents", "POST", {
        application_id: application.id,
        kind,
        title: kind === "resume" ? "CV" : "Letter",
      });
      await attachSource(page, document.id, "Synthetic text.", kind);
      const current = await call(page, `/documents/${document.id}`);
      await call(page, `/documents/${document.id}/review`, "POST", {
        review_state: "approved",
        expected_version: current.version,
      });
    }
    application = await call(page, `/applications/${application.id}`);
    application = await call(
      page,
      `/applications/${application.id}/ready`,
      "POST",
      {
        expected_version: application.version,
      },
    );
  }
  if (options.status) {
    application = await call(page, `/applications/${application.id}`, "PATCH", {
      expected_version: application.version,
      status: options.status,
      ...(options.appliedDaysAgo !== undefined
        ? {
            // Calendar days, as the dashboard counts them: 50 × 24 h can be
            // 49 local days across a daylight saving change.
            applied_at: (() => {
              const day = new Date();
              day.setDate(day.getDate() - options.appliedDaysAgo);
              return day.toISOString();
            })(),
          }
        : {}),
    });
  }
  return call(page, `/applications/${application.id}`);
}
/**
 * The screen has read its records. Not "networkidle": a browser without a PDF
 * viewer never finishes the request of a PDF shown in a frame.
 */
async function settled(page: Page) {
  await page.waitForLoadState("load");
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.waitForTimeout(250);
  await expect(page.locator(".loading")).toHaveCount(0);
}
const row = (page: Page, title: string) =>
  page
    .getByRole("row")
    .filter({ has: page.getByRole("link", { name: title, exact: true }) });

test("keyboard only: a ready application is reviewed from Today and marked applied", async ({
  page,
}) => {
  const title = unique("Keyboard review");
  const application = await make(page, title, {
    ready: true,
    deadline: localDay(0),
    priority: 1,
    questions: [{ id: "why", label: "Why this team?", required: true }],
    requirements: [{ kind: "deadline", text: "Send it before Friday." }],
  });
  // Today is open already: read it again with the new application.
  await page.reload();
  await settled(page);
  // Move to the Review link of this application with the keyboard alone.
  const reached = async (name: RegExp) => {
    for (let index = 0; index < 120; index++) {
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
  };
  expect(await reached(new RegExp(`^Review ${title}$`))).toBe(true);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(
    new RegExp(`#review\\?application=${application.id}$`),
  );
  await expect(page.locator(".main h1")).toHaveText(title);
  await expect(page.getByText(/of \d+ ready/)).toBeVisible();
  const before = page
    .locator(".banner")
    .filter({ hasText: "Before you send:" });
  await expect(before).toContainText('"Why this team?"');
  await expect(before).toContainText("Send it before Friday.");
  // Both PDFs are shown beside the posting.
  await expect(page.locator("iframe.frame")).toHaveCount(2);
  await settled(page);
  expect(await reached(/^Mark applied$/)).toBe(true);
  // The next Ready application in Today's order is opened next.
  const queue = await call(page, READY_QUEUE);
  const next = nextOf(queue.items, application.id);
  await page.keyboard.press("Enter");
  await expect(toast(page)).toContainText("Marked applied");
  await expect
    .poll(
      async () => (await call(page, `/applications/${application.id}`)).status,
    )
    .toBe("applied");
  if (next)
    await expect(page).toHaveURL(
      new RegExp(`#review\\?application=${next.id}$`),
    );
  else await expect(page.getByText("All sent.")).toBeVisible();
  const sent = await call(page, `/applications/${application.id}`);
  expect(sent.applied_at).toBeTruthy();
  // The Ready history stays in the timeline.
  const history = await call(page, `/applications/${application.id}/events`);
  expect(history.items.map((event: any) => event.kind)).toContain(
    "application_marked_ready",
  );
  await go(page, `review?application=${application.id}`);
  await expect(
    page.getByRole("button", { name: "Record response" }).first(),
  ).toBeVisible();
  await fitsViewport(page);
});

test("after Mark applied the next Ready application opens, with Undo", async ({
  page,
}) => {
  const prefix = unique("Send next");
  // A deadline before every other Ready application: these two lead the queue.
  const first = await make(page, `${prefix} first`, {
    ready: true,
    deadline: "2000-01-01",
  });
  const second = await make(page, `${prefix} second`, {
    ready: true,
    deadline: "2000-01-02",
  });
  await go(page, `review?application=${first.id}`);
  await settled(page);
  await page.getByRole("button", { name: "Mark applied" }).first().click();
  await expect(page).toHaveURL(
    new RegExp(`#review\\?application=${second.id}$`),
  );
  await expect(page.locator(".main h1")).toHaveText(`${prefix} second`);
  await expect(toast(page)).toContainText("Marked applied.");
  const sent = await call(page, `/applications/${first.id}`);
  expect([sent.status, !!sent.applied_at]).toEqual(["applied", true]);
  // Undo: back to the first one, Preparing and Ready again, never sent.
  await toast(page).getByRole("button", { name: "Undo" }).click();
  await expect(page).toHaveURL(
    new RegExp(`#review\\?application=${first.id}$`),
  );
  await expect
    .poll(async () => {
      const back = await call(page, `/applications/${first.id}`);
      return [back.status, back.applied_at, back.readiness];
    })
    .toEqual(["draft", null, "ready"]);
  await expect(
    page.getByRole("button", { name: "Mark applied" }).first(),
  ).toBeVisible();
  // The last one: no other application is ready, so the page says so.
  await page.route(
    /\/api\/v1\/applications\?status=draft&ready=true/,
    (route) => route.fulfill({ json: { items: [first], total: 1 } }),
  );
  await page.getByRole("button", { name: "Mark applied" }).first().click();
  await expect(page.getByText("All sent.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Today" })).toBeVisible();
  await expect(page).toHaveURL(
    new RegExp(`#review\\?application=${first.id}$`),
  );
  await expect(
    page.getByRole("button", { name: "Record response" }).first(),
  ).toBeVisible();
  await page.unroute(/\/api\/v1\/applications\?status=draft&ready=true/);
  // The second one leaves the queue, so the next project starts from its own.
  const left = await call(page, `/applications/${second.id}`);
  await call(page, `/applications/${second.id}`, "PATCH", {
    expected_version: left.version,
    status: "closed",
    outcome: "not_pursued",
  });
  // A confirmation goes by itself; an error stays until it is closed.
  await page.mouse.move(0, 0);
  await expect(toast(page)).toHaveCount(0, { timeout: 9000 });
  await fitsViewport(page);
});

test("the response dialog lays its fields out one under the other, without an earlier toast", async ({
  page,
}) => {
  const application = await make(page, unique("Dialog layout"), {
    ready: true,
  });
  // Stay on this page after Mark applied: it is the only Ready one here.
  await page.route(
    /\/api\/v1\/applications\?status=draft&ready=true/,
    (route) => route.fulfill({ json: { items: [application], total: 1 } }),
  );
  await go(page, `review?application=${application.id}`);
  await settled(page);
  await page.getByRole("button", { name: "Mark applied" }).first().click();
  await expect(toast(page)).toContainText("Marked applied.");
  await page.unroute(/\/api\/v1\/applications\?status=draft&ready=true/);
  await page.getByRole("button", { name: "Record response" }).first().click();
  const box = dialog(page);
  await expect(box).toBeVisible();
  // The confirmation from before the dialog is gone, inside it and outside.
  await expect(page.locator(".app-toast")).toHaveCount(0);
  const form = box.getByRole("form", {
    name: /Record the employer's response/,
  });
  const body = (await box.locator(".dialog-body").boundingBox())!;
  const note = (await form.getByLabel("Note").boundingBox())!;
  const date = (await form.getByLabel("Date of the answer").boundingBox())!;
  const choice = (await form.getByRole("group").first().boundingBox())!;
  // Choice, date, note: one under the other, the note as wide as the form.
  expect(date.y).toBeGreaterThan(choice.y + choice.height - 1);
  expect(note.y).toBeGreaterThan(date.y + date.height - 1);
  expect(note.width).toBeGreaterThan(body.width * 0.75);
  const cancel = (await form
    .getByRole("button", { name: "Cancel" })
    .boundingBox())!;
  const save = (await form
    .getByRole("button", { name: "Save and move to Interview" })
    .boundingBox())!;
  // The buttons come after the note, Cancel before the main one, at the end.
  expect(cancel.y).toBeGreaterThan(note.y + note.height - 1);
  expect(save.x).toBeGreaterThan(cancel.x);
  expect(body.x + body.width - (save.x + save.width)).toBeLessThan(40);
  await form.getByLabel("Note").fill("Call with the team lead.");
  await form
    .getByRole("button", { name: "Save and move to Interview" })
    .click();
  await expect(box).toHaveCount(0);
  await expect(toast(page)).toContainText("Response saved.");
  await expect
    .poll(
      async () => (await call(page, `/applications/${application.id}`)).status,
    )
    .toBe("interview");
});

test("an inline response form closes when the stage changes", async ({
  page,
}) => {
  const title = unique("Inline form");
  await make(page, title, { status: "applied" });
  await go(page, `applications?stage=applied&q=${encodeURIComponent(title)}`);
  await settled(page);
  await row(page, title)
    .getByRole("button", { name: /^Record response/ })
    .click();
  const form = page.getByRole("form", {
    name: /Record the employer's response/,
  });
  await expect(form).toBeVisible();
  await page
    .getByRole("group", { name: "Stage" })
    .getByRole("button", { name: /^All/ })
    .click();
  await expect(page).toHaveURL(/stage=all|#applications\?q=/);
  await expect(row(page, title)).toBeVisible();
  await expect(form).toHaveCount(0);
});

test("the list is as tall as its rows: no empty rows below them", async ({
  page,
}) => {
  await go(page, "applications?stage=all");
  await settled(page);
  const rows = page.locator(
    ".grid-table [role=rowgroup]:not(.grid-head) > [role=row]",
  );
  expect(await rows.count()).toBeGreaterThan(20);
  const height = () =>
    page.evaluate(() => document.documentElement.scrollHeight);
  const before = await height();
  // Scroll through the whole list: no row changes size once it is drawn.
  for (let y = 0; y < before; y += 400) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.waitForTimeout(30);
  }
  expect(await height()).toBe(before);
  const last = rows.last();
  await last.scrollIntoViewIfNeeded();
  const table = (await page.locator(".grid-table").boundingBox())!;
  const end = (await last.boundingBox())!;
  // The last row ends the table.
  expect(table.y + table.height - (end.y + end.height)).toBeLessThan(2);
  await expect(last.getByRole("link").first()).toBeVisible();
});

test("marking applied is refused cleanly once the application is no longer ready", async ({
  page,
}) => {
  const title = unique("No longer ready");
  const application = await make(page, title, { ready: true });
  await go(page, `review?application=${application.id}`);
  await settled(page);
  // Another session saves a new revision: the Ready mark is cleared.
  await call(page, "/documents", "POST", {
    application_id: application.id,
    kind: "resume",
    title: "Changed CV",
  });
  await page.getByRole("button", { name: "Mark applied" }).first().click();
  await expect(toast(page)).toContainText("no longer ready");
  expect((await call(page, `/applications/${application.id}`)).status).toBe(
    "draft",
  );
  await expect(page.getByRole("button", { name: "Mark applied" })).toHaveCount(
    0,
  );
});

test("the Ready mark is removed and set again under Details", async ({
  page,
}) => {
  const title = unique("Ready mark");
  const application = await make(page, title, { ready: true });
  await go(page, `review?application=${application.id}&tab=details`);
  await settled(page);
  await page.getByRole("button", { name: "Not ready", exact: true }).click();
  await expect(toast(page)).toContainText("No longer marked ready.");
  await expect
    .poll(
      async () =>
        (await call(page, `/applications/${application.id}`)).ready_at,
    )
    .toBeNull();
  await page.getByRole("button", { name: "Mark ready", exact: true }).click();
  await expect(toast(page)).toContainText("Marked ready to apply.");
  await expect
    .poll(
      async () =>
        (await call(page, `/applications/${application.id}`)).readiness,
    )
    .toBe("ready");
});

test("keyboard only: an employer response is recorded from an Applied row", async ({
  page,
}) => {
  const prefix = unique("Response row");
  const rejected = await make(page, `${prefix} rejected`, {
    status: "applied",
  });
  const invited = await make(page, `${prefix} invited`, { status: "applied" });
  const silent = await make(page, `${prefix} silent`, {
    status: "applied",
    appliedDaysAgo: 50,
  });
  await go(page, `applications?stage=applied&q=${encodeURIComponent(prefix)}`);
  await settled(page);
  // 50 days in UTC; the local day can be one off near midnight.
  await expect(row(page, `${prefix} silent`)).toContainText(
    /No reply for (49|50|51) days/,
  );

  // Rejection, with the keyboard: the form takes focus on its first choice.
  await row(page, `${prefix} rejected`)
    .getByRole("button", { name: /^Record response/ })
    .focus();
  await page.keyboard.press("Enter");
  const form = page.getByRole("form", {
    name: /Record the employer's response/,
  });
  await expect(
    form.getByRole("button", { name: "Interview", exact: true }),
  ).toBeFocused();
  await page.keyboard.press(tabKey(page));
  await expect(
    form.getByRole("button", { name: "Rejection", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    form.getByRole("button", { name: "Rejection", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await form.getByLabel("Note").focus();
  await page.keyboard.type("Position filled internally.");
  await page.keyboard.press(tabKey(page));
  await expect(
    form.getByRole("button", { name: "Save and close as rejected" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(toast(page)).toContainText("Rejection saved");
  const closed = await call(page, `/applications/${rejected.id}`);
  expect([closed.status, closed.outcome]).toEqual(["closed", "rejected"]);
  expect(closed.responses).toEqual([
    expect.objectContaining({
      kind: "rejection",
      date: localDay(0),
      note: "Position filled internally.",
      origin: "stage",
    }),
  ]);

  // An interview invitation moves the application to Interview.
  await row(page, `${prefix} invited`)
    .getByRole("button", { name: /^Record response/ })
    .click();
  await form.getByLabel("Date of the answer").fill(localDay(-2));
  await form
    .getByRole("button", { name: "Save and move to Interview" })
    .click();
  await expect
    .poll(async () => (await call(page, `/applications/${invited.id}`)).status)
    .toBe("interview");
  expect(
    (await call(page, `/applications/${invited.id}`)).responses[0],
  ).toEqual(expect.objectContaining({ kind: "interview", date: localDay(-2) }));

  // No reply closes the application on the day it was concluded.
  await row(page, `${prefix} silent`)
    .getByRole("button", { name: /^Record response/ })
    .click();
  await form.getByRole("button", { name: "No reply", exact: true }).click();
  await expect(form.getByLabel("Note")).toHaveCount(0);
  await form.getByRole("button", { name: "Close as no reply" }).click();
  await expect
    .poll(async () => (await call(page, `/applications/${silent.id}`)).outcome)
    .toBe("no_response");
  expect((await call(page, `/applications/${silent.id}`)).concluded_on).toBe(
    localDay(0),
  );

  // Closed, each row says what the employer did.
  await go(page, `applications?stage=closed&q=${encodeURIComponent(prefix)}`);
  await settled(page);
  await expect(row(page, `${prefix} rejected`)).toContainText(
    /Rejection · .*, after 0 days/,
  );
  await expect(row(page, `${prefix} silent`)).toContainText(
    /No reply · closed .* after (49|50|51) days/,
  );
  await fitsViewport(page);
});

test("selected applications are closed as no reply, reopened and deleted together", async ({
  page,
}) => {
  const prefix = unique("Bulk");
  const items = [];
  for (const name of ["one", "two"])
    items.push(await make(page, `${prefix} ${name}`, { status: "applied" }));
  const draft = await make(page, `${prefix} draft`);
  await go(page, `applications?q=${encodeURIComponent(prefix)}`);
  await settled(page);
  await page
    .getByRole("checkbox", { name: "Select every application shown" })
    .check();
  const bar = page.getByRole("group", { name: "Selected applications" });
  await expect(bar).toContainText("3 selected");
  // Only the actions valid for every selected application are offered: the
  // Draft was never sent and is not Ready, the others are not Preparing.
  await expect(bar.getByRole("button")).toHaveText([
    "Close…",
    "Delete…",
    "Clear",
  ]);
  await row(page, `${prefix} draft`).getByRole("checkbox").uncheck();
  await expect(bar).toContainText("2 selected");
  await expect(bar.getByRole("button")).toHaveText([
    "Close as no reply",
    "Close…",
    "Delete…",
    "Clear",
  ]);
  await bar.getByRole("button", { name: "Close as no reply" }).click();
  for (const item of items)
    await expect
      .poll(async () => (await call(page, `/applications/${item.id}`)).outcome)
      .toBe("no_response");
  await expect(bar).toHaveCount(0);

  await page
    .getByRole("group", { name: "Stage" })
    .getByRole("button", { name: /^Closed/ })
    .click();
  await page
    .getByRole("checkbox", { name: "Select every application shown" })
    .check();
  await bar.getByRole("button", { name: "Reopen…" }).click();
  await dialog(page).getByLabel("Stage").selectOption("applied");
  await dialog(page)
    .getByRole("button", { name: "Reopen 2 applications" })
    .click();
  await expect
    .poll(async () => (await call(page, `/applications/${items[0].id}`)).status)
    .toBe("applied");
  await page
    .getByRole("group", { name: "Stage" })
    .getByRole("button", { name: /^All/ })
    .click();
  await page
    .getByRole("checkbox", { name: "Select every application shown" })
    .check();
  await bar.getByRole("button", { name: "Delete…" }).click();
  await dialog(page)
    .getByRole("button", { name: "Delete 3 applications" })
    .click();
  await expect(
    page.getByRole("heading", { name: "No application matches" }),
  ).toBeVisible();
  const left = await call(
    page,
    `/applications?q=${encodeURIComponent(prefix)}`,
  );
  expect(left.total).toBe(0);
  expect(draft.id).toBeTruthy();
});

test("the pipeline counts each stage, filters and shows a board", async ({
  page,
}) => {
  await go(page, "applications");
  await settled(page);
  const counts = await call(page, "/applications?limit=1");
  const chips = page.getByRole("group", { name: "Stage" }).getByRole("button");
  await expect(chips).toHaveText([
    `All${counts.total}`,
    `Preparing${counts.stage_counts.draft - counts.ready_count}`,
    `Ready${counts.ready_count}`,
    `Applied${counts.stage_counts.applied}`,
    `Interview${counts.stage_counts.interview}`,
    `Offer${counts.stage_counts.offer}`,
    `Closed${counts.stage_counts.closed}`,
  ]);
  // Ready is its own stage; Preparing no longer includes it.
  await chips.filter({ hasText: /^Ready/ }).click();
  await expect(page).toHaveURL(/stage=ready/);
  await expect(
    page.getByRole("table", { name: "Applications" }).getByRole("row"),
  ).toHaveCount(counts.ready_count + 1);
  await expect(
    page.getByRole("link", { name: /^Review / }).first(),
  ).toHaveClass(/primary/);
  await page.getByLabel("Sort", { exact: true }).selectOption("deadline");
  await expect(page).toHaveURL(/sort=deadline/);
  await page.getByLabel("Readiness", { exact: true }).selectOption("blocked");
  await expect(
    page.getByRole("heading", { name: "No application matches" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await page
    .getByRole("searchbox", { name: "Search applications" })
    .fill("Harbor Bank");
  await chips.filter({ hasText: /^All/ }).click();
  await expect(row(page, "Platform Engineer")).toContainText(
    "Blocking requirement",
  );
  await expect(
    row(page, "Platform Engineer").getByRole("link", { name: /^Decide/ }),
  ).toHaveAttribute("href", /tab=requirements$/);
  await page.getByRole("searchbox", { name: "Search applications" }).fill("");

  // The board: one column per open stage, the rest of a stage in the list.
  await page.getByRole("button", { name: "Board", exact: true }).click();
  await expect(page).toHaveURL(/view=board/);
  const board = page.getByRole("region", { name: "Applications as a board" });
  await expect(board.locator("section h3")).toHaveText([
    /^Preparing/,
    /^Ready/,
    /^Applied/,
    /^Interview/,
    /^Offer/,
  ]);
  await board.getByRole("button", { name: "Show closed" }).click();
  await expect(board.locator("section h3")).toHaveCount(6);
  await board.getByRole("button", { name: /more in Applied$/ }).click();
  await expect(page).toHaveURL(/stage=applied/);
  await expect(page.getByRole("table", { name: "Applications" })).toBeVisible();
  await fitsViewport(page);
});

test("Insights shows the rates of sent applications and withholds small groups", async ({
  page,
}) => {
  await go(page, "applications?section=insights");
  await settled(page);
  const report = await call(page, "/insights");
  const stats = page.locator(".tiles .stat");
  await expect(stats.filter({ hasText: "Applications sent" })).toContainText(
    String(report.overall.sent),
  );
  await expect(stats.filter({ hasText: "Got an answer" })).toContainText(
    `${report.overall.responded} of ${report.overall.sent}`,
  );
  await expect(page.getByText("Not counted:")).toContainText(
    `${report.excluded.closed_unsent} application`,
  );
  const families = page
    .locator("section.card")
    .filter({ has: page.getByRole("heading", { name: "By role family" }) });
  for (const group of report.groups.role_family) {
    const line = families.getByRole("row").filter({ hasText: group.label });
    await expect(line).toContainText(String(group.sent));
    if (group.withheld)
      await expect(line).toContainText("Too few to show a rate");
  }
  await page.getByRole("button", { name: "Last 90 days" }).click();
  await expect(page).toHaveURL(/period=90/);
  await settled(page);
  await expect(page.getByRole("heading", { name: "Progress" })).toBeVisible();
  await fitsViewport(page);
});

test("answers and the questions of the form are edited without JSON", async ({
  page,
}) => {
  const application = await make(page, unique("Answers"), {
    questions: [{ id: "motivation", label: "Why this role?", type: "text" }],
  });
  await go(page, `review?application=${application.id}&tab=answers`);
  await settled(page);
  await page.getByLabel("Why this role?").fill("Synthetic motivation.");
  await page.getByRole("button", { name: "Save answers" }).click();
  await expect
    .poll(
      async () => (await call(page, `/applications/${application.id}`)).answers,
    )
    .toEqual({ motivation: "Synthetic motivation." });
  // A new question with choices.
  await page.getByRole("button", { name: "Add question" }).click();
  await dialog(page).getByLabel("Question").fill("Which office?");
  await dialog(page)
    .getByLabel("Answer", { exact: true })
    .selectOption("choice");
  await dialog(page).getByLabel("Choices").fill("Zurich\nBasel");
  await dialog(page).getByRole("button", { name: "Save the question" }).click();
  await expect(dialog(page)).toHaveCount(0);
  await page.getByLabel("Which office?").selectOption("Basel");
  await page.getByRole("button", { name: "Save answers" }).click();
  await expect
    .poll(async () =>
      Object.values(
        (await call(page, `/applications/${application.id}`)).answers,
      ).sort(),
    )
    .toEqual(["Basel", "Synthetic motivation."]);
  // A change of type that the saved answer does not fit is cleared on purpose only.
  await page.getByRole("button", { name: "Edit Why this role?" }).click();
  await dialog(page)
    .getByLabel("Answer", { exact: true })
    .selectOption("number");
  await dialog(page).getByRole("button", { name: "Save the question" }).click();
  await expect(dialog(page)).toContainText("The saved answer does not fit");
  await dialog(page)
    .getByRole("checkbox", {
      name: "Clear the saved answer when saving the question",
    })
    .check();
  await dialog(page).getByRole("button", { name: "Save the question" }).click();
  await expect(dialog(page)).toHaveCount(0);
  const saved = await call(page, `/applications/${application.id}`);
  expect(saved.answers.motivation).toBeUndefined();
  await page.getByRole("button", { name: "Remove Which office?" }).click();
  await dialog(page)
    .getByRole("button", { name: "Remove question and answer" })
    .click();
  await expect
    .poll(
      async () =>
        (await call(page, `/applications/${application.id}`)).questions.length,
    )
    .toBe(1);
});

test("requirements, the plan and a concurrent change in the details", async ({
  page,
}) => {
  const application = await make(page, unique("Planned"), {
    priority: 1,
    deadline: "2026-12-01",
    requirements: [
      {
        kind: "authorship",
        text: "Applications must be written without AI tools.",
        blocking: true,
      },
    ],
  });
  // The old drawer's address opens the review page on the same tab.
  await go(
    page,
    `applications?application=${application.id}&detail=requirements`,
  );
  await expect(page).toHaveURL(/#review\?application=.*&tab=requirements$/);
  await settled(page);
  const list = page.getByRole("form", { name: "Requirements" });
  await list.getByRole("checkbox", { name: "Resolved" }).first().check();
  await list
    .getByLabel("Resolution or open question")
    .first()
    .fill("The owner writes it.");
  await list.getByRole("button", { name: "Add requirement" }).click();
  await list.getByLabel("Kind").last().selectOption("reference");
  await list
    .getByLabel("Requirement", { exact: true })
    .last()
    .fill("Two references.");
  await list.getByRole("button", { name: "Save requirements" }).click();
  await expect
    .poll(
      async () =>
        (await call(page, `/applications/${application.id}`)).requirements,
    )
    .toEqual([
      expect.objectContaining({
        kind: "authorship",
        resolved: true,
        note: "The owner writes it.",
      }),
      expect.objectContaining({
        kind: "reference",
        text: "Two references.",
        blocking: false,
      }),
    ]);

  await page.getByRole("tab", { name: "Details" }).click();
  const details = page.getByRole("form", { name: "Stage and plan" });
  await details.getByLabel("Priority").selectOption("3");
  await details.getByLabel("Deadline").fill("2027-01-15");
  // Another session changes the application before the owner saves.
  const current = await call(page, `/applications/${application.id}`);
  await call(page, `/applications/${application.id}`, "PATCH", {
    expected_version: current.version,
    deadline: "2027-03-03",
  });
  await details.getByRole("button", { name: "Save details" }).click();
  await details.getByRole("button", { name: "Review latest values" }).click();
  await expect(details.locator(".conflict-recovery")).toContainText(
    "2027-03-03",
  );
  await details
    .getByRole("button", { name: "Reload editor and discard draft" })
    .click();
  // The editor now holds the latest record.
  await expect(
    page.getByRole("form", { name: "Stage and plan" }).getByLabel("Deadline"),
  ).toHaveValue("2027-03-03");
  await page
    .getByRole("form", { name: "Stage and plan" })
    .getByLabel("Priority")
    .selectOption("3");
  await page
    .getByRole("form", { name: "Stage and plan" })
    .getByLabel("Deadline")
    .fill("2027-01-15");
  await page
    .getByRole("form", { name: "Stage and plan" })
    .getByRole("button", { name: "Save details" })
    .click();
  await expect
    .poll(async () => {
      const value = await call(page, `/applications/${application.id}`);
      return [value.priority, value.deadline];
    })
    .toEqual([3, "2027-01-15"]);

  // The pinned note: pinned, edited, then unpinned into the timeline.
  const pinned = page.getByRole("form", { name: "Pinned note" });
  await pinned.getByLabel("Pinned note").fill("Lead with the platform work.");
  await pinned.getByRole("button", { name: "Pin this note" }).click();
  await expect
    .poll(
      async () =>
        (await call(page, `/applications/${application.id}`)).pinned_note?.body,
    )
    .toBe("Lead with the platform work.");
  await expect(
    pinned.getByRole("button", { name: "Save the pinned note" }),
  ).toBeVisible();
  await pinned.getByLabel("Pinned note").fill("Lead with the API work.");
  await pinned.getByRole("button", { name: "Save the pinned note" }).click();
  await expect
    .poll(async () => {
      const value = await call(page, `/applications/${application.id}`);
      return [value.pinned_note?.body, value.pinned_note?.version];
    })
    .toEqual(["Lead with the API work.", 2]);
  await pinned.getByRole("button", { name: "Unpin" }).click();
  await expect(
    pinned.getByRole("button", { name: "Pin this note" }),
  ).toBeVisible();
  await expect(pinned.getByLabel("Pinned note")).toHaveValue("");
  await page.getByRole("tab", { name: "Timeline" }).click();
  await expect(
    page.getByRole("list", { name: "Timeline of this application" }),
  ).toContainText("Lead with the API work.");
});

test("documents, revisions, frozen copies and their files are managed in the review page", async ({
  page,
}) => {
  const application = await make(page, unique("Documents"));
  await go(page, `review?application=${application.id}&tab=inputs`);
  await settled(page);
  // A frozen copy with deliberately empty selections.
  await page.getByRole("button", { name: "Prepare a frozen copy" }).click();
  await dialog(page)
    .getByRole("checkbox", { name: "Choose the Career entries" })
    .check();
  await dialog(page)
    .getByRole("checkbox", { name: "Choose the approved claims" })
    .check();
  await dialog(page)
    .getByRole("group", { name: /Career entries/ })
    .getByRole("button", { name: "Clear matching" })
    .click();
  await expect(
    dialog(page)
      .getByRole("group", { name: /Approved claims/ })
      .getByRole("checkbox"),
  ).toHaveCount(0);
  const saved = page.waitForEvent("download");
  await dialog(page).getByRole("button", { name: "Save and download" }).click();
  await saved;
  await expect(dialog(page)).toHaveCount(0);
  const contexts = await call(
    page,
    `/contexts?application_id=${application.id}`,
  );
  const context = await call(page, `/contexts/${contexts.items[0].id}`);
  expect([context.payload.knowledge, context.payload.claims]).toEqual([[], []]);
  const copies = page.getByRole("list", { name: "Frozen copies" });
  await copies.getByRole("button", { name: "Files" }).first().click();
  await expect(copies).toContainText(/No file in this copy|\.tex|\.pdf/);
  const again = page.waitForEvent("download");
  await copies
    .getByRole("button", { name: /^Download/ })
    .first()
    .click();
  await again;

  // A CV from that copy: its source and the PDF built from it, approved,
  // revised, compared with the first revision and deleted.
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByRole("button", { name: "Add a document" }).click();
  await dialog(page).getByLabel("Title").fill("Workflow CV");
  await dialog(page).getByLabel("Written from").selectOption({ index: 1 });
  await dialog(page)
    .getByLabel("Source (.tex)")
    .setInputFiles({
      name: "workflow.tex",
      mimeType: "application/x-tex",
      buffer: syntheticTex("Synthetic document text."),
    });
  await dialog(page).getByLabel("PDF", { exact: true }).setInputFiles({
    name: "workflow.pdf",
    mimeType: "application/pdf",
    buffer: syntheticPdf(),
  });
  await dialog(page).getByLabel("Note").fill("Leads with the data work.");
  await dialog(page).getByRole("button", { name: "Save the revision" }).click();
  await expect(dialog(page)).toHaveCount(0);
  // The Documents tab can keep the list it read before the files arrived
  // (seen on a loaded CI runner); open it again for a fresh read.
  await page.waitForLoadState("networkidle");
  await go(page, `review?application=${application.id}&tab=documents`);
  await settled(page);
  const revisions = page.getByRole("list", { name: "Document revisions" });
  await revisions.getByRole("button", { name: /^Open Workflow CV/ }).click();
  await expect(
    revisions.getByRole("document", { name: "Text of revision 1" }),
  ).toHaveText("Synthetic document text.");
  await expect(revisions).toContainText("PDF, built from workflow.tex");
  await expect(revisions).toContainText("Leads with the data work.");
  await page.getByRole("button", { name: "Approve this revision" }).click();
  await expect(
    revisions.getByText("Approved", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.locator('iframe[title^="Preview of the CV"]'),
  ).toBeVisible();
  // The CV pane shows the text read from the source beside the PDF.
  await page
    .getByRole("group", { name: "Show the CV as" })
    .getByRole("button", { name: "Text" })
    .click();
  await expect(
    page.getByRole("document", { name: "Text of the CV" }),
  ).toHaveText("Synthetic document text.");
  await page.getByRole("button", { name: "workflow.pdf" }).click();
  await expect(
    dialog(page).getByTitle("Preview of workflow.pdf"),
  ).toBeVisible();
  await dialog(page)
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByRole("button", { name: "New revision" }).click();
  await dialog(page)
    .getByLabel("Source (.tex)")
    .setInputFiles({
      name: "workflow.tex",
      mimeType: "application/x-tex",
      buffer: syntheticTex("Changed synthetic document."),
    });
  await dialog(page).getByRole("button", { name: "Save the revision" }).click();
  await expect(dialog(page)).toHaveCount(0);
  await expect(revisions.locator(":scope > li")).toHaveCount(2);
  await revisions.getByRole("button", { name: /^Open/ }).first().click();
  await expect(
    page.getByText("Add the PDF built from the source before approving."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve this revision" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Compare with revision 1" }).click();
  const changes = page.getByRole("list", {
    name: "Changes since revision 1",
  });
  await expect(changes.getByRole("listitem")).toHaveText([
    "−Removed: Synthetic document text.",
    "+Added: Changed synthetic document.",
  ]);
  await expect(
    page.getByText("Since revision 1: 1 line added, 1 removed."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete revision" }).click();
  await dialog(page)
    .getByRole("button", { name: "Delete the revision" })
    .click();
  await expect(revisions.locator(":scope > li")).toHaveCount(1);

  // An input changes after the copy: the Inputs tab says what changed.
  const instructions = await call(page, "/instructions");
  await call(page, "/instructions", "PATCH", {
    expected_version: instructions.version,
    general: instructions.general + "\nSynthetic change.",
  });
  // The change was made elsewhere: the page shows it once read again.
  await page.reload();
  await settled(page);
  await page.getByRole("tab", { name: "Inputs" }).click();
  await expect(page.getByText("Inputs changed since")).toBeVisible();
  await expect(
    page.getByRole("list", {
      name: "Inputs changed since the documents were written",
    }),
  ).toContainText("General instructions");
  expect((await call(page, `/applications/${application.id}`)).answers).toEqual(
    {},
  );
});

test("the Inputs tab and the list name the parts that changed since the documents were written", async ({
  page,
}) => {
  const stamp = unique("Inputs");
  const application = await make(page, stamp);
  const add = async (section: string, body: Record<string, unknown>) =>
    (
      await call(page, `/policy/${section}/items`, "POST", {
        expected_version: (await call(page, `/policy/${section}`)).version,
        ...body,
      })
    ).item;
  const authorization = await add("eligibility", {
    label: `Work authorization ${stamp}`,
    statement: "EU citizen.",
  });
  const onePage = await add("writing", {
    label: `One page ${stamp}`,
    statement: "Keep the CV to one page.",
    scope: "cv",
  });
  const context = await call(page, "/contexts", "POST", {
    application_id: application.id,
  });
  for (const kind of ["resume", "cover_letter"])
    await call(page, "/documents", "POST", {
      application_id: application.id,
      context_id: context.id,
      kind,
      title: kind === "resume" ? "CV" : "Letter",
    });
  const profile = async (fields: Record<string, unknown>) =>
    call(page, "/career/profile", "PATCH", {
      expected_version: (await call(page, "/career/profile")).version,
      ...fields,
    });
  const before = await call(page, "/career/profile");

  // Metadata is not used by documents: they stay current.
  await profile({ metadata: { ...before.metadata, synthetic: stamp } });
  await go(page, `review?application=${application.id}&tab=inputs`);
  await settled(page);
  await expect(page.getByText("Inputs are current")).toBeVisible();

  // The summary, an eligibility fact and a CV rule change.
  await profile({ summary: `${before.summary} ${stamp}` });
  for (const [item, statement] of [
    [authorization, "EU citizen, no sponsorship needed."],
    [onePage, "One page, no photo."],
  ])
    await call(page, `/policy/items/${item.id}`, "PATCH", {
      expected_version: (await call(page, `/policy/${item.section}`)).version,
      statement,
    });
  await page.reload();
  await settled(page);
  await expect(page.getByText("Inputs changed since")).toBeVisible();
  const changes = page.getByRole("list", {
    name: "Inputs changed since the documents were written",
  });
  await expect(changes.getByRole("listitem")).toHaveText([
    /^Profile summary\s*changed$/,
    new RegExp(
      `^Policy “Work authorization ${stamp}”\\s*changed · Facts employers ask about$`,
    ),
    new RegExp(
      `^Policy “One page ${stamp}”\\s*changed · Rules for your documents · CV only$`,
    ),
  ]);
  await expect(changes).not.toContainText("Metadata");
  await fitsViewport(page);

  // The list names the first change and counts the others.
  await go(page, `applications?q=${encodeURIComponent(stamp)}`);
  await settled(page);
  await expect(row(page, stamp)).toContainText("Inputs changed");
  await expect(row(page, stamp)).toContainText("Profile summary and 2 more");

  // Put the shared Profile and policy back for the other tests.
  await profile({ summary: before.summary, metadata: before.metadata });
  for (const item of [authorization, onePage])
    await call(
      page,
      `/policy/items/${item.id}?expected_version=${(await call(page, `/policy/${item.section}`)).version}`,
      "DELETE",
    );
});

test("the timeline records responses, notes and who made each change", async ({
  page,
}) => {
  const stamp = unique("Timeline");
  const agent = await call(page, "/tokens", "POST", {
    name: `Synthetic agent ${stamp}`,
  });
  const application = await make(page, stamp, { status: "applied" });
  await page.evaluate(
    async ({ token, id, version }) => {
      await fetch(`/api/v1/applications/${id}`, {
        method: "PATCH",
        credentials: "omit",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({ expected_version: version, priority: 2 }),
      });
    },
    { token: agent.token, id: application.id, version: application.version },
  );
  await call(page, "/tokens/" + agent.id, "DELETE");
  await go(page, `review?application=${application.id}&tab=timeline`);
  await settled(page);
  const history = page.getByRole("list", {
    name: "Timeline of this application",
  });
  await expect(history.getByRole("listitem").first()).toContainText(
    `Synthetic agent ${stamp}`,
  );
  await expect(history).toContainText("Owner (dashboard)");

  // An employer response: recorded, its day corrected, then removed.
  await page.getByRole("button", { name: "Record a response" }).click();
  const form = page.getByRole("form", {
    name: /Record the employer's response/,
  });
  await form.getByRole("button", { name: "Other", exact: true }).click();
  await form.getByLabel("Note").fill("Asked for references.");
  await form.getByRole("button", { name: "Save the answer" }).click();
  const responses = page.getByRole("list", { name: "Employer responses" });
  await expect(responses).toContainText("Other answer");
  await responses.getByRole("button", { name: /^Edit/ }).click();
  await page
    .getByRole("form", { name: "Correct the response" })
    .getByLabel("Date of the answer")
    .fill(localDay(-3));
  await page
    .getByRole("form", { name: "Correct the response" })
    .getByRole("button", { name: "Save" })
    .click();
  await expect
    .poll(
      async () =>
        (await call(page, `/applications/${application.id}/responses`)).items[0]
          .date,
    )
    .toBe(localDay(-3));
  await responses.getByRole("button", { name: /^Remove/ }).click();
  await dialog(page)
    .getByRole("button", { name: "Remove the response" })
    .click();
  await expect(page.getByText("No answer is recorded.")).toBeVisible();

  // A note on the application, then deleted after asking.
  await page
    .getByLabel("A note on this application")
    .fill("Synthetic note on the application.");
  await page.getByRole("button", { name: "Add the note" }).click();
  await expect(history).toContainText("Synthetic note on the application.");
  // Pinned, it leads the timeline.
  await history.getByRole("button", { name: "Pin this note" }).click();
  await expect(history.getByRole("listitem").first()).toContainText(
    "Pinned note",
  );
  // Notes only, then the job's own entries, marked as such.
  const filters = page.getByRole("group", { name: "Timeline filters" });
  await filters.getByRole("button", { name: /^Notes/ }).click();
  await expect(history.getByRole("listitem")).toHaveCount(1);
  await filters.getByRole("button", { name: /^Everything/ }).click();
  await filters.getByLabel("Scope").selectOption("job");
  await expect(history).toContainText("Collected");
  await expect(history.getByRole("listitem").first()).toContainText("Job");
  await expect(history).not.toContainText("Synthetic note on the application.");
  await filters.getByLabel("Scope").selectOption("");
  await history.getByRole("button", { name: "Delete this note" }).click();
  await dialog(page).getByRole("button", { name: "Delete the note" }).click();
  await expect(history).not.toContainText("Synthetic note on the application.");
  await fitsViewport(page);
});

test("the agent is asked from the review page and the application is deleted", async ({
  page,
}) => {
  const application = await make(page, unique("Ask and delete"));
  await go(page, `review?application=${application.id}&tab=details`);
  await settled(page);
  await page
    .getByLabel("A request about this application")
    .fill("Rewrite the letter with more on data pipelines.");
  await page.getByRole("button", { name: "Send the request" }).click();
  const request = page.getByRole("article", { name: /Rewrite the letter/ });
  await expect(request).toContainText("Waiting for your agent");
  await request.getByRole("button", { name: "Withdraw" }).click();
  await expect(request).toContainText("Withdrawn");
  // Stop it as Not pursued, then delete it for good.
  await page
    .getByRole("form", { name: "Stage and plan" })
    .getByLabel("Stage")
    .selectOption("closed");
  await page
    .getByRole("form", { name: "Stage and plan" })
    .getByLabel("Outcome")
    .selectOption("not_pursued");
  await page
    .getByRole("form", { name: "Stage and plan" })
    .getByRole("button", { name: "Save details" })
    .click();
  await expect
    .poll(
      async () => (await call(page, `/applications/${application.id}`)).outcome,
    )
    .toBe("not_pursued");
  await page.getByRole("button", { name: "Delete this application" }).click();
  await dialog(page)
    .getByRole("button", { name: "Delete the application" })
    .click();
  await expect(page).toHaveURL(/#applications$/);
  const left = await page.evaluate(
    (id) =>
      fetch(`/api/v1/applications/${id}`).then((response) => response.status),
    application.id,
  );
  expect(left).toBe(404);
});

test("on a phone the review page shows one pane at a time above a fixed action bar", async ({
  page,
}) => {
  test.skip(!isNarrow(page), "The pane switch exists on narrow screens.");
  const application = await make(page, unique("Phone review"), { ready: true });
  await go(page, `review?application=${application.id}`);
  await settled(page);
  const panes = page.getByRole("group", { name: "Shown document" });
  await expect(page.locator(".pane:visible")).toHaveCount(1);
  await expect(page.locator(".pane:visible")).toContainText("CV");
  await panes.getByRole("button", { name: "Posting" }).click();
  await expect(page.locator(".pane:visible")).toContainText("Posting");
  const bar = page.getByRole("group", { name: "Main actions" });
  await expect(bar.getByRole("button", { name: "Mark applied" })).toBeVisible();
  const nav = await page
    .getByRole("navigation", { name: "Main" })
    .boundingBox();
  const actions = await bar.boundingBox();
  expect(actions!.y + actions!.height).toBeLessThanOrEqual(nav!.y + 1);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const end = await page.locator(".review-more").boundingBox();
  expect(end!.y + end!.height).toBeLessThanOrEqual(actions!.y + 1);
  await fitsViewport(page);
});
