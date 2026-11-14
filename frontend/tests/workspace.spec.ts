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
  await expect(page.locator(".main h1")).toBeVisible();
}
const top = (page: Page) => page.locator("dialog[open]").last();
const errors = new WeakMap<Page, string[]>();
const ownerCookies = ownerSession();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(ownerCookies);
  await page.goto("/");
  await expect(page.locator(".main h1")).toBeVisible();
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
  const active = (await call(page, "/applications?status=draft&limit=1"))
    .items[0];
  const job = await call(page, "/jobs/" + active.job_id);
  await call(page, `/jobs/${job.id}/triage`, "POST", {
    triage: "inbox",
    expected_version: job.version,
  });
  await go(page, "jobs");
  const queue = await call(page, "/jobs?queue=inbox");
  await expect(page.locator(".navcount").first()).toHaveText(
    String(queue.total),
  );
  const rows = page.locator(".job-list > li");
  await rows.first().locator("a.title").click();
  await expect(page.locator(".job-detail .posting")).toBeVisible();
  await expect(
    page
      .getByRole("group", { name: "Actions on this job" })
      .getByRole("button", { name: "Shortlist", exact: true }),
  ).toHaveClass(/primary/);
  // On a phone the job replaces the list until the switch shows it again.
  if (page.viewportSize()!.width <= 860)
    await page.getByRole("button", { name: "List", exact: true }).click();
  await rows.first().locator("input[type=checkbox]").check();
  await expect(
    page.getByRole("group", { name: "Selected jobs" }),
  ).toBeVisible();
  await page
    .getByRole("searchbox", { name: "Search jobs", exact: true })
    .fill("no-such-synthetic-role");
  // A new search empties the selection: an action never reaches unseen jobs.
  await expect(page.getByRole("group", { name: "Selected jobs" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("heading", { name: "No job matches" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Clear the filters", exact: true })
    .click();
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
  const editor = page.getByRole("form", { name: "Correct this job" });
  await page.getByText("Correct the job", { exact: true }).click();
  await editor.locator("input[name=company]").fill("My draft");
  await call(page, `/jobs/${job.id}`, "PATCH", {
    expected_version: job.version,
    company: "Newer value",
  });
  await editor
    .getByRole("button", { name: "Save the details", exact: true })
    .click();
  await expect(editor.locator("input[name=company]")).toHaveValue("My draft");
  await editor
    .getByRole("button", { name: "Review latest values", exact: true })
    .click();
  await expect(editor.locator(".conflict-recovery")).toContainText(
    "Newer value",
  );
  await editor
    .getByRole("button", {
      name: "Reload editor and discard draft",
      exact: true,
    })
    .click();
  await expect(editor.locator("input[name=company]")).toHaveValue(
    "Newer value",
  );
  await editor.locator("input[name=company]").fill("Reapplied deliberately");
  await editor
    .getByRole("button", { name: "Save the details", exact: true })
    .click();
  await expect
    .poll(async () => (await call(page, `/jobs/${job.id}`)).company)
    .toBe("Reapplied deliberately");
});

test("import protection and nested dialogs restore scroll after browser Back", async ({
  page,
}) => {
  await go(page, "jobs");
  await go(page, "career?section=knowledge");
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await top(page)
    .getByRole("textbox", { name: "Text or JSON", exact: true })
    .fill("Synthetic unsaved evidence");
  page.once("dialog", (dialog) => dialog.dismiss());
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();
  await expect(
    top(page).getByRole("textbox", { name: "Text or JSON", exact: true }),
  ).toHaveValue("Synthetic unsaved evidence");
  page.once("dialog", (dialog) => dialog.accept());
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();
  // A claim of the selected entry opens in a dialog, from its menu.
  const detail = page
    .getByRole("group", { name: "Shown pane" })
    .getByRole("button", { name: "Selected entry", exact: true });
  if (await detail.isVisible()) await detail.click();
  await page
    .getByRole("button", { name: /^More actions for claim: /, exact: false })
    .first()
    .click();
  await page
    .getByRole("button", { name: /^Edit claim: /, exact: false })
    .first()
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await page.goBack();
  await expect(page.locator(".main h1")).toHaveText("Jobs");
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await expect
    .poll(() => page.evaluate(() => document.body.style.overflow))
    .not.toBe("hidden");
});

test("mobile navigation contains focus and releases the background on close and resize", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const button = page.getByRole("button", { name: "More", exact: true });
  await button.click();
  await expect(page.locator("main")).toHaveAttribute("inert", "");
  for (let index = 0; index < 15; index++) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(
        () => !!document.activeElement?.closest(".more-sheet"),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(button).toBeFocused();
  await expect(page.locator("main")).not.toHaveAttribute("inert", "");
  await button.click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator("main")).not.toHaveAttribute("inert", "");
});

test("mobile applications, templates and stats stay usable inside the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await go(page, "applications");
  await expect(page.getByRole("table", { name: "Applications" })).toBeVisible();
  await expect(
    page.getByRole("group", { name: "Stage" }).getByRole("button"),
  ).toHaveCount(7);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  await go(page, "templates");
  // One pane at a time: the list first, the chosen template after a tap.
  const list = page.getByRole("region", { name: "Templates by kind" });
  await expect(list).toBeVisible();
  await expect(page.locator("#template-title")).toBeHidden();
  await list
    .getByRole("button", { name: "Synthetic CV 01", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Synthetic CV 01", exact: true }),
  ).toBeVisible();
  await expect(list).toBeHidden();
  expect(
    await page
      .locator("#template-title")
      .evaluate((element) => element.getBoundingClientRect().top),
  ).toBeLessThan(844);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  // Stats fits the phone: its numbers and the funnel.
  await go(page, "applications?section=stats");
  await expect(page.getByRole("table", { name: "Funnel" })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
});

test("the career entry editor recovers its own concurrent version", async ({
  page,
}) => {
  const recover = async (field: string, value: string, scope = top(page)) => {
    await scope
      .getByRole("button", { name: "Review latest values", exact: true })
      .click();
    await expect(scope.locator(".conflict-recovery")).toContainText(value);
    await scope
      .getByRole("button", {
        name: "Reload editor and discard draft",
        exact: true,
      })
      .click();
    await expect(scope.locator(`[name=${field}]`)).toHaveValue(value);
  };
  const entry = await call(page, "/career/knowledge", "POST", {
    kind: "project",
    title: "Concurrent career entry",
  });
  await go(page, "career?section=knowledge&q=Concurrent");
  // The entry is edited in the panel beside the record, not in a dialog.
  const shown = page
    .getByRole("group", { name: "Shown pane" })
    .getByRole("button", { name: "Selected entry", exact: true });
  if (await shown.isVisible()) await shown.click();
  const editor = page.locator("section.detail");
  await expect(editor.locator("[name=title]")).toHaveValue(
    "Concurrent career entry",
  );
  await editor.locator("[name=title]").fill("My entry draft");
  await call(page, `/career/knowledge/${entry.id}`, "PATCH", {
    expected_version: entry.version,
    title: "Concurrent newer title",
  });
  await editor.getByRole("button", { name: "Save entry", exact: true }).click();
  await recover("title", "Concurrent newer title", editor);
  await editor
    .locator("[name=title]")
    .fill("Concurrent, saved after the conflict");
  await editor.getByRole("button", { name: "Save entry", exact: true }).click();
  await expect
    .poll(async () => (await call(page, `/career/knowledge/${entry.id}`)).title)
    .toBe("Concurrent, saved after the conflict");
  // The four projects share one workspace: leave no entry that matches the search.
  const left = await call(page, `/career/knowledge/${entry.id}`);
  await call(
    page,
    `/career/knowledge/${entry.id}?expected_version=${left.version}`,
    "DELETE",
  );
});

test("live file and note deletion identify the item before removal", async ({
  page,
}) => {
  const job = await call(page, "/jobs", "POST", {
    title: "Owned notes and files",
    posting: "Build services.",
  });
  await go(page, `jobs?section=all&job=${job.id}`);
  const detail = page.locator(".job-detail");
  await detail
    .getByLabel("A note on this job")
    .fill("Synthetic note to review before deletion.");
  await detail
    .getByRole("button", { name: "Add the note", exact: true })
    .click();
  const timeline = detail.getByRole("list", { name: "Timeline of this job" });
  await timeline
    .getByRole("button", { name: "Delete this note", exact: true })
    .click();
  await expect(top(page)).toContainText(
    "Synthetic note to review before deletion.",
  );
  await top(page)
    .getByRole("button", { name: "Keep the note", exact: true })
    .click();
  await expect(timeline).toContainText(
    "Synthetic note to review before deletion.",
  );
  await detail.getByText("Files", { exact: true }).click();
  await detail.locator("input[type=file]").setInputFiles({
    name: "safe-text.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "<script>window.__unsafe=true</script>\nSynthetic source",
    ),
  });
  await detail
    .getByRole("button", { name: "safe-text.txt", exact: true })
    .click();
  await expect(top(page).locator("pre")).toContainText("<script>");
  expect(await page.evaluate(() => (window as any).__unsafe)).toBeUndefined();
  await top(page).getByRole("button", { name: "Close", exact: true }).click();
  await detail
    .getByRole("button", { name: "Remove safe-text.txt", exact: true })
    .click();
  await expect(top(page)).toContainText("safe-text.txt");
  await top(page)
    .getByRole("button", { name: "Keep file", exact: true })
    .click();
  await expect(
    detail.getByRole("button", { name: "safe-text.txt", exact: true }),
  ).toBeVisible();
  await detail
    .getByRole("button", { name: "Remove safe-text.txt", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "Remove file", exact: true })
    .click();
  await expect(
    detail.getByRole("button", { name: "safe-text.txt", exact: true }),
  ).toHaveCount(0);
});
