import { test, expect, type Page } from "./fixtures";
import { ownerSession } from "./session";

function syntheticPdf() {
  const stream = "BT /F1 18 Tf 40 440 Td (Synthetic application CV) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 500] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let data = "%PDF-1.4\n";
  const offsets = [0];
  for (const [index, object] of objects.entries()) {
    offsets.push(Buffer.byteLength(data));
    data += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xref = Buffer.byteLength(data);
  data +=
    "xref\n0 6\n0000000000 65535 f \n" +
    offsets
      .slice(1)
      .map((offset) => String(offset).padStart(10, "0") + " 00000 n \n")
      .join("") +
    `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(data);
}
async function call(page: Page, path: string, method = "GET", body?: unknown) {
  return page.evaluate(
    async ({ path, method, body }) => {
      const session = await fetch("/api/v1/auth/session").then((r) => r.json());
      const response = await fetch("/api/v1" + path, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": session.csrf_token,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const value = await response.json();
      if (!response.ok) throw Error(JSON.stringify(value));
      return value;
    },
    { path, method, body },
  );
}
async function go(page: Page, hash: string) {
  await page.goto("/#" + hash);
  await expect(page.locator("h1:visible")).toBeVisible();
}
const top = (page: Page) => page.locator("dialog[open]").last();
const errors = new WeakMap<Page, string[]>();
const ownerCookies = ownerSession();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(ownerCookies);
  await page.goto("/");
  await expect(page.locator("h1:visible")).toBeVisible();
});
test.afterEach(async ({ page }, info) => {
  await page.screenshot({
    path: info.outputPath("workspace.png"),
    fullPage: true,
  });
  expect(errors.get(page)).toEqual([]);
});

test("queue count, posting hierarchy and query-safe selection", async ({
  page,
}) => {
  // A shortlist undone while its application is still empty: back in New.
  const job = await call(page, "/jobs", "POST", {
    title: "Undone shortlist",
    company: "Example Labs",
    posting: "Build services.",
  });
  const shortlisted = await call(page, `/jobs/${job.id}/triage`, "POST", {
    triage: "shortlisted",
    expected_version: job.version,
  });
  await call(page, `/jobs/${job.id}/triage`, "POST", {
    triage: "new",
    expected_version: shortlisted.version,
  });
  await go(page, "jobs");
  // The navigation read its count before these changes.
  await page.reload();
  const queue = await call(page, "/jobs?triage=new");
  await expect(page.locator(".ui-needs:visible").first()).toHaveText(
    String(queue.total),
  );
  const rows = page.locator(".jobs-list .ui-row");
  await rows.first().locator(".ui-row-main").click();
  await expect(page.locator(".jobs-posting")).toBeVisible();
  // Shortlist is the one primary action of the job.
  await expect(
    page
      .locator(".jobs-decision, .ui-actionbar")
      .getByRole("button", { name: /^Shortlist/ })
      .filter({ visible: true }),
  ).toHaveAttribute("data-variant", "primary");
  const phone = page.viewportSize()!.width < 720;
  if (phone) await page.getByRole("button", { name: "Back to list" }).click();
  else {
    await page.keyboard.press("x");
    await expect(
      page.getByRole("toolbar", { name: "1 selected" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
  }
  if (phone) await page.getByRole("button", { name: "Search jobs" }).click();
  await page
    .getByRole("searchbox", { name: "Search jobs", exact: true })
    .filter({ visible: true })
    .fill("no-such-synthetic-role");
  await expect(
    page.getByRole("heading", { name: "No jobs match" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear search", exact: true }).click();
  await expect(rows.first()).toBeVisible();
});

test("version conflict reviews latest values and reloads the editor with a usable version", async ({
  page,
}) => {
  const job = await call(page, "/jobs", "POST", {
    title: "Concurrent editor",
    company: "Original",
    posting: "Build services.",
  });
  await go(page, `jobs?job=${job.id}`);
  await expect(page).toHaveURL(new RegExp(`#jobs\\?job=${job.id}$`));
  await page
    .getByRole("button", { name: "More actions" })
    .filter({ visible: true })
    .click();
  await page.getByRole("menuitem", { name: /^Correct details/ }).click();
  const editor = page.getByRole("dialog", { name: "Correct details" });
  const company = editor.getByLabel("Company");
  await company.fill("My draft");
  await call(page, `/jobs/${job.id}`, "PATCH", {
    expected_version: job.version,
    company: "Newer value",
  });
  await editor.getByRole("button", { name: /^Save/ }).click();
  await expect(editor.getByRole("alert")).toContainText("Changed elsewhere");
  await expect(company).toHaveValue("My draft");
  await editor.getByRole("button", { name: "Reload", exact: true }).click();
  await expect(company).toHaveValue("Newer value");
  await company.fill("Reapplied deliberately");
  await editor.getByRole("button", { name: /^Save/ }).click();
  await expect
    .poll(async () => (await call(page, `/jobs/${job.id}`)).company)
    .toBe("Reapplied deliberately");
});

test("keyboard only: the phone's More menu opens, moves, closes and gives focus back", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const button = page.getByRole("button", { name: "More", exact: true });
  await button.focus();
  await page.keyboard.press("Enter");
  const menu = page.getByRole("menu", { name: "More" });
  await expect(
    menu.getByRole("menuitem", { name: "Preferences" }),
  ).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(menu.getByRole("menuitem", { name: "Templates" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(button).toBeFocused();
  // Wide again: the sidebar replaces the bars.
  await button.click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(button).toBeHidden();
  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link", {
      name: "Preferences",
    }),
  ).toBeVisible();
});

test("mobile applications, templates and stats stay usable inside the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await go(page, "applications");
  await expect(
    page.getByRole("region", { name: "Applications" }),
  ).toBeVisible();
  await expect(
    page.getByRole("tablist", { name: "Stage" }).getByRole("tab"),
  ).toHaveCount(7);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  await go(page, "templates");
  // One pane at a time: the list first, the chosen template after a tap.
  const list = page.getByRole("region", { name: "Templates", exact: true });
  await expect(list).toBeVisible();
  await expect(page.locator(".tpl-title")).toBeHidden();
  await list.getByRole("button", { name: /^Synthetic CV 01\b/ }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic CV 01", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Back to templates" }),
  ).toBeVisible();
  expect(
    await page
      .locator(".tpl-title")
      .evaluate((element) => element.getBoundingClientRect().top),
  ).toBeLessThan(844);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  // Stats fits the phone: its numbers and the funnel.
  await go(page, "applications?section=stats");
  await expect(page.getByRole("list", { name: "Funnel" })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
});

test("a note is added to a job and pinned to the top of its history", async ({
  page,
}) => {
  const job = await call(page, "/jobs", "POST", {
    title: "Owned notes",
    posting: "Build services.",
  });
  await go(page, `jobs?section=all&job=${job.id}`);
  await page.getByText("Notes and history").click();
  await page.getByLabel("Add a note").fill("Synthetic pinned note.");
  await page.getByLabel("Pin it to the top").check();
  await page.getByRole("button", { name: "Add note", exact: true }).click();
  const history = page.getByRole("list", { name: "History of this job" });
  await expect(history.locator("li").first()).toContainText(
    "Synthetic pinned note.",
  );
  await expect(history.locator("li").first()).toContainText("Pinned note");
  const notes = await call(page, `/jobs/${job.id}/notes`);
  expect(notes.items[0].pinned).toBe(true);
});
