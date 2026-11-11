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

test("document upload, revision ownership and safe file preview", async ({
  page,
}) => {
  const job = await call(page, "/jobs", "POST", {
    title: "Document workflow",
    posting: "Build reliable systems.",
  });
  const application = await call(page, "/applications", "POST", {
    job_id: job.id,
  });
  await go(page, `applications?application=${application.id}`);
  await top(page)
    .getByRole("button", { name: "Add document", exact: true })
    .click();
  await top(page).locator("input[name=title]").fill("Workflow CV");
  await top(page)
    .locator("textarea[name=text]")
    .fill("Synthetic document text.");
  await top(page).locator("input[type=file]").setInputFiles({
    name: "workflow.pdf",
    mimeType: "application/pdf",
    buffer: syntheticPdf(),
  });
  await top(page)
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(top(page).locator(".preparation-summary")).toContainText(
    "PDF to review",
  );
  await top(page)
    .getByRole("button", { name: "Show Workflow CV", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "Approve this revision", exact: true })
    .click();
  await expect(top(page).locator(".preparation-summary")).toContainText(
    "Approved PDF",
  );
  await top(page)
    .getByRole("button", { name: "workflow.pdf", exact: true })
    .click();
  await expect(top(page).getByTitle("Preview of workflow.pdf")).toBeVisible();
  await top(page)
    .getByRole("button", { name: "Close preview", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "New revision", exact: true })
    .click();
  await top(page)
    .locator("textarea[name=text]")
    .fill("Changed synthetic document.");
  await top(page)
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(top(page).locator(".preparation-summary")).toContainText(
    "Needs PDF",
  );
  await top(page)
    .getByRole("button", { name: "Add document", exact: true })
    .click();
  await top(page).locator("select[name=kind]").selectOption("answers");
  await top(page).locator("input[name=title]").fill("Archived form answers");
  await top(page)
    .locator("textarea[name=text]")
    .fill("Synthetic archived answer, separate from live answers.");
  await top(page)
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(top(page).locator(".preparation-summary")).toContainText(
    "Form answers: Content saved",
  );
  const preparedApplication = await call(
    page,
    `/applications/${application.id}`,
  );
  expect(preparedApplication.status).toBe("draft");
  expect(preparedApplication.answers).toEqual({});
  await top(page)
    .getByRole("button", { name: "View posting", exact: true })
    .click();
  await expect(top(page).locator(".posting")).toContainText(
    "Build reliable systems.",
  );
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();
  await expect(page.locator(".main h1")).toHaveText("Applications");
});

test("question edits preserve compatible work and require deliberate incompatible removal", async ({
  page,
}) => {
  const job = await call(page, "/jobs", "POST", {
    title: "Question workflow",
    posting: "Build services.",
  });
  let application = await call(page, "/applications", "POST", {
    job_id: job.id,
    questions: [{ id: "motivation", label: "Why this role?", type: "text" }],
  });
  application = await call(page, `/applications/${application.id}`, "PATCH", {
    expected_version: application.version,
    answers: { motivation: "Synthetic motivation." },
  });
  await go(page, `applications?application=${application.id}`);
  await top(page)
    .getByRole("tab", { name: "Form answers", exact: true })
    .click();
  await top(page).getByText("Manage questions", { exact: true }).click();
  await top(page)
    .getByRole("button", { name: "Edit Why this role?", exact: true })
    .click();
  await top(page).locator("textarea[name=label]").fill("Why this team?");
  await top(page)
    .getByRole("button", { name: "Save question", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(top(page).locator("textarea[name=motivation]")).toHaveValue(
    "Synthetic motivation.",
  );
  await top(page)
    .getByRole("button", { name: "Edit Why this team?", exact: true })
    .click();
  await top(page)
    .getByLabel("Answer type", { exact: true })
    .selectOption("number");
  await top(page)
    .getByRole("button", { name: "Save question", exact: true })
    .click();
  await expect(
    top(page).getByText("Saved answer:", { exact: false }),
  ).toContainText("Synthetic motivation.");
  await top(page)
    .getByRole("checkbox", {
      name: "Clear this incompatible answer when saving the question",
    })
    .check();
  await top(page)
    .getByRole("button", { name: "Save question", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  expect((await call(page, `/applications/${application.id}`)).answers).toEqual(
    {},
  );
});

test("context selection follows evidence and supports deliberate empty selections", async ({
  page,
}) => {
  const application = (await call(page, "/applications?status=draft&limit=1"))
    .items[0];
  await go(page, `applications?application=${application.id}`);
  await top(page).locator(".agent-preparation > summary").click();
  await top(page)
    .getByRole("button", { name: "Prepare context", exact: true })
    .click();
  await top(page)
    .getByRole("checkbox", {
      name: "Choose specific career entries",
      exact: true,
    })
    .check();
  await top(page)
    .getByRole("checkbox", {
      name: "Choose specific approved claims",
      exact: true,
    })
    .check();
  const evidence = top(page).getByRole("group", { name: /Career entries/ });
  await evidence
    .getByRole("button", { name: "Clear matching", exact: true })
    .click();
  await expect(
    top(page)
      .getByRole("group", { name: /Approved claims/ })
      .getByRole("checkbox"),
  ).toHaveCount(0);
  const download = page.waitForEvent("download");
  await top(page)
    .getByRole("button", { name: "Save & download context", exact: true })
    .click();
  await download;
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  const contexts = await call(
    page,
    `/contexts?application_id=${application.id}&summary=true`,
  );
  const context = await call(page, `/contexts/${contexts.items[0].id}`);
  expect(context.payload.knowledge).toEqual([]);
  expect(context.payload.claims).toEqual([]);
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
  await page.locator(".career-entry-card .career-entry-title").first().click();
  await top(page)
    .getByRole("button", { name: "Edit details", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(2);
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
  const button = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  await button.click();
  await expect(page.locator("main")).toHaveAttribute("inert", "");
  for (let index = 0; index < 15; index++) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(() => !!document.activeElement?.closest(".sidebar")),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(button).toBeFocused();
  await expect(page.locator("main")).not.toHaveAttribute("inert", "");
  await button.click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator("main")).not.toHaveAttribute("inert", "");
});

test("mobile applications, templates and funnel stay usable inside the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await go(page, "applications");
  await expect(page.locator(".application-list")).toBeVisible();
  await expect(page.locator(".stage-overview .btn")).toHaveCount(5);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  await go(page, "templates");
  await expect(page.locator(".mobile-template-picker select")).toBeVisible();
  const chooser = page.locator(".mobile-template-picker select");
  await expect(chooser.locator("option")).toHaveCount(30);
  await chooser.selectOption({ index: 1 });
  await expect(
    page.getByRole("heading", { name: "Synthetic CV 01", exact: true }),
  ).toBeVisible();
  expect(
    await page
      .locator(".templates-layout > section")
      .evaluate((element) => element.getBoundingClientRect().top),
  ).toBeLessThan(844);
  await go(page, "overview");
  await page.getByText("View counts as a table", { exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  await expect(
    page.getByRole("region", { name: "Application journey chart" }),
  ).toHaveAttribute("tabindex", "0");
});

test("records export downloads valid JSON with undated career entries", async ({
  page,
}) => {
  await go(page, "settings?section=workspace");
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export records", exact: true })
    .click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.json$/);
  const records = await call(page, "/export");
  expect(records.knowledge.some((entry: any) => entry.dates === null)).toBe(
    true,
  );
  await expect(page.getByText("Openings 0.9.1", { exact: false })).toHaveCount(
    0,
  );
});

test("independent career, source and provider editors recover their own concurrent versions", async ({
  page,
}) => {
  const recover = async (field: string, value: string) => {
    await top(page)
      .getByRole("button", { name: "Review latest values", exact: true })
      .click();
    await expect(top(page).locator(".conflict-recovery")).toContainText(value);
    await top(page)
      .getByRole("button", {
        name: "Reload editor and discard draft",
        exact: true,
      })
      .click();
    await expect(top(page).locator(`[name=${field}]`)).toHaveValue(value);
  };
  const entry = await call(page, "/career/knowledge", "POST", {
    kind: "project",
    title: "Concurrent career entry",
  });
  await go(page, "career?section=knowledge&q=Concurrent");
  await page.locator(".career-entry-title").first().click();
  await top(page)
    .getByRole("button", { name: "Edit details", exact: true })
    .click();
  await top(page).locator("[name=title]").fill("My entry draft");
  await call(page, `/career/knowledge/${entry.id}`, "PATCH", {
    expected_version: entry.version,
    title: "Newer career title",
  });
  await top(page)
    .getByRole("button", { name: "Save entry", exact: true })
    .click();
  await recover("title", "Newer career title");
  await top(page)
    .getByRole("button", { name: "Save entry", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();
  const source = await call(page, "/sources", "POST", {
    name: "Concurrent search",
    kind: "jobspy",
    config: {
      query: "synthetic engineer",
      location: "Zurich",
      providers: ["linkedin"],
    },
  });
  await go(page, "collection?q=Concurrent");
  await page
    .locator(".companycard")
    .getByRole("button", { name: "Edit settings", exact: true })
    .click();
  await top(page).locator("[name=name]").fill("My source draft");
  await call(page, `/sources/${source.id}`, "PATCH", {
    expected_version: source.version,
    name: "Newer search name",
  });
  await top(page)
    .getByRole("button", { name: "Save search", exact: true })
    .click();
  await recover("name", "Newer search name");
  await top(page)
    .getByRole("button", { name: "Save search", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await go(page, "settings?section=collection");
  const provider = (await call(page, "/providers")).items.find(
    (item: any) => item.capability.supported,
  );
  const card = page.locator(".provider-grid > article").filter({
    has: page.getByRole("heading", { name: provider.name, exact: true }),
  });
  await card
    .getByRole("button", { name: "Edit request settings", exact: true })
    .click();
  await top(page).locator("[name=min_interval_seconds]").fill("7");
  await call(page, `/providers/${provider.id}`, "PATCH", {
    expected_version: provider.version,
    min_interval_seconds: provider.policy.min_interval_seconds + 2,
  });
  await top(page)
    .getByRole("button", { name: "Save settings", exact: true })
    .click();
  await recover(
    "min_interval_seconds",
    String(provider.policy.min_interval_seconds + 2),
  );
  await top(page)
    .getByRole("button", { name: "Save settings", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
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

test("application plan, blocking requirements and a stale button action recover", async ({
  page,
}, info) => {
  const title = `Planned role ${info.project.name}`;
  const job = await call(page, "/jobs", "POST", {
    title,
    company: "Deadline Labs",
    posting: "Build services.",
  });
  const application = await call(page, "/applications", "POST", {
    job_id: job.id,
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
  await go(
    page,
    `applications?view=list&readiness=blocked&q=${encodeURIComponent(title)}`,
  );
  const row = page.locator(".application-list tbody tr", { hasText: title });
  await expect(row).toContainText("P1");
  await expect(row).toContainText("1 blocking requirement");
  await expect(
    page.getByRole("combobox", { name: "Filter preparation readiness" }),
  ).toHaveValue("blocked");

  // Another session changes the attempt; the stale button action reloads it.
  await call(page, `/applications/${application.id}`, "PATCH", {
    expected_version: application.version,
    note: "Changed in another session",
  });
  const stage = row.getByRole("combobox", { name: `Stage for ${title}` });
  const reloaded = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/applications?") &&
      response.request().method() === "GET",
  );
  await stage.selectOption("applied");
  await expect(page.locator(".app-toast")).toContainText(
    "changed in another session",
  );
  await reloaded;
  await expect(stage).toHaveValue("draft");
  await stage.selectOption("applied");
  await expect
    .poll(
      async () => (await call(page, `/applications/${application.id}`)).status,
    )
    .toBe("applied");

  await row.getByRole("button", { name: new RegExp(title) }).click();
  await expect(top(page).locator(".requirement-alert")).toContainText(
    "Applications must be written without AI tools.",
  );
  await top(page)
    .getByRole("tab", { name: /Requirements/ })
    .click();
  const requirement = top(page).locator(".requirement-row").first();
  await requirement.getByRole("checkbox", { name: "Resolved" }).check();
  await requirement
    .getByRole("textbox", { name: "Resolution or open question" })
    .fill("The owner writes this letter.");
  await top(page)
    .getByRole("button", { name: "Add requirement", exact: true })
    .click();
  const added = top(page).locator(".requirement-row").last();
  await added.getByRole("combobox", { name: "Kind" }).selectOption("reference");
  await added
    .getByRole("textbox", { name: "Requirement", exact: true })
    .fill("Two professional references.");
  await top(page)
    .getByRole("button", { name: "Save requirements", exact: true })
    .click();
  await expect(top(page).locator(".requirement-alert")).toHaveCount(0);
  const saved = await call(page, `/applications/${application.id}`);
  expect(saved.readiness).toBe("none");
  expect(saved.requirements).toEqual([
    expect.objectContaining({
      kind: "authorship",
      resolved: true,
      note: "The owner writes this letter.",
    }),
    expect.objectContaining({
      kind: "reference",
      text: "Two professional references.",
      blocking: false,
    }),
  ]);

  await top(page).getByRole("tab", { name: "Details", exact: true }).click();
  await top(page).getByRole("combobox", { name: "Priority" }).selectOption("3");
  await top(page).getByLabel("Application deadline").fill("2027-01-15");
  await top(page)
    .getByRole("button", { name: "Save details", exact: true })
    .click();
  await expect
    .poll(async () => {
      const value = await call(page, `/applications/${application.id}`);
      return [value.priority, value.deadline];
    })
    .toEqual([3, "2027-01-15"]);
});

async function agentCall(
  page: Page,
  token: string,
  path: string,
  method = "GET",
  body?: unknown,
) {
  // An agent's request: bearer token, no browser session.
  return page.evaluate(
    async ({ token, path, method, body }) => {
      const response = await fetch("/api/v1" + path, {
        method,
        credentials: "omit",
        headers: {
          "X-Openings-E2E-Setup": "1",
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const value = await response.json();
      if (!response.ok) throw Error(JSON.stringify(value));
      return value;
    },
    { token, path, method, body },
  );
}
async function fitsViewport(page: Page) {
  const width = page.viewportSize()!.width;
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(width);
}

test("the owner answers an agent's question and the agent can read the answer", async ({
  page,
}, info) => {
  const stamp = `${info.project.name} ${Date.now()}`;
  const agent = await call(page, "/tokens", "POST", {
    name: `Synthetic agent ${stamp}`,
  });
  const job = await call(page, "/jobs", "POST", {
    title: `Hybrid role ${stamp}`,
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  const text = `Is a hybrid schedule acceptable? ${stamp}`;
  const asked = await agentCall(page, agent.token, "/questions", "POST", {
    question: text,
    why: "The posting requires two office days each week.",
    subject_type: "job",
    subject_id: job.id,
    choices: ["Yes", "No"],
  });
  const open = (await call(page, "/questions?state=open&limit=1")).total;

  await go(page, "activity");
  await expect(page.locator(".navbadge")).toHaveText(String(open));
  const card = page.getByRole("article", { name: text, exact: true });
  await expect(card).toContainText("two office days");
  await expect(card).toContainText(`Asked by Synthetic agent ${stamp}`);
  await fitsViewport(page);
  // The subject opens the job it is about.
  await card.getByRole("button", { name: /^Job: Hybrid role/ }).click();
  await expect(top(page)).toContainText("Hybrid role");
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();

  // Answer with the keyboard: choose, comment, submit.
  await card.getByRole("radio", { name: "Yes", exact: true }).focus();
  await page.keyboard.press("Space");
  await card.getByRole("textbox").fill("Two days are fine.");
  await card.getByRole("button", { name: "Answer", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".app-toast")).toContainText("Answer saved.");
  await expect(card).toHaveCount(0);
  if (open > 1)
    await expect(page.locator(".navbadge")).toHaveText(String(open - 1));
  else await expect(page.locator(".navbadge")).toHaveCount(0);

  await page.getByLabel("State", { exact: true }).selectOption("answered");
  await expect(card).toContainText("Yes · Two days are fine.");
  await expect(card).toContainText("Answered by Owner (dashboard)");
  await fitsViewport(page);

  const answers = await agentCall(
    page,
    agent.token,
    "/questions?answered_since=" + encodeURIComponent(asked.created_at),
  );
  expect(answers.items).toContainEqual(
    expect.objectContaining({
      id: asked.id,
      state: "answered",
      answer_choice: "Yes",
      answer: "Two days are fine.",
    }),
  );
  await call(page, "/tokens/" + agent.id, "DELETE");
});

test("an agent run, its report and its changes are readable", async ({
  page,
}, info) => {
  const stamp = `${info.project.name} ${Date.now()}`;
  const workflow = `review-inbox ${stamp}`;
  const agent = await call(page, "/tokens", "POST", {
    name: `Synthetic agent ${stamp}`,
  });
  const job = await call(page, "/jobs", "POST", {
    title: `Run subject ${stamp}`,
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  const run = await agentCall(page, agent.token, "/runs", "POST", {
    workflow,
    scope: "One synthetic Inbox job.",
  });
  await agentCall(page, agent.token, `/jobs/${job.id}/notes`, "POST", {
    body: "Synthetic agent note.",
  });
  await agentCall(page, agent.token, "/questions", "POST", {
    question: `Which notice period applies? ${stamp}`,
    subject_type: "job",
    subject_id: job.id,
  });
  await agentCall(page, agent.token, `/runs/${run.id}/finish`, "POST", {
    expected_version: run.version,
    summary: "Reviewed one synthetic job.",
    changes: "Added one note and asked one question.",
    not_done: [
      {
        item: "Shortlist decision",
        reason: "Waiting for the notice period.",
        subject_type: "job",
        subject_id: job.id,
      },
    ],
    checks: [
      { check: "Inbox query re-read" },
      { check: "PDF render", verified: false },
    ],
    limits: "No application was submitted.",
    method: "A salary filter is missing.",
  });

  await go(page, "activity?section=runs");
  const row = page.getByRole("button", { name: new RegExp(workflow) });
  await expect(row).toContainText("Finished");
  await expect(row).toContainText("2 changes · 1 question");
  await fitsViewport(page);
  await row.focus();
  await page.keyboard.press("Enter");

  const report = page.locator(".run-detail");
  await expect(
    report.getByRole("heading", { name: workflow, exact: true }),
  ).toBeVisible();
  await expect(report).toContainText(`Synthetic agent ${stamp}`);
  for (const [heading, content] of [
    ["Scope", "One synthetic Inbox job."],
    ["Summary", "Reviewed one synthetic job."],
    ["Changes", "Added one note and asked one question."],
    ["Not done", "Waiting for the notice period."],
    ["Checks", "Not verified"],
    ["Statement of limits", "No application was submitted."],
    ["Method", "A salary filter is missing."],
    ["Questions for you", "Which notice period applies?"],
  ]) {
    const section = report.locator(".report-section", {
      has: page.getByRole("heading", { name: heading, exact: true }),
    });
    await expect(section).toContainText(content);
  }
  await expect(report).toContainText("Note added · 1");
  await expect(report).toContainText("Question asked · 1");
  const changes = page.locator(".change-list .activity");
  await expect(changes).toHaveCount(2);
  await expect(changes.first()).toContainText("Question asked");
  await expect(changes.last()).toContainText("Note added");
  await expect(changes.last()).toContainText(`Synthetic agent ${stamp}`);
  await fitsViewport(page);
  // A change links to the record it touched.
  await changes
    .last()
    .getByRole("button", { name: /Run subject/ })
    .click();
  await expect(top(page)).toContainText("Run subject");
  await top(page)
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();

  await page.getByRole("button", { name: "Back to runs", exact: true }).click();
  await expect(row).toBeVisible();
  await page.getByRole("tab", { name: "Changes", exact: true }).click();
  await expect(
    page.locator(".change-list .activity", {
      hasText: `Synthetic agent ${stamp}`,
    }),
  ).toHaveCount(2);
  await call(page, "/tokens/" + agent.id, "DELETE");
});

test("application history shows who made each change", async ({
  page,
}, info) => {
  const stamp = `${info.project.name} ${Date.now()}`;
  const agent = await call(page, "/tokens", "POST", {
    name: `Synthetic agent ${stamp}`,
  });
  const job = await call(page, "/jobs", "POST", {
    title: `Attributed role ${stamp}`,
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  const application = await call(page, "/applications", "POST", {
    job_id: job.id,
  });
  await agentCall(
    page,
    agent.token,
    `/applications/${application.id}`,
    "PATCH",
    { expected_version: application.version, priority: 2 },
  );
  // The recorded name outlives the token.
  await call(page, "/tokens/" + agent.id, "DELETE");

  await go(page, `applications?application=${application.id}`);
  await top(page).getByRole("tab", { name: "History", exact: true }).click();
  const entries = top(page).locator(".activity");
  await expect(entries).toHaveCount(2);
  await expect(entries.first()).toContainText("application updated");
  await expect(entries.first()).toContainText(`Synthetic agent ${stamp}`);
  await expect(entries.last()).toContainText("application created");
  await expect(entries.last()).toContainText("Owner (dashboard)");
  await call(page, `/applications/${application.id}`, "PATCH", {
    expected_version: application.version + 1,
    status: "closed",
    outcome: "not_pursued",
  });
});

test("an application is marked ready and a new revision clears the step", async ({
  page,
}, info) => {
  const stamp = `${info.project.name} ${Date.now()}`;
  const title = `Ready role ${stamp}`;
  const job = await call(page, "/jobs", "POST", {
    title,
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  const application = await call(page, "/applications", "POST", {
    job_id: job.id,
  });
  await go(page, `applications?application=${application.id}`);
  const panel = top(page).getByRole("region", { name: "Ready to apply" });
  const mark = panel.getByRole("button", { name: "Mark ready", exact: true });
  await expect(panel).toContainText("No documents");
  await expect(mark).toBeDisabled();

  await top(page)
    .getByRole("button", { name: "Add document", exact: true })
    .click();
  await top(page).locator("input[name=title]").fill("Ready CV");
  await top(page).locator("textarea[name=text]").fill("Synthetic CV text.");
  await top(page).locator("input[type=file]").setInputFiles({
    name: "ready.pdf",
    mimeType: "application/pdf",
    buffer: syntheticPdf(),
  });
  await top(page)
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(panel).toContainText("Needs review");
  await expect(mark).toBeDisabled();
  await top(page)
    .getByRole("button", { name: "Show Ready CV", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "Approve this revision", exact: true })
    .click();
  await expect(panel).toContainText("Reviewed, not marked ready");

  // Mark ready with the keyboard.
  await mark.focus();
  await page.keyboard.press("Enter");
  await expect(top(page).locator(".app-toast")).toContainText(
    "Marked ready to apply.",
  );
  await expect(panel).toContainText("Marked by Owner (dashboard)");
  await expect(
    panel.getByRole("button", { name: "Not ready", exact: true }),
  ).toBeVisible();
  await fitsViewport(page);
  expect((await call(page, `/applications/${application.id}`)).readiness).toBe(
    "ready",
  );

  // The ready queue lists it with its badge.
  await go(
    page,
    `applications?view=list&readiness=ready&sort=ready&q=${encodeURIComponent(title)}`,
  );
  const row = page.locator("tbody tr", { hasText: title });
  await expect(row.locator(".ready-tag")).toHaveText("Ready to apply");
  await expect(
    page.getByRole("button", { name: /^Ready to apply \d+$/ }),
  ).toHaveClass(/selected/);
  await fitsViewport(page);

  // A new revision changes what was judged, so the step is cleared.
  await row.getByRole("button", { name: new RegExp(title) }).click();
  await top(page)
    .getByRole("button", { name: "Show Ready CV", exact: true })
    .click();
  await top(page)
    .getByRole("button", { name: "New revision", exact: true })
    .click();
  await top(page).locator("textarea[name=text]").fill("Changed synthetic CV.");
  await top(page)
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(panel).toContainText("Missing PDF");
  await expect(mark).toBeDisabled();
  await top(page).getByRole("tab", { name: "History", exact: true }).click();
  const cleared = top(page).locator(".activity", {
    hasText: "application ready cleared",
  });
  await expect(cleared).toContainText("A new document revision was saved");
  await expect(cleared).toContainText("Owner (dashboard)");
  const current = await call(page, `/applications/${application.id}`);
  expect([current.readiness, current.ready_at]).toEqual(["missing_pdf", null]);
  await call(page, `/applications/${application.id}`, "PATCH", {
    expected_version: current.version,
    status: "closed",
    outcome: "not_pursued",
  });
});
