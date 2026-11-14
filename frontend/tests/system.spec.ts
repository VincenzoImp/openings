import { readFileSync } from "node:fs";
import { test, expect, type Page } from "./fixtures";
import {
  call,
  card,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  type Cookies,
} from "./session";

// The System screens: Collection (sources, runs and tasks, the provider
// request gate) and Settings (agent access, backup and restore, workspace).
// The browser-test server runs no acquisition worker, so a run stays queued
// until it is stopped. Each test starts from the seeded workspace (fixtures.ts).
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
const toast = (page: Page, text: string) =>
  expect(page.locator(".toast").last()).toContainText(text);
const dialog = (page: Page) => page.locator("dialog[open]").last();
const sourceRow = (page: Page, name: string) =>
  page.getByRole("table", { name: "Sources" }).locator("tr", { hasText: name });
async function recover(
  scope: ReturnType<Page["locator"]>,
  field: string,
  value: string,
) {
  await scope
    .getByRole("button", { name: "Review latest values", exact: true })
    .click();
  await expect(scope.locator(".conflict-recovery")).toContainText(value);
  await scope
    .getByRole("button", { name: "Reload editor and discard draft" })
    .click();
  await expect(scope.locator(`[name=${field}]`)).toHaveValue(value);
}

test("a saved search is added, switched on, run once, stopped and removed", async ({
  page,
}) => {
  const name = unique("Synthetic search");
  await go(page, "collection");
  // The empty list offers the same button: use the one of the screen.
  await page
    .locator(".page-head")
    .getByRole("button", { name: "Add a search", exact: true })
    .click();
  const editor = page.locator("section", {
    has: page.getByRole("heading", { name: "New search" }),
  });
  await expect(
    editor.getByRole("heading", { name: "New search" }),
  ).toBeFocused();
  await editor.getByLabel("Name", { exact: true }).fill(name);
  await editor.getByLabel("Keywords").fill("synthetic engineer");
  await editor.getByLabel("Location", { exact: true }).fill("Zurich");
  await editor.getByLabel("Country").fill("switzerland");
  await editor.getByLabel("Titles to keep").fill("engineer, developer");
  await editor.getByLabel("Frequency").selectOption("daily");
  await editor.getByRole("button", { name: "Add a time" }).click();
  await editor.getByLabel("Time zone").fill("Europe/Zurich");
  await editor.getByRole("button", { name: "Save the search" }).click();
  await toast(page, "Search saved.");
  await expect(editor).toHaveCount(0);
  const source = (
    await call(page, "/sources?summary=false&limit=200")
  ).items.find((item: { name: string }) => item.name === name);
  expect(source.config).toMatchObject({
    query: "synthetic engineer",
    location: "Zurich",
    country: "switzerland",
    providers: ["linkedin", "indeed"],
  });
  expect(source.filters.titles).toEqual(["engineer", "developer"]);
  expect(source.schedule).toMatchObject({
    kind: "daily",
    times: ["07:00", "08:00"],
    timezone: "Europe/Zurich",
  });
  expect(source.enabled).toBe(false);

  // Find it, switch it on, run it once and stop the run.
  await page.getByRole("searchbox", { name: "Find a source" }).fill(name);
  const row = sourceRow(page, name);
  await expect(row).toHaveCount(1);
  await row.getByRole("switch").click();
  await toast(page, `${name} is on.`);
  await expect
    .poll(async () => (await call(page, `/sources/${source.id}`)).enabled)
    .toBe(true);
  await row.getByRole("button", { name: "Run once", exact: true }).click();
  await toast(page, `${name} is collecting.`);
  // Its run, with one task per portal: stop one task, queue it again, then
  // stop the whole run.
  await row.getByRole("link", { name: "Runs of this search" }).click();
  await expect(page).toHaveURL(
    new RegExp(`section=runs&source_id=${source.id}`),
  );
  const runs = page.getByRole("table", { name: "Collection runs" });
  const run = runs.locator("tr", { hasText: name }).first();
  await run.getByRole("button", { name: "Tasks", exact: true }).click();
  const linkedin = runs.locator("tr.nested", { hasText: "Task: linkedin" });
  await expect(
    runs.locator("tr.nested", { hasText: "Task: indeed" }),
  ).toBeVisible();
  await linkedin.getByRole("button", { name: "Stop task" }).click();
  await toast(page, "Task stopped.");
  await linkedin.getByRole("button", { name: "Retry" }).click();
  await toast(page, "The task is queued again");
  await run.getByRole("button", { name: "Stop run", exact: true }).click();
  await toast(page, "The run was stopped");
  await expect(run).toContainText("Stopped");
  await expect(runs).toContainText("Settings this run froze");
  await fitsViewport(page);

  // Remove it from the list; it asks first.
  await go(page, `collection?q=${encodeURIComponent(name)}`);
  await sourceRow(page, name)
    .getByRole("button", { name: `Remove ${name}` })
    .click();
  await dialog(page).getByRole("button", { name: "Remove source" }).click();
  await toast(page, `${name} was removed. Its jobs are kept.`);
  await expect(sourceRow(page, name)).toHaveCount(0);
});

test("a preview through paused providers asks no job board and saves nothing", async ({
  page,
}) => {
  // The browser tests never reach a job board: both search providers are
  // paused in the request gate for the preview, then set back as they were.
  const providers = async () =>
    (await call(page, "/providers")).items.filter((item: { id: string }) =>
      ["linkedin", "indeed"].includes(item.id),
    ) as { id: string; version: number; policy: { enabled: boolean } }[];
  const before = await providers();
  const gate = async (enabled: (id: string) => boolean) => {
    for (const provider of await providers())
      await call(page, `/providers/${provider.id}`, "PATCH", {
        enabled: enabled(provider.id),
        expected_version: provider.version,
      });
  };
  await gate(() => false);
  try {
    const sources = (await call(page, "/sources?limit=1")).total;
    await go(page, "collection");
    await page
      .locator(".page-head")
      .getByRole("button", { name: "Add a search", exact: true })
      .click();
    const editor = page.locator("section", {
      has: page.getByRole("heading", { name: "New search" }),
    });
    await editor.getByLabel("Name", { exact: true }).fill(unique("Preview"));
    await editor.getByLabel("Keywords").fill("synthetic engineer");
    await editor.getByLabel("Location", { exact: true }).fill("Zurich");
    // No country by default; Indeed searches one country's site and needs it.
    const country = editor.getByLabel("Country");
    await expect(country).toHaveValue("");
    await expect(country).toHaveAttribute("required", "");
    await editor.getByRole("checkbox", { name: "Indeed" }).uncheck();
    await expect(country).not.toHaveAttribute("required", "");
    await editor.getByRole("checkbox", { name: "Indeed" }).check();
    await country.fill("switzerland");
    await editor.getByRole("button", { name: "Preview results" }).click();
    await toast(page, "Preview complete. No job was saved.");
    const result = editor.getByRole("region", { name: /^Preview:/ });
    await expect(result).toContainText("Preview: 0 matches");
    await expect(result).toContainText("LinkedIn: provider paused.");
    await expect(result).toContainText("Indeed: provider paused.");
    await editor.getByRole("button", { name: "Cancel", exact: true }).click();
    expect((await call(page, "/sources?limit=1")).total).toBe(sources);
  } finally {
    await gate(
      (id) => before.find((provider) => provider.id === id)!.policy.enabled,
    );
  }
});

test("sources filter by kind and act in bulk, with run-only limits", async ({
  page,
}) => {
  const stamp = unique("Bulk");
  const made = [];
  for (const city of ["Basel", "Bern"])
    made.push(
      await call(page, "/sources", "POST", {
        name: `${stamp} ${city}`,
        kind: "jobspy",
        config: {
          query: "synthetic analyst",
          location: city,
          country: "switzerland",
          providers: ["indeed"],
        },
      }),
    );
  await go(page, `collection?q=${encodeURIComponent(stamp)}`);
  await page
    .getByRole("group", { name: "Kind of source" })
    .getByRole("button", { name: /^Company boards/ })
    .click();
  await expect(page.getByText("No source matches")).toBeVisible();
  await page
    .getByRole("group", { name: "Kind of source" })
    .getByRole("button", { name: /^Searches/ })
    .click();
  await expect(page).toHaveURL(/kind=search/);
  await page
    .getByRole("checkbox", { name: "Select the sources on this page" })
    .check();
  const bar = page.getByRole("region", { name: "Selected sources" });
  await expect(bar).toContainText("2 sources selected");
  await bar.getByRole("button", { name: "Configure" }).click();
  await dialog(page).getByLabel("Change acquisition limits").check();
  await dialog(page).getByLabel("Results per portal").fill("7");
  await dialog(page).getByRole("button", { name: "Save changes" }).click();
  await toast(page, "Collection settings saved.");
  for (const source of made)
    expect(
      (await call(page, `/sources/${source.id}`)).config.results_wanted,
    ).toBe(7);
  // Run with options: limits for this run only.
  await page
    .getByRole("checkbox", { name: "Select the sources on this page" })
    .check();
  await bar.getByRole("button", { name: "Run with options" }).click();
  await dialog(page).getByLabel("Results per portal").fill("3");
  await dialog(page).getByRole("button", { name: "Run with options" }).click();
  await toast(page, "Collection runs queued.");
  const runs = await call(
    page,
    `/collection/runs?source_id=${made[0].id}&summary=false`,
  );
  expect(runs.items[0].overrides).toMatchObject({ results_wanted: 3 });
  expect(
    (await call(page, `/sources/${made[0].id}`)).config.results_wanted,
  ).toBe(7);
  // Stop both runs and remove both sources.
  for (const source of made) {
    const queued = await call(page, `/collection/runs?source_id=${source.id}`);
    await call(page, `/collection/runs/${queued.items[0].id}/cancel`, "POST");
  }
  await page.reload();
  await page
    .getByRole("checkbox", { name: "Select the sources on this page" })
    .check();
  await bar.getByRole("button", { name: "Remove" }).click();
  await dialog(page).getByRole("button", { name: "Remove sources" }).click();
  await toast(page, "Sources removed");
  await fitsViewport(page);
});

test("the source and provider editors recover their own concurrent versions", async ({
  page,
}) => {
  const name = unique("Concurrent search");
  const source = await call(page, "/sources", "POST", {
    name,
    kind: "jobspy",
    config: {
      query: "synthetic engineer",
      location: "Zurich",
      providers: ["linkedin"],
    },
  });
  await go(page, `collection?q=${encodeURIComponent(name)}`);
  await sourceRow(page, name)
    .getByRole("button", { name: "Edit", exact: true })
    .click();
  const editor = page.locator("section", {
    has: page.getByRole("heading", { name: `Edit ${name}` }),
  });
  await editor.locator("[name=name]").fill("My source draft");
  await call(page, `/sources/${source.id}`, "PATCH", {
    expected_version: source.version,
    name: `${name} newer`,
  });
  await editor.getByRole("button", { name: "Save the search" }).click();
  await recover(editor, "name", `${name} newer`);
  await page
    .locator("section", { has: page.getByRole("heading", { name: /^Edit / }) })
    .getByRole("button", { name: "Save the search" })
    .click();
  await toast(page, "Search saved.");
  const latest = await call(page, `/sources/${source.id}`);
  await call(page, "/sources/bulk", "POST", {
    action: "delete",
    items: [{ id: latest.id, expected_version: latest.version }],
  });

  await go(page, "collection?section=providers");
  const provider = (await call(page, "/providers")).items.find(
    (item: { capability: { supported: boolean } }) => item.capability.supported,
  );
  const form = page.getByRole("form", { name: provider.name, exact: true });
  await form.locator("[name=min_interval_seconds]").fill("7");
  await call(page, `/providers/${provider.id}`, "PATCH", {
    expected_version: provider.version,
    min_interval_seconds: provider.policy.min_interval_seconds + 2,
  });
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await recover(
    form,
    "min_interval_seconds",
    String(provider.policy.min_interval_seconds + 2),
  );
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await toast(page, `${provider.name} request settings saved.`);
  // Put the spacing back for the other projects.
  const after = (await call(page, "/providers")).items.find(
    (item: { id: string }) => item.id === provider.id,
  );
  await call(page, `/providers/${provider.id}`, "PATCH", {
    expected_version: after.version,
    min_interval_seconds: provider.policy.min_interval_seconds,
  });
});

test("keyboard only: move through the Collection tabs and pause collection", async ({
  page,
}) => {
  await go(page, "collection");
  const before = await call(page, "/collection");
  await expect(page.getByRole("tab")).toHaveText([
    "Sources",
    "Runs and tasks",
    "Providers",
  ]);
  await page.getByRole("tab", { name: "Sources" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Runs and tasks" })).toBeFocused();
  await expect(page).toHaveURL(/#collection\?section=runs$/);
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Providers" })).toBeFocused();
  await expect(
    page.getByRole("list").filter({ has: page.getByRole("form") }),
  ).toBeVisible();
  // The switch of scheduled collection, by keyboard, and back.
  const master = page.getByRole("switch", { name: /^Scheduled collection is/ });
  await master.focus();
  await page.keyboard.press("Space");
  await toast(page, before.enabled ? "paused" : "is on");
  await expect
    .poll(async () => (await call(page, "/collection")).enabled)
    .toBe(!before.enabled);
  await expect(master).toBeEnabled();
  await master.focus();
  await page.keyboard.press("Space");
  await expect
    .poll(async () => (await call(page, "/collection")).enabled)
    .toBe(before.enabled);
  await go(page, "collection?section=runs&view=tasks");
  const tasks = page.getByRole("table", { name: "Collection tasks" });
  await expect(tasks).toBeVisible();
  // A task's details: what it was asked and what it recorded.
  await tasks.getByRole("button", { name: "Details" }).first().click();
  await expect(tasks.locator("tr.nested").first()).toContainText("asked");
  await fitsViewport(page);
});

test("Settings creates an agent token that is refused owner operations", async ({
  page,
}) => {
  const name = unique("Scoped agent");
  await go(page, "settings?section=agents");
  // Owner-only parts say so; the form offers an agent token first.
  await expect(card(page, "Tokens")).toContainText("Owner only");
  const create = card(page, "Create a token");
  const kind = create.getByRole("group", { name: "Token kind" });
  await expect(kind.getByRole("button", { name: "Agent" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(create).toContainText(
    "Cannot change your password, manage tokens, restore a backup",
  );
  await create.getByLabel("Token name").fill(name);
  await create.getByLabel("Token name").press("Enter");
  const secret = await create.locator("pre.secret").innerText();
  expect(secret).toMatch(/^op_/);
  const tokens = page.getByRole("table", { name: "API tokens" });
  const row = tokens.locator("tr", { hasText: name });
  await expect(row.locator(".tag")).toHaveText("Agent");
  await create.getByRole("button", { name: "I have saved it" }).click();
  await kind.getByRole("button", { name: "Owner" }).click();
  await expect(create).toContainText("Full access");
  await create.getByLabel("Token name").fill(`Owner ${name}`);
  await create.getByRole("button", { name: "Create", exact: true }).click();
  const ownerRow = tokens.locator("tr", { hasText: `Owner ${name}` });
  await expect(ownerRow.locator(".tag")).toHaveText("Owner");
  await fitsViewport(page);

  const attempt = (path: string, method = "GET", body?: unknown) =>
    page.evaluate(
      async ({ secret, path, method, body }) => {
        const response = await fetch("/api/v1" + path, {
          method,
          credentials: "omit",
          headers: {
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
  // An agent may write the local notes of a skill: it is attributed.
  const notes = await call(page, "/skills/manage-sources/notes");
  expect(
    await attempt("/skills/manage-sources/notes", "PUT", {
      expected_version: notes.version,
      text: `Noted by ${name}.`,
    }),
  ).toEqual([200, null]);
  await go(page, "activity?section=timeline");
  await expect(
    page
      .locator("main li", { hasText: "Skill notes updated" })
      .first()
      .locator(".actor"),
  ).toHaveText(name);

  // Revoke both tokens with the keyboard; each asks first.
  await go(page, "settings?section=agents");
  for (const label of [name, `Owner ${name}`]) {
    await page.getByRole("button", { name: `Revoke ${label}` }).focus();
    await page.keyboard.press("Enter");
    await dialog(page).getByRole("button", { name: "Revoke token" }).focus();
    await page.keyboard.press("Enter");
    await toast(page, `${label} was revoked.`);
    await expect(
      tokens.getByRole("row").filter({
        has: page.getByText(label, { exact: true }),
      }),
    ).toHaveCount(0);
  }
  expect(await attempt("/jobs?limit=1")).toEqual([401, "unauthorized"]);
});

test("backup, records export and a guarded restore", async ({ page }) => {
  await go(page, "settings?section=backup");
  const workspace = await call(page, "/workspace");
  await expect(page.locator(".stats")).toContainText(
    "Largest backup you can restore",
  );
  const backup = page.waitForEvent("download");
  await card(page, "Back up")
    .getByRole("button", { name: "Download a backup" })
    .click();
  expect((await backup).suggestedFilename()).toMatch(/^openings-.*\.sqlite$/);
  const exported = page.waitForEvent("download");
  await card(page, "Back up")
    .getByRole("button", { name: "Export records" })
    .click();
  expect((await exported).suggestedFilename()).toBe("openings-records.json");
  const records = await call(page, "/export");
  expect(
    records.knowledge.some((entry: { dates: unknown }) => entry.dates === null),
  ).toBe(true);
  expect(records.skill_notes.length).toBeGreaterThan(0);
  // The workspace tab names the version and schema of this workspace.
  await go(page, "settings?section=workspace");
  const about = card(page, "This workspace");
  await expect(about).toContainText(workspace.version);
  await expect(about).toContainText(String(workspace.schema_version));
  await expect(card(page, "Change the password")).toContainText("Owner only");
  await expect(card(page, "Retention")).toContainText(
    "never removed automatically",
  );
  await go(page, "settings?section=backup");
  // Restoring is owner only and needs a file and the typed confirmation.
  const restore = card(page, "Restore");
  await expect(restore).toContainText("Owner only");
  const button = restore.getByRole("button", { name: "Restore this file" });
  await expect(button).toBeDisabled();
  await restore.getByLabel("Backup file").setInputFiles({
    name: "synthetic.sqlite",
    mimeType: "application/vnd.sqlite3",
    buffer: Buffer.from("not a database"),
  });
  await expect(button).toBeDisabled();
  await restore.getByLabel("Type RESTORE to confirm").fill("RESTORE");
  await expect(button).toBeEnabled();
  await fitsViewport(page);
  // A file that is not a backup is refused and the workspace stays as it was.
  await button.click();
  await toast(page, "Select a SQLite database backup.");
  // The backup downloaded above restores: the workspace is what it was a
  // moment ago, and the owner stays signed in.
  const jobs = (await call(page, "/jobs?limit=1")).total;
  await restore.getByLabel("Backup file").setInputFiles({
    name: "openings-backup.sqlite",
    mimeType: "application/vnd.sqlite3",
    buffer: readFileSync(await (await backup).path()),
  });
  await restore.getByLabel("Type RESTORE to confirm").fill("RESTORE");
  const reloaded = page.waitForEvent("load");
  await button.click();
  await reloaded;
  await expect(page.locator(".main h1")).toHaveText("Settings");
  expect((await call(page, "/jobs?limit=1")).total).toBe(jobs);
});

test("automatic backups: download a daily one, delete a pre-upgrade copy", async ({
  page,
}) => {
  await go(page, "settings?section=backup");
  const automatic = card(page, "Automatic backups");
  await expect(automatic).toContainText("Owner only");
  await expect(automatic).toContainText("Last backup: Today");
  const daily = automatic.getByRole("table", { name: "Daily backups" });
  const first = daily.getByRole("row").nth(1);
  const name = (await first.locator(".title").textContent())!;
  expect(name).toMatch(/^openings-\d{8}T\d{6}Z\.sqlite$/);
  const download = page.waitForEvent("download");
  await first.getByRole("link", { name: `Download ${name}` }).click();
  expect((await download).suggestedFilename()).toBe(name);
  // Daily backups rotate by themselves: there is nothing to delete.
  await expect(daily.getByRole("button")).toHaveCount(0);

  const copies = automatic.getByRole("table", {
    name: "Copies before an upgrade",
  });
  const rows = copies.locator("tbody tr");
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
  const copy = (await rows.first().locator(".title").textContent())!;
  expect(copy).toMatch(/\.pre-schema13-\d{8}T\d{6}Z\.sqlite$/);
  await rows
    .first()
    .getByRole("button", { name: `Delete ${copy}` })
    .click();
  const confirm = dialog(page);
  await expect(confirm).toContainText(`Delete ${copy}?`);
  await expect(confirm).toContainText(/\d+(\.\d)? MiB/);
  await fitsViewport(page);
  await confirm.getByRole("button", { name: "Delete copy" }).click();
  await toast(page, `${copy} was deleted.`);
  await expect(rows).toHaveCount(count - 1);
  await expect(copies.getByText(copy, { exact: true })).toHaveCount(0);
});

test("the password form and the list of operations", async ({ page }) => {
  // A real change signs out every browser session, the shared one of these
  // tests too: the test answers the request as the server does.
  // test_archive.py changes the password over REST and MCP.
  const sent: unknown[] = [];
  await page.route("**/api/v1/auth/password", (route) => {
    sent.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        updated: true,
        sign_in_required: true,
        api_tokens_preserved: true,
      },
    });
  });
  await go(page, "settings?section=workspace");
  const password = card(page, "Change the password");
  await password
    .getByLabel("New password", { exact: true })
    .fill("synthetic-new-password");
  await password
    .getByLabel("Confirm the new password")
    .fill("synthetic-other-password");
  await password.getByRole("button", { name: "Change the password" }).click();
  await toast(page, "The passwords do not match.");
  expect(sent).toEqual([]);
  await password
    .getByLabel("Confirm the new password")
    .fill("synthetic-new-password");
  await password.getByRole("button", { name: "Change the password" }).click();
  // Every browser session signs in again.
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  expect(sent).toEqual([{ password: "synthetic-new-password" }]);
  await page.unroute("**/api/v1/auth/password");
  // The session was not really ended: loading the page again signs back in.
  await page.goto("/#settings?section=agents");
  await page.reload();
  await expect(page.locator(".main h1")).toHaveText("Settings");
  // The operations an agent can call, as the workspace serves them.
  const list = page.waitForEvent("popup");
  await page.getByRole("link", { name: "Available operations" }).click();
  const operations = await list;
  await expect(operations.locator("body")).toContainText('"operations"');
  await operations.close();
});

test("the connection snippet wraps inside its block with a copy button, and the tabs scroll", async ({
  page,
}) => {
  await go(page, "settings?section=agents");
  const block = page.locator(".code-block").filter({
    has: page.getByLabel("MCP configuration", { exact: true }),
  });
  const code = block.getByLabel("MCP configuration", { exact: true });
  await expect(code).toContainText("claude mcp add");
  // Nothing hides past the right edge: the lines wrap.
  const fits = await code.evaluate(
    (element) => element.scrollWidth <= element.clientWidth + 1,
  );
  expect(fits).toBe(true);
  const copy = block.getByRole("button", {
    name: "Copy the MCP configuration",
  });
  const inner = (await copy.boundingBox())!;
  const outer = (await block.boundingBox())!;
  expect(inner.x).toBeGreaterThanOrEqual(outer.x);
  expect(inner.x + inner.width).toBeLessThanOrEqual(outer.x + outer.width + 1);
  await expect(
    page.getByRole("button", { name: "Copy the MCP address" }),
  ).toBeVisible();
  // The last tab of Settings is reached and shown whole.
  const strip = page.getByRole("tablist", { name: /Settings/ });
  const last = strip.getByRole("tab").last();
  await last.click();
  await expect(last).toHaveAttribute("aria-selected", "true");
  const width = page.viewportSize()!.width;
  await expect
    .poll(async () => {
      const box = (await last.boundingBox())!;
      return box.x >= 0 && box.x + box.width <= width;
    })
    .toBe(true);
  if (isNarrow(page)) {
    const scrolls = await strip.evaluate(
      (element) => element.scrollWidth > element.clientWidth,
    );
    expect(scrolls).toBe(true);
    await expect(strip).toHaveAttribute("data-hidden", /start|both/);
  }
  await fitsViewport(page);
});
