import { test, expect, type Page } from "./fixtures";
import {
  attachSource,
  call,
  go,
  isPhone,
  ownerSession,
  syntheticPdf,
  type Cookies,
} from "./session";

// Applications (#224): the list by stage, Stats, and the application page
// whose content follows its stage, with the send loop review → send → next.
// Each test starts from the seeded workspace (fixtures.ts).
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
const toast = (page: Page) => page.locator(".ui-toast").last();
const dialog = (page: Page) => page.locator("dialog[open]").last();
/** The visible one of a control the page shows twice (head and phone bar). */
const visible = (page: Page, name: string) =>
  page
    .getByRole("button", { name: new RegExp(`^${name}`) })
    .filter({ visible: true })
    .first();

interface Options {
  ready?: boolean;
  status?: string;
  deadline?: string;
  requirements?: unknown[];
  appliedDaysAgo?: number;
}
/** A job and its application, set up through the API as the test's own data. */
async function make(page: Page, title: string, options: Options = {}) {
  const job = await call(page, "/jobs", "POST", {
    title,
    company: "Example Labs",
    location: "Zurich, Switzerland",
    posting: `${title} at Example Labs.\n\nBuild reliable services with a small team.`,
  });
  let application = await call(page, "/applications", "POST", {
    job_id: job.id,
    deadline: options.deadline,
    requirements: options.requirements ?? [],
  });
  if (options.ready)
    for (const kind of ["cv", "letter"]) {
      const document = await call(page, "/documents", "POST", {
        application_id: application.id,
        kind,
        title: kind === "cv" ? "CV" : "Letter",
      });
      await attachSource(page, document.id, "Synthetic text.", kind);
    }
  application = await call(page, `/applications/${application.id}`);
  if (options.status) {
    const day = new Date();
    day.setDate(day.getDate() - (options.appliedDaysAgo ?? 0));
    application = await call(page, `/applications/${application.id}`, "PATCH", {
      expected_version: application.version,
      status: options.status,
      ...(options.appliedDaysAgo !== undefined
        ? { applied_at: day.toISOString() }
        : {}),
    });
  }
  return call(page, `/applications/${application.id}`);
}
const read = (page: Page, id: string) => call(page, `/applications/${id}`);

/** Close every Ready application of the seed, so the queue is the test's own. */
async function emptyQueue(page: Page) {
  const ready = await call(page, "/applications?stage=ready&limit=200");
  if (!ready.items.length) return;
  await call(page, "/applications/bulk", "POST", {
    action: "close",
    outcome: "not_pursued",
    items: ready.items.map((item: { id: string; version: number }) => ({
      id: item.id,
      expected_version: item.version,
    })),
  });
}

test("five Ready applications are sent from Today with five Mark applied and no navigation", async ({
  page,
}) => {
  test.setTimeout(60000);
  await emptyQueue(page);
  const prefix = unique("Send loop");
  const queue = [];
  for (let index = 1; index <= 5; index++)
    queue.push(
      await make(page, `${prefix} ${index}`, {
        ready: true,
        deadline: `2000-01-0${index}`,
      }),
    );
  await page.reload();
  await page.locator(`a[href="#applications/${queue[0].id}"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`#applications/${queue[0].id}$`));
  await expect(page.getByText("1 of 5 ready")).toBeVisible();
  for (const [index, app] of queue.entries()) {
    await expect(page).toHaveURL(new RegExp(`#applications/${app.id}$`));
    await expect(
      page.getByRole("heading", { name: `${prefix} ${index + 1}` }).first(),
    ).toBeAttached();
    await visible(page, "Mark applied").click();
    await expect(toast(page)).toContainText("Marked applied");
  }
  await expect(
    page.getByRole("heading", { name: /^All sent — \d+ applications today/ }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Today" })).toBeVisible();
  for (const app of queue) {
    const sent = await read(page, app.id);
    expect([sent.status, !!sent.applied_at]).toEqual(["applied", true]);
  }
  // Undo brings the last one back, Ready and never sent.
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect(page).toHaveURL(new RegExp(`#applications/${queue[4].id}$`));
  await expect(visible(page, "Mark applied")).toBeVisible();
  await expect
    .poll(async () => {
      const back = await read(page, queue[4].id);
      return [back.status, back.applied_at, back.ready];
    })
    .toEqual(["shortlisted", null, true]);
  // The keyboard: ⇧↵ marks it applied again.
  await page.locator("body").press("Shift+Enter");
  await expect(page.getByRole("heading", { name: /^All sent —/ })).toBeVisible();
  expect((await read(page, queue[4].id)).status).toBe("applied");
});

test("an error on Mark applied leaves the page in place", async ({ page }) => {
  const app = await make(page, unique("Refused"), { ready: true });
  await go(page, `applications/${app.id}`);
  await page.route(/\/api\/v1\/applications\/[^/?]+$/, (route) =>
    route.request().method() === "PATCH"
      ? route.fulfill({
          status: 409,
          json: { error: { code: "conflict", status: 409, message: "Changed elsewhere." } },
        })
      : route.continue(),
  );
  await visible(page, "Mark applied").click();
  await expect(page.locator(".ui-toast[data-tone=error]")).toContainText(
    "Not marked applied",
  );
  await expect(page).toHaveURL(new RegExp(`#applications/${app.id}$`));
  expect((await read(page, app.id)).status).toBe("shortlisted");
});

test("without LaTeX: a PDF CV and letter uploaded on the page make it Ready", async ({
  page,
}) => {
  const title = unique("PDF only");
  const app = await make(page, title);
  expect(app.missing).toEqual(["cv", "letter"]);
  await go(page, `applications/${app.id}`);
  await expect(page.getByRole("heading", { name: "What's missing" })).toBeVisible();
  for (const [name, file] of [
    ["CV", "cv.pdf"],
    ["Letter", "letter.pdf"],
  ]) {
    await page.getByLabel(`Upload PDF of the ${name}`).setInputFiles({
      name: file,
      mimeType: "application/pdf",
      buffer: syntheticPdf(`Synthetic ${name}`),
    });
    await expect(toast(page)).toContainText(`${name} uploaded`, {
      timeout: 15000,
    });
  }
  await expect.poll(async () => (await read(page, app.id)).ready).toBe(true);
  // Nothing is missing: the page is the Ready page.
  await expect(visible(page, "Mark applied")).toBeVisible();
  await expect(page.getByText("Before you send")).toBeAttached();
});

test("an open blocking requirement keeps an application from Ready until ticked", async ({
  page,
}) => {
  const app = await make(page, unique("Blocked"), {
    ready: true,
    requirements: [
      { kind: "reference", text: "Two references", blocking: true },
    ],
  });
  expect(app.ready).toBe(false);
  await go(page, `applications/${app.id}`);
  await expect(visible(page, "Resolve requirements")).toBeVisible();
  await page.getByRole("checkbox", { name: /Two references/ }).click();
  await expect.poll(async () => (await read(page, app.id)).ready).toBe(true);
  await expect(visible(page, "Mark applied")).toBeVisible();
});

test("Record reply records the reply and moves the stage by its kind", async ({
  page,
}) => {
  const prefix = unique("Reply");
  for (const [kind, label, status, outcome] of [
    ["interview", "Interview invitation", "interview", null],
    ["offer", "Offer", "offer", null],
    ["rejection", "Rejection", "closed", "rejected"],
  ] as const) {
    const app = await make(page, `${prefix} ${kind}`, { status: "applied" });
    await go(page, `applications/${app.id}`);
    // Status line and Record reply above the fold, never an empty slot.
    const line = page.locator(".apg-statusline");
    await expect(line).toContainText(/^Applied/);
    const fold = page.viewportSize()!.height;
    expect((await line.boundingBox())!.y).toBeLessThan(fold);
    expect((await visible(page, "Record reply").boundingBox())!.y).toBeLessThan(fold);
    await expect(page.locator(".ap-drop")).toHaveCount(0);
    await visible(page, "Record reply").click();
    const form = dialog(page);
    await form.getByLabel(label, { exact: true }).check();
    await form.getByLabel("Note").fill(`Synthetic ${kind} note.`);
    await form.getByRole("button", { name: "Record reply" }).click();
    await expect(form).toHaveCount(0);
    await expect
      .poll(async () => {
        const after = await read(page, app.id);
        return [after.status, after.outcome ?? null, after.replies.length];
      })
      .toEqual([status, outcome, 1]);
  }
});

test("close as no reply from the page with Undo, and in bulk from the list", async ({
  page,
}) => {
  test.skip(isPhone(page), "Bulk selection is a desktop pattern.");
  const prefix = unique("No reply");
  const single = await make(page, `${prefix} single`, {
    status: "applied",
    appliedDaysAgo: 60,
  });
  await go(page, `applications/${single.id}`);
  await page.getByRole("button", { name: "More actions" }).filter({ visible: true }).click();
  await page.getByRole("menuitem", { name: "Close as no reply" }).click();
  await expect(toast(page)).toContainText("Closed as no reply");
  await expect
    .poll(async () => (await read(page, single.id)).outcome)
    .toBe("no_response");
  await toast(page).getByRole("button", { name: /Undo/ }).click();
  await expect.poll(async () => (await read(page, single.id)).status).toBe("applied");

  const first = await make(page, `${prefix} one`, { status: "applied", appliedDaysAgo: 50 });
  const second = await make(page, `${prefix} two`, { status: "applied", appliedDaysAgo: 55 });
  await go(page, `applications?stage=applied&q=${encodeURIComponent(prefix)}`);
  const rows = page.locator(".ui-list [data-row-id]");
  await expect(rows).toHaveCount(3);
  // Content at rest: no row shows a button.
  await page.mouse.move(0, 0);
  await expect(page.locator(".ui-row button").filter({ visible: true })).toHaveCount(0);
  await rows.first().click({ modifiers: ["ControlOrMeta"] });
  await rows.nth(1).click({ modifiers: ["ControlOrMeta"] });
  const bar = page.getByRole("toolbar", { name: "2 selected" });
  await expect(bar.getByRole("button")).toContainText([
    "Close as no reply",
    "Close…",
    "Set priority…",
    "Clear",
  ]);
  await bar.getByRole("button", { name: "Close as no reply" }).click();
  await expect(toast(page)).toContainText("Closed 2 as no reply");
  const closed = await Promise.all(
    [first, second, single].map(async (app) => (await read(page, app.id)).outcome ?? null),
  );
  expect(closed.filter((value) => value === "no_response")).toHaveLength(2);
});

test("the list starts with what needs action and opens the page; Stats has its numbers", async ({
  page,
}) => {
  await go(page, "applications");
  const list = page.getByRole("region", { name: "Applications" });
  await expect(list.getByRole("heading", { name: /^Ready to send/ })).toBeVisible();
  const row = list.locator("[data-row-id]").first();
  const box = (await row.boundingBox())!;
  expect(box.y).toBeLessThanOrEqual(isPhone(page) ? 220 : 300);
  await page
    .getByRole("group", { name: "Stage" })
    .getByRole("button", { name: /^Applied/ })
    .click();
  await expect(page).toHaveURL(/stage=applied/);
  await row.click();
  await expect(page).toHaveURL(/#applications\/[^?]+$/);
  await go(page, "applications?section=stats");
  await expect(page.getByText("Reply rate")).toBeVisible();
  await expect(page.getByRole("list", { name: "Funnel" }).getByRole("listitem")).toHaveCount(4);
  await page.getByRole("radio", { name: "All time" }).click();
  await expect(page).toHaveURL(/period=all/);
  await expect(page.getByText("Median days to a reply")).toBeVisible();
});
