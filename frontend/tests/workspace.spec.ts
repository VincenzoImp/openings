import { test, expect, type Page, type BrowserContext } from "@playwright/test";

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
      // The header separates test setup from requests made by the dashboard
      // (scripts/parity_matrix.py records only the latter).
      const setup = { "X-Openings-E2E-Setup": "1" };
      const session = await fetch("/api/v1/auth/session", {
        headers: setup,
      }).then((r) => r.json());
      const response = await fetch("/api/v1" + path, {
        method,
        headers: {
          ...setup,
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
let ownerCookies: Parameters<BrowserContext["addCookies"]>[0] = [];
test.beforeAll(async ({ browser }, info) => {
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL,
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.locator("input[name=password]").fill("synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".main h1")).toBeVisible();
  ownerCookies = await context.cookies();
  await context.close();
});
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
  await go(page, "inbox");
  const queue = await call(page, "/jobs?queue=inbox");
  await expect(page.locator(".navcount")).toHaveText(String(queue.total));
  await page.locator(".jobmain").first().click();
  await expect(top(page).locator(".posting")).toBeVisible();
  await expect(
    top(page).getByRole("button", { name: "Shortlist", exact: true }),
  ).toHaveClass(/primary/);
  await expect(
    top(page).getByRole("button", { name: "Merge duplicate", exact: true }),
  ).not.toBeVisible();
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();
  await page.locator(".row-select").first().check();
  await expect(page.getByLabel("Selected opportunities")).toBeVisible();
  await page.route("**/api/v1/jobs?*", async (route) => {
    if (new URL(route.request().url()).searchParams.get("q")) {
      const response = await route.fetch();
      await new Promise((r) => setTimeout(r, 700));
      await route.fulfill({ response });
    } else await route.continue();
  });
  await page
    .getByRole("textbox", { name: "Search jobs", exact: true })
    .fill("no-such-synthetic-role");
  await expect(
    page.getByRole("status").filter({ hasText: "Updating results" }),
  ).toBeVisible();
  await expect(page.locator(".jobrow")).toHaveCount(0);
  await expect(page.getByLabel("Selected opportunities")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "No jobs match your filters" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .last()
    .click();
  await expect(page.locator(".jobrow").first()).toBeVisible();
});

test("version conflict reviews latest values and reloads the editor with a usable version", async ({
  page,
}) => {
  const job = await call(page, "/jobs", "POST", {
    title: "Concurrent editor",
    company: "Original",
    posting: "Build services.",
  });
  await go(page, `inbox?job=${job.id}`);
  await top(page)
    .getByRole("tab", { name: "Edit details", exact: true })
    .click();
  await top(page).locator("input[name=company]").fill("My draft");
  await call(page, `/jobs/${job.id}`, "PATCH", {
    expected_version: job.version,
    company: "Newer value",
  });
  await top(page)
    .getByRole("button", { name: "Save details", exact: true })
    .click();
  await expect(top(page).locator("input[name=company]")).toHaveValue(
    "My draft",
  );
  await top(page)
    .getByRole("button", { name: "Review latest values", exact: true })
    .click();
  await expect(top(page).locator(".conflict-recovery")).toContainText(
    "Newer value",
  );
  await top(page)
    .getByRole("button", {
      name: "Reload editor and discard draft",
      exact: true,
    })
    .click();
  await expect(top(page).locator("input[name=company]")).toHaveValue(
    "Newer value",
  );
  await top(page).locator("input[name=company]").fill("Reapplied deliberately");
  await top(page)
    .getByRole("button", { name: "Save details", exact: true })
    .click();
  await expect
    .poll(async () => (await call(page, `/jobs/${job.id}`)).company)
    .toBe("Reapplied deliberately");
});

test("import protection and nested dialogs restore scroll after browser Back", async ({
  page,
}) => {
  await go(page, "inbox");
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
  // A claim of the selected entry opens in a dialog.
  const detail = page
    .getByRole("group", { name: "Shown pane" })
    .getByRole("button", { name: "Selected entry", exact: true });
  if (await detail.isVisible()) await detail.click();
  await page
    .getByRole("button", { name: /^Edit claim: /, exact: false })
    .first()
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await page.goBack();
  await expect(page.locator(".main h1")).toHaveText("Inbox");
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

test("mobile applications, templates and progress stay usable inside the viewport", async ({
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
  // The progress of sent applications stacks its table in Insights.
  await go(page, "applications?section=insights");
  await expect(
    page.getByRole("table", {
      name: "Sent applications by the furthest stage they reached",
    }),
  ).toBeVisible();
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
  await go(page, `inbox?job=${job.id}`);
  await top(page).getByRole("tab", { name: /Notes/ }).click();
  await top(page)
    .locator("[name=body]")
    .fill("Synthetic note to review before deletion.");
  await top(page)
    .getByRole("button", { name: "Add note", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "Delete note", exact: true })
    .click();
  await expect(top(page)).toContainText(
    "Synthetic note to review before deletion.",
  );
  await top(page)
    .getByRole("button", { name: "Keep note", exact: true })
    .click();
  await expect(page.locator(".note-entry")).toHaveCount(1);
  await top(page).getByRole("tab", { name: "Files", exact: true }).click();
  await top(page)
    .locator("input[type=file]")
    .setInputFiles({
      name: "safe-text.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "<script>window.__unsafe=true</script>\nSynthetic source",
      ),
    });
  await top(page)
    .getByRole("button", { name: "safe-text.txt", exact: true })
    .click();
  await expect(top(page).locator(".file-text")).toContainText("<script>");
  expect(await page.evaluate(() => (window as any).__unsafe)).toBeUndefined();
  await top(page)
    .getByRole("button", { name: "Close preview", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "Delete safe-text.txt", exact: true })
    .click();
  await expect(top(page)).toContainText("safe-text.txt");
  await top(page)
    .getByRole("button", { name: "Keep file", exact: true })
    .click();
  await expect(
    top(page).getByRole("button", { name: "safe-text.txt", exact: true }),
  ).toBeVisible();
  await top(page)
    .getByRole("button", { name: "Delete safe-text.txt", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "Delete file", exact: true })
    .click();
  await expect(
    top(page).getByRole("button", { name: "safe-text.txt", exact: true }),
  ).toHaveCount(0);
});
