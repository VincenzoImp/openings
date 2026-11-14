import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "./fixtures";
import {
  call,
  fitsViewport,
  go,
  isPhone,
  ownerSession,
  type Cookies,
} from "./session";

// Settings (#227): Account, API & agents, Data and Advanced on one page, a
// sub-navigation on a wide screen and a list of sections on a phone. Each
// test starts from the seeded workspace (fixtures.ts).
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const toast = (page: Page) => page.locator(".ui-toast").last();
test("the sections: a sub-navigation on a wide screen, a list on a phone", async ({
  page,
}) => {
  await go(page, "settings");
  const nav = page.getByRole("navigation", { name: "Settings sections" });
  await expect(nav.getByRole("link")).toHaveText([
    "Account",
    "API & agents",
    "Data",
    "Advanced",
  ]);
  if (isPhone(page)) {
    // The list alone; a section opens as its own page with a way back.
    await expect(page.getByRole("heading", { name: "Account" })).toHaveCount(0);
    await nav.getByRole("link", { name: "Data" }).click();
    await expect(page).toHaveURL(/#settings\?section=data$/);
    await expect(nav).toBeHidden();
    await page.getByRole("link", { name: "All settings" }).click();
    await expect(nav).toBeVisible();
  } else {
    await expect(
      page.getByRole("heading", { name: "Account", level: 2 }),
    ).toBeVisible();
    await expect(nav.getByRole("link", { name: "Account" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  }
  // Settings has no skill text and no agent status.
  for (const id of ["account", "agents", "data", "advanced"]) {
    await go(page, `settings?section=${id}`);
    await expect(page.locator("#content")).not.toContainText("SKILL.md");
    await fitsViewport(page);
  }
});

test("Account: theme, setup guide, sign out and a checked password", async ({
  page,
}) => {
  const sent: unknown[] = [];
  // A real change signs out every browser, the shared session of these tests
  // too: the route answers as the server does.
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
  await go(page, "settings?section=account");
  const theme = page.getByRole("combobox", { name: "Theme" });
  await theme.selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await theme.selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(
    page.getByRole("link", { name: "Open setup guide" }),
  ).toHaveAttribute("href", "#setup");
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();

  await page.getByRole("button", { name: "Change password" }).click();
  const dialog = page.getByRole("dialog", { name: "Change password" });
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(dialog).toContainText("Enter your current password.");
  await dialog.getByLabel("Current password").fill("synthetic-old-password");
  await dialog.getByLabel("New password", { exact: true }).fill("short");
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(dialog).toContainText("Use at least 10 characters.");
  await dialog
    .getByLabel("New password", { exact: true })
    .fill("synthetic-new-password");
  await dialog.getByLabel("Confirm the new password").fill("synthetic-other");
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(dialog).toContainText("The two passwords are not the same.");
  expect(sent).toEqual([]);
  await dialog
    .getByLabel("Confirm the new password")
    .fill("synthetic-new-password");
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  expect(sent).toEqual([
    {
      current_password: "synthetic-old-password",
      password: "synthetic-new-password",
    },
  ]);
});

test("API & agents: three steps, an Agent token by default, copy, revoke", async ({
  page,
  context,
  browserName,
}) => {
  // WebKit has no clipboard permissions to grant; it checks the toast only.
  const clipboard = browserName === "chromium";
  if (clipboard) {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  }
  await go(page, "settings?section=agents");
  await expect(page.locator(".set-step-title")).toContainText([
    "Create a token",
    "Add Openings to your agent",
    "Open your agent and ask",
  ]);
  await expect(page.locator("#content")).toContainText(
    "Openings has no AI of its own; nothing happens until you ask your agent.",
  );

  // A new token: Agent is preselected; the secret is shown once.
  const name = unique("Synthetic agent");
  await page.getByRole("button", { name: "New token" }).click();
  const create = page.getByRole("dialog", { name: "New token" });
  await expect(create.getByRole("radio", { name: /^Agent/ })).toBeChecked();
  await create.getByRole("button", { name: "Create token" }).click();
  await expect(create).toContainText("Give the token a name.");
  await create.getByLabel("Name", { exact: true }).fill(name);
  await create.getByRole("button", { name: "Create token" }).click();
  const shown = page.getByRole("dialog", { name: "Copy your token" });
  const secret = await shown.getByRole("region", { name: "Token" }).innerText();
  expect(secret).toMatch(/^op_/);
  await shown.getByRole("button", { name: "Copy token" }).click();
  await expect(toast(page)).toContainText("Token copied");
  await shown.getByRole("button", { name: "Done" }).click();
  const tokens = page.getByRole("list", { name: "API tokens" });
  const item = tokens.getByRole("listitem").filter({ hasText: name });
  await expect(item).toContainText("Agent · Created");
  await expect(item).toContainText("Never used");
  const token = (await call(page, "/tokens")).items.find(
    (row: { name: string }) => row.name === name,
  );
  expect(token.kind).toBe("agent");
  // The agent token is refused owner operations.
  const status = await page.evaluate(async (secret) => {
    const response = await fetch("/api/v1/tokens", {
      credentials: "omit",
      headers: { Authorization: "Bearer " + secret },
    });
    return response.status;
  }, secret);
  expect(status).toBe(403);

  // The connect snippet, with its copy button inside the block.
  const snippet = page.getByRole("region", { name: "MCP configuration" });
  await expect(snippet).toContainText(
    "claude mcp add --transport http openings",
  );
  await page.getByRole("combobox", { name: "Agent" }).selectOption("codex");
  await expect(snippet).toContainText("bearer_token_env_var");
  await page.getByRole("button", { name: "Copy mcp configuration" }).click();
  await expect(toast(page)).toContainText("Configuration copied");
  if (clipboard) {
    expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
      "[mcp_servers.openings]",
    );
  }
  const fits = await snippet.evaluate(
    (element) => element.scrollWidth <= element.clientWidth + 1,
  );
  expect(fits).toBe(true);
  await expect(
    page.getByRole("link", { name: "API reference" }),
  ).toHaveAttribute("href", "/api/docs");

  // What you can ask: title, summary and example of each skill, no skill text.
  const skills = (await call(page, "/skills")).items as {
    title: string;
    summary: string;
    example: string;
  }[];
  const ask = page.getByRole("list", { name: "What you can ask your agent" });
  await expect(ask.getByRole("listitem")).toHaveCount(skills.length);
  await expect(ask.getByRole("listitem").first()).toContainText(
    skills[0].title,
  );
  await expect(ask.getByRole("listitem").first()).toContainText(
    `“${skills[0].example}”`,
  );

  // Revoke asks first.
  await item.hover();
  await item.getByRole("button", { name: `More actions for ${name}` }).click();
  await page.getByRole("menuitem", { name: "Revoke…" }).click();
  const confirm = page.getByRole("dialog", { name: `Revoke “${name}”?` });
  await confirm.getByRole("button", { name: "Revoke token" }).click();
  await expect(toast(page)).toContainText(`Revoked “${name}”`);
  await expect(item).toHaveCount(0);
  await fitsViewport(page);
});

test("Data: download a backup, the restore dialog, kept copies", async ({
  page,
}) => {
  await go(page, "settings?section=data");
  const backup = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download backup" }).click();
  expect((await backup).suggestedFilename()).toMatch(/^openings-.*\.sqlite$/);
  const exported = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export", exact: true }).click();
  expect((await exported).suggestedFilename()).toMatch(/\.json$/);

  // Restore names what is replaced and what is kept.
  await page.getByRole("button", { name: "Restore from backup…" }).click();
  const restore = page.getByRole("dialog", { name: "Restore from backup" });
  await expect(restore).toContainText("Replaced");
  await expect(restore).toContainText(
    "Your password, your API tokens and this browser's sign-in.",
  );
  const replace = restore.getByRole("button", {
    name: "Replace this workspace",
  });
  await expect(replace).toBeDisabled();
  await restore.getByLabel("Backup file").setInputFiles({
    name: "synthetic.sqlite",
    mimeType: "application/vnd.sqlite3",
    buffer: Buffer.from("not a database"),
  });
  await replace.click();
  await expect(restore).toContainText("Select a SQLite database backup.");
  await fitsViewport(page);
  // The backup just downloaded restores; the page reloads, still signed in.
  const jobs = (await call(page, "/jobs?limit=1")).total;
  await restore.getByLabel("Backup file").setInputFiles({
    name: "openings-backup.sqlite",
    mimeType: "application/vnd.sqlite3",
    buffer: readFileSync(await (await backup).path()),
  });
  const reloaded = page.waitForEvent("load");
  await replace.click();
  await reloaded;
  await expect(page.locator("h1:visible")).toHaveText("Settings");
  expect((await call(page, "/jobs?limit=1")).total).toBe(jobs);

  // Automatic backups download; a copy before an upgrade asks before delete.
  const daily = page.getByRole("list", { name: "Automatic backups" });
  const first = daily.getByRole("listitem").first();
  const download = page.waitForEvent("download");
  await first.hover();
  await first.getByRole("button", { name: /^Download openings-/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^openings-.*\.sqlite$/);
  const copies = page
    .getByRole("list", { name: "Copies before upgrades" })
    .getByRole("listitem");
  const count = await copies.count();
  expect(count).toBeGreaterThan(0);
  await copies.first().hover();
  await copies
    .first()
    .getByRole("button", { name: /^More actions for / })
    .click();
  await page.getByRole("menuitem", { name: "Delete…" }).click();
  const confirm = page.getByRole("dialog", { name: "Delete this copy?" });
  await expect(confirm).toContainText(/\d+(\.\d)? (KB|MB)/);
  await confirm.getByRole("button", { name: "Delete copy" }).click();
  await expect(toast(page)).toContainText("Deleted the copy of");
  await expect(copies).toHaveCount(count - 1);
});

test("Advanced: request limits of the sites in use save on blur", async ({
  page,
}) => {
  await go(page, "settings?section=advanced");
  const table = page.getByRole("table", { name: /Request limits/ });
  const linkedin = table.getByLabel("Seconds between requests to LinkedIn");
  await expect(table.getByRole("row")).not.toHaveCount(1);
  // Only sites the sources use: no Glassdoor in the seeded workspace.
  await expect(table).not.toContainText("Glassdoor");
  const before = (await call(page, "/providers")).items.find(
    (item: { id: string }) => item.id === "linkedin",
  );
  await linkedin.fill("x");
  await linkedin.press("Tab");
  await expect(table).toContainText("A number from 0 to 3600");
  await linkedin.fill("7");
  await linkedin.press("Tab");
  await expect(toast(page)).toContainText(
    "LinkedIn: 7 seconds between requests",
  );
  await expect
    .poll(
      async () =>
        (await call(page, "/providers")).items.find(
          (item: { id: string }) => item.id === "linkedin",
        ).policy.min_interval_seconds,
    )
    .toBe(7);
  expect(before.policy.min_interval_seconds).not.toBe(7);
  const workspace = await call(page, "/workspace");
  await expect(page.locator("#content")).toContainText(workspace.version);
  await expect(page.locator("#content")).toContainText(
    String(workspace.schema_version),
  );
});

test("Settings with its dialogs open has no serious accessibility finding", async ({
  page,
}) => {
  const check = async () => {
    // A dialog or menu still fading in would be measured half blended.
    await page.evaluate(() =>
      Promise.all(
        document
          .getAnimations()
          .map((animation) => animation.finished.catch(() => undefined)),
      ),
    );
    const { violations } = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      violations
        .filter((item) => ["serious", "critical"].includes(item.impact ?? ""))
        .map(
          (item) => `${item.id}: ${item.nodes.map((n) => n.target).join(" ")}`,
        ),
    ).toEqual([]);
  };
  for (const theme of ["light", "dark"]) {
    await page.emulateMedia({ colorScheme: theme as "light" | "dark" });
    await go(page, "settings?section=agents");
    await page.reload();
    await page.getByRole("button", { name: "New token" }).click();
    await check();
    await page.keyboard.press("Escape");
    await go(page, "settings?section=data");
    await page.getByRole("button", { name: "Restore from backup…" }).click();
    await check();
    await page.keyboard.press("Escape");
    await go(page, "settings?section=account");
    await page.getByRole("button", { name: "Change password" }).click();
    await check();
  }
});
