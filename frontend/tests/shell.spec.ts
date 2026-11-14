import { test, expect, type Page } from "./fixtures";
import {
  call,
  go,
  heading,
  isPhone,
  ownerSession,
  type Cookies,
} from "./session";

// The shell: the sidebar and the phone's bars, the routes, the account menu
// and the theme, the global keyboard, the ⌘K palette and Add job, and the
// screens loaded on demand inside it.
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

const main = (page: Page) => page.locator("main#content");
const nav = (page: Page) =>
  page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
const mod = (page: Page) =>
  page.context().browser()?.browserType().name() === "webkit" ||
  process.platform === "darwin"
    ? "Meta"
    : "Control";

test("keyboard only: skip link, sidebar navigation and focus on the new screen", async ({
  page,
}) => {
  test.skip(isPhone(page), "The sidebar exists on wide screens.");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(main(page)).toBeFocused();
  expect(page.url()).toContain("#today");

  const applications = nav(page).getByRole("link", { name: /^Applications/ });
  await applications.focus();
  await page.keyboard.press("Enter");
  await expect(heading(page)).toHaveText("Applications");
  await expect(applications).toHaveAttribute("aria-current", "page");
  await expect(main(page)).toBeFocused();
  await expect(page).toHaveTitle("Applications · Openings");
  await expect(page).toHaveURL(/#applications$/);
});

test("the sidebar: brand, Add job, search, three groups with icons, the account", async ({
  page,
}) => {
  test.skip(isPhone(page), "The sidebar exists on wide screens.");
  const sidebar = nav(page);
  await expect(sidebar.getByRole("link")).toHaveText([
    /^Today/,
    /^Jobs/,
    /^Applications/,
    /^Profile/,
    /^Preferences/,
    /^Templates/,
    /^Sources/,
    /^Settings/,
  ]);
  await expect(sidebar.getByRole("group")).toHaveCount(3);
  await expect(sidebar.getByRole("group", { name: "You" })).toBeVisible();
  await expect(sidebar.getByRole("group", { name: "Workspace" })).toBeVisible();
  // Every item has an icon; nothing of the agent remains.
  for (const link of await sidebar.getByRole("link").all())
    await expect(link.locator("svg")).toHaveCount(1);
  await expect(sidebar.getByText(/Activity|agent/i)).toHaveCount(0);
  await expect(sidebar.getByRole("button", { name: "Add job" })).toBeVisible();
  await expect(
    sidebar.getByRole("button", { name: /^Search/ }),
  ).toHaveAttribute("aria-keyshortcuts", "Meta+K Control+K /");
  await expect(
    sidebar.getByRole("button", { name: /^Alex Morgan|^You/ }),
  ).toBeVisible();
  // No desktop top bar: no Refresh, Theme or Density button at rest.
  for (const name of [/^Refresh/, /^Theme/, /^Density/])
    await expect(page.getByRole("button", { name })).toHaveCount(0);
});

test("the needs-you counts come from the workspace", async ({ page }) => {
  const ready = (await call(page, "/applications?limit=1")).stage_counts.ready;
  const fresh = (await call(page, "/jobs?triage=new&limit=1")).total;
  const links = nav(page);
  await expect(
    links.getByRole("link", { name: /Applications/ }),
  ).toHaveAccessibleName(
    ready ? new RegExp(`${ready} ready applications`) : /^Applications$/,
  );
  await expect(links.getByRole("link", { name: /Jobs/ })).toHaveAccessibleName(
    fresh ? new RegExp(`${fresh} new jobs`) : /^Jobs$/,
  );
  // A new job counts at once: the shell reads again after a write.
  await page.keyboard.press("n");
  const dialog = page.getByRole("dialog", { name: "Add a job" });
  await dialog
    .getByLabel("Address or posting text")
    .fill(`Counted role ${test.info().project.name}\n\nA synthetic posting.`);
  await dialog.getByRole("button", { name: "Add job" }).click();
  await expect(links.getByRole("link", { name: /Jobs/ })).toHaveAccessibleName(
    new RegExp(`${fresh + 1} new jobs`),
  );
});

test("the account menu sets the theme, shows the shortcuts and signs out", async ({
  page,
}) => {
  test.skip(isPhone(page), "On a phone these are under More.");
  const root = page.locator("html");
  const account = nav(page).getByRole("button", { name: /Alex Morgan|You/ });
  await account.click();
  const menu = page.getByRole("menu", { name: "Account" });
  await menu.getByRole("menuitemradio", { name: "Dark" }).click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await account.click();
  await expect(
    menu.getByRole("menuitemradio", { name: "Dark" }),
  ).toHaveAttribute("aria-checked", "true");
  await menu.getByRole("menuitemradio", { name: "Light" }).click();
  await expect(root).toHaveAttribute("data-theme", "light");
  // System follows the browser and forgets the choice.
  await page.emulateMedia({ colorScheme: "dark" });
  await account.click();
  await menu.getByRole("menuitemradio", { name: "System" }).click();
  await expect(root).toHaveAttribute("data-theme", "dark");
  expect(
    await page.evaluate(() => localStorage.getItem("openings-theme")),
  ).toBeNull();
  await page.emulateMedia({ colorScheme: "light" });
  await expect(root).toHaveAttribute("data-theme", "light");

  await account.click();
  await menu.getByRole("menuitem", { name: "Keyboard shortcuts" }).click();
  const sheet = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(sheet).toContainText("Go to Jobs");
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(account).toBeFocused();

  await account.click();
  await menu.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.locator("input[name=password]")).toBeVisible();
});

test("the phone: top bar, bottom bar, More and a pushed page with a back chevron", async ({
  page,
}) => {
  test.skip(!isPhone(page), "The bars exist on phones.");
  const bar = nav(page);
  // Icon above label; a needs-you count sits on the icon.
  await expect(bar.getByRole("link")).toHaveText([
    /Today$/,
    /Jobs$/,
    /Applications$/,
    /Profile$/,
  ]);
  const top = page.getByRole("banner");
  await expect(top.getByRole("heading", { level: 1 })).toHaveText("Today");
  await expect(top.getByRole("button", { name: "Search" })).toBeVisible();
  await expect(top.getByRole("button", { name: "Add job" })).toBeVisible();

  const more = bar.getByRole("button", { name: "More" });
  await more.click();
  const menu = page.getByRole("menu", { name: "More" });
  await expect(menu.getByRole("menuitem")).toHaveText([
    "Preferences",
    "Templates",
    "Sources",
    "Settings",
    "Sign out",
  ]);
  await expect(menu.getByRole("menuitemradio")).toHaveText([
    "System",
    "Light",
    "Dark",
  ]);
  await menu.getByRole("menuitem", { name: "Templates" }).click();
  await expect(heading(page)).toHaveText("Templates");
  await expect(more).toHaveAttribute("data-current", "true");

  // A second-level page: its title and the way back.
  const [application] = (await call(page, "/applications?stage=ready&limit=1"))
    .items;
  await go(page, `applications/${application.id}`);
  await expect(heading(page)).toHaveText(application.job.title);
  await top.getByRole("link", { name: "Back to Applications" }).click();
  await expect(heading(page)).toHaveText("Applications");
  await expect(
    page.evaluate(() => document.documentElement.scrollWidth),
  ).resolves.toBeLessThanOrEqual(page.viewportSize()!.width);
});

test("g and a letter go to a screen; ? shows the shortcuts; n adds a job", async ({
  page,
}) => {
  for (const [letter, title] of [
    ["j", "Jobs"],
    ["a", "Applications"],
    ["p", "Profile"],
    ["t", "Today"],
  ]) {
    await page.keyboard.press("g");
    await page.keyboard.press(letter);
    await expect(heading(page)).toHaveText(title);
  }
  await expect(page).toHaveURL(/#today$/);
  await page.keyboard.press("?");
  await expect(
    page.getByRole("dialog", { name: "Keyboard shortcuts" }),
  ).toBeVisible();
  // Inside a dialog the shortcuts rest.
  await page.keyboard.press("g");
  await page.keyboard.press("j");
  await expect(page).toHaveURL(/#today$/);
  await page.keyboard.press("Escape");
  await page.keyboard.press("n");
  const add = page.getByRole("dialog", { name: "Add a job" });
  await expect(add).toBeVisible();
  await expect(add.getByLabel("Address or posting text")).toBeFocused();
  // Typing in a field is never a shortcut.
  await page.keyboard.type("g j");
  await expect(page).toHaveURL(/#today$/);
  await page.keyboard.press("Escape");
  await expect(add).toBeHidden();
});

test("⌘K and / open the palette: jobs, applications and commands", async ({
  page,
}) => {
  const [job] = (await call(page, "/jobs?triage=new&limit=1")).items;
  await page.keyboard.press(`${mod(page)}+k`);
  const palette = page.getByRole("dialog", { name: "Search and commands" });
  const input = palette.getByRole("combobox");
  await expect(input).toBeFocused();
  // Commands at rest; the first one is active.
  await expect(palette.getByRole("option").first()).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await input.fill(job.title);
  const hit = palette
    .getByRole("group", { name: "Jobs" })
    .getByRole("option", { name: new RegExp(job.title) })
    .first();
  await expect(hit).toBeVisible();
  await hit.click();
  await expect(palette).toBeHidden();
  await expect(page).toHaveURL(new RegExp(`#jobs\\?job=${job.id}$`));

  // An application by its company, opened with the keyboard.
  const [application] = (await call(page, "/applications?stage=ready&limit=1"))
    .items;
  await page.keyboard.press("Escape");
  await main(page).focus();
  await page.keyboard.press("/");
  await expect(input).toBeFocused();
  await input.fill(application.job.title);
  await expect(
    palette.getByRole("group", { name: "Applications" }).getByRole("option"),
  ).not.toHaveCount(0);
  // Move to the application with the arrows and open it.
  const applicationIndex = await palette
    .getByRole("option")
    .evaluateAll(
      (all, title) =>
        all.findIndex(
          (option) =>
            option.closest("[role=group]")?.getAttribute("aria-label") ===
              "Applications" && !!option.textContent?.startsWith(title),
        ),
      application.job.title,
    );
  expect(applicationIndex).toBeGreaterThanOrEqual(0);
  for (let index = 0; index < applicationIndex; index++)
    await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`#applications/${application.id}$`));
  await expect(heading(page)).toHaveText(application.job.title);

  // A command: go to Settings.
  await page.keyboard.press(`${mod(page)}+k`);
  await input.fill("Go to Settings");
  await page.keyboard.press("Enter");
  await expect(heading(page)).toHaveText("Settings");
  // Nothing matches: the palette says so.
  await page.keyboard.press(`${mod(page)}+k`);
  await input.fill("zzzz no such thing");
  await expect(palette.getByRole("status")).toContainText("Nothing matches");
  await page.keyboard.press("Escape");
  await expect(palette).toBeHidden();
});

test("Add job: one field, optional details, the job opens", async ({
  page,
}) => {
  const title = `Shell added role ${test.info().project.name}`;
  if (isPhone(page))
    await page
      .getByRole("banner")
      .getByRole("button", { name: "Add job" })
      .click();
  else await nav(page).getByRole("button", { name: "Add job" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a job" });
  const submit = dialog.getByRole("button", { name: "Add job" });
  await expect(submit).toBeDisabled();
  await dialog
    .getByLabel("Address or posting text")
    .fill("We build synthetic data tools. You write Python every day.");
  await dialog.getByText("More details").click();
  await dialog.getByLabel("Role").fill(title);
  await dialog.getByLabel("Company").fill("Example Labs");
  await submit.click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/#jobs\?job=/);
  const id = new URL(page.url()).hash.split("job=")[1];
  const job = await call(page, `/jobs/${id}`);
  expect(job.title).toBe(title);
  expect(job.company).toBe("Example Labs");
  expect(job.posting).toContain("synthetic data tools");
  await expect(
    page.getByRole("status").filter({ hasText: `Added “${title}”` }),
  ).toBeVisible();

  // An address already in the workspace is named before adding it again.
  const known = (await call(page, "/jobs?limit=20")).items.find(
    (item: { url: string }) => /^https?:\/\//.test(item.url),
  );
  test.skip(!known, "The seeded workspace has a job with an address.");
  await page.keyboard.press("n");
  await dialog.getByLabel("Address or posting text").fill(known.url);
  await dialog.getByLabel("Address or posting text").blur();
  await expect(dialog.getByText("Already in your workspace")).toBeVisible();
  await dialog.getByRole("button", { name: "Open it" }).click();
  await expect(page).toHaveURL(new RegExp(`#jobs\\?job=${known.id}$`));
});

test("each screen has one address; an unknown or retired one opens Today", async ({
  page,
}) => {
  for (const route of [
    "overview",
    "inbox",
    "career",
    "collection",
    "activity?section=runs",
    `review?application=x`,
    "no-such-screen",
  ]) {
    await page.goto("/#" + route);
    await expect(heading(page)).toHaveText("Today");
    await expect(page).toHaveURL(/#today$/);
  }
});

test("a screen that fails to load offers a reload", async ({ page }) => {
  await page.route("**/assets/Templates-*.js", (route) => route.abort());
  errors.set(page, []);
  page.removeAllListeners("pageerror");
  await page.goto("/#templates");
  await expect(
    page.getByRole("alert").filter({ hasText: "could not be loaded" }),
  ).toBeVisible();
  await page.unroute("**/assets/Templates-*.js");
  await page
    .getByRole("button", { name: "Reload the dashboard", exact: true })
    .click();
  await expect(heading(page)).toHaveText("Templates");
  await expect(
    page.getByRole("region", { name: "Templates", exact: true }),
  ).toBeVisible();
});

// One test per width, so the workers share them.
for (const width of [360, 390, 600, 719, 720, 1024, 1280, 1600])
  test(`no horizontal scroll at ${width} px on every screen`, async ({
    page,
  }) => {
    test.skip(
      test.info().project.name !== "chromium",
      "Widths are set by the test; one project is enough.",
    );
    test.setTimeout(60000);
    const ready = (await call(page, "/applications?stage=ready&limit=1"))
      .items[0];
    const sent = (await call(page, "/applications?stage=interview&limit=1"))
      .items[0];
    // A job with every kind of signal: a likely duplicate of a job in progress.
    const flagged = (await call(page, "/jobs?signal=likely_duplicate&limit=1"))
      .items[0];
    await page.setViewportSize({ width, height: 900 });
    for (const [route, title] of [
      ["today", "Today"],
      ["applications", "Applications"],
      ["applications?section=stats", "Applications"],
      [`applications/${ready.id}`, ready.job.title],
      [`applications/${sent.id}?tab=timeline`, sent.job.title],
      [`applications/${ready.id}?tab=details`, ready.job.title],
      ["jobs", "Jobs"],
      // On a phone the job is its own page, titled by the job.
      [`jobs?job=${flagged.id}`, width < 720 ? flagged.title : "Jobs"],
      ["jobs?section=dismissed", "Jobs"],
      ["jobs?section=all", "Jobs"],
      ["profile", "Profile"],
      ["preferences", "Preferences"],
      ["templates", "Templates"],
      ["templates?tab=source", "Templates"],
      ["templates?tab=limits", "Templates"],
      ["sources", "Sources"],
      ["settings", "Settings"],
      ["settings?section=agents", "Settings"],
      ["settings?section=data", "Settings"],
      ["settings?section=advanced", "Settings"],
    ]) {
      await page.goto("/#" + route);
      await expect(heading(page)).toHaveText(title);
      await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
      await page.waitForLoadState("networkidle");
      const [page_, content] = await page.evaluate(() => {
        const box = document.getElementById("content")!;
        return [
          document.documentElement.scrollWidth,
          box.scrollWidth - box.clientWidth,
        ];
      });
      expect(page_, `${route} at ${width}px`).toBeLessThanOrEqual(width);
      expect(content, `${route} content at ${width}px`).toBeLessThanOrEqual(0);
    }
  });
