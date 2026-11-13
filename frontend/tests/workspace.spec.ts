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

test("Settings creates an agent token that is refused token management", async ({
  page,
}, info) => {
  const stamp = `${info.project.name} ${Date.now()}`;
  const name = `Scoped agent ${stamp}`;
  await go(page, "settings?section=agents");
  // The form offers an agent token first; the owner chooses the kind.
  const kind = page.getByLabel("Token kind", { exact: true });
  await expect(kind).toHaveValue("agent");
  await expect(page.locator(".token-kind-hint")).toContainText(
    "Cannot change your password, manage tokens, restore a backup",
  );
  await page.getByLabel("Token name", { exact: true }).fill(name);
  await page.getByLabel("Token name", { exact: true }).press("Enter");
  const secret = await page.locator(".new-token code").innerText();
  expect(secret).toMatch(/^op_/);
  const row = page.locator(".token-list .settingrow", { hasText: name });
  await expect(row.locator(".tag")).toHaveText("Agent");
  await kind.selectOption("owner");
  await expect(page.locator(".token-kind-hint")).toContainText("Full access");
  await page.getByLabel("Token name", { exact: true }).fill(`Owner ${stamp}`);
  await page.getByRole("button", { name: "Create token", exact: true }).click();
  const ownerRow = page.locator(".token-list .settingrow", {
    hasText: `Owner ${stamp}`,
  });
  await expect(ownerRow.locator(".tag")).toHaveText("Owner");
  await fitsViewport(page);

  // The agent token works for the job search and is refused owner operations.
  const attempt = (path: string, method = "GET", body?: unknown) =>
    page.evaluate(
      async ({ secret, path, method, body }) => {
        const response = await fetch("/api/v1" + path, {
          method,
          credentials: "omit",
          headers: {
            "X-Openings-E2E-Setup": "1",
            "Content-Type": "application/json",
            Authorization: "Bearer " + secret,
          },
          body: body === undefined ? undefined : JSON.stringify(body),
        });
        const value = await response.json();
        return [response.status, value.error?.code ?? null];
      },
      { secret, path, method, body },
    );
  expect(await attempt("/jobs?limit=1")).toEqual([200, null]);
  expect(await attempt("/tokens")).toEqual([403, "forbidden"]);
  expect(await attempt("/tokens", "POST", { name: "Escalation" })).toEqual([
    403,
    "forbidden",
  ]);
  expect(
    await attempt("/auth/password", "POST", { password: "changed-password" }),
  ).toEqual([403, "forbidden"]);
  const job = await call(page, "/jobs", "POST", {
    title: `Scoped token job ${stamp}`,
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  expect(
    await attempt(`/jobs/${job.id}/notes`, "POST", { body: "Synthetic note." }),
  ).toEqual([200, null]);

  // Activity names the agent by its token.
  await go(page, "activity?section=timeline");
  await expect(
    page
      .locator("main li", { hasText: "Note added" })
      .first()
      .locator(".actor"),
  ).toHaveText(name);
  await fitsViewport(page);

  // Revoke both tokens from Settings with the keyboard.
  await go(page, "settings?section=agents");
  for (const item of [row, ownerRow]) {
    await item.getByRole("button", { name: "Revoke", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(item).toHaveCount(0);
  }
  expect(await attempt("/jobs?limit=1")).toEqual([401, "unauthorized"]);
});
