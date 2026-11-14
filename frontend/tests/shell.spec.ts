import { test, expect, type Page } from "./fixtures";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// The shell: navigation groups, routes, the theme, screens
// loaded on demand, and everything of it operated from the keyboard alone.
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

const focused = (page: Page) =>
  page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return el
      ? `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}:${(
          el.getAttribute("aria-label") ||
          el.textContent ||
          ""
        )
          .trim()
          .slice(0, 40)}`
      : "";
  });
const main = (page: Page) => page.locator("main#content");
// Safari moves through links with Option+Tab; the other browsers with Tab.
const tabKey = (page: Page) =>
  page.context().browser()?.browserType().name() === "webkit"
    ? "Alt+Tab"
    : "Tab";

test("keyboard only: skip link, navigation and theme", async ({ page }) => {
  // The first Tab reaches the skip link; Enter moves focus to the content.
  await page.keyboard.press(tabKey(page));
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(main(page)).toBeFocused();
  expect(page.url()).toContain("#today");

  // Navigation by keyboard: focus the Applications link and press Enter.
  const nav = page.getByRole("navigation", { name: "Main" });
  await nav.getByRole("link", { name: /^Applications/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".main h1")).toHaveText("Applications");
  await expect(
    nav.getByRole("link", { name: /^Applications/ }),
  ).toHaveAttribute("aria-current", "page");
  // A new screen takes focus, so reading continues at its content.
  await expect(main(page)).toBeFocused();
  await expect(page).toHaveTitle("Applications · Openings");

  // Theme: the button says what it will do, keeps focus and is remembered.
  const root = page.locator("html");
  const before = await root.getAttribute("data-theme");
  const other = before === "dark" ? "light" : "dark";
  const theme = page.getByRole("button", { name: /^Theme:/ });
  await theme.focus();
  await expect(theme).toHaveAccessibleName(
    `Theme: ${before}. Switch to ${other}`,
  );
  await page.keyboard.press("Enter");
  await expect(root).toHaveAttribute("data-theme", other);
  await expect(theme).toBeFocused();
  await expect(theme).toHaveAccessibleName(
    `Theme: ${other}. Switch to ${before}`,
  );

  // The top bar has no density control.
  await expect(page.getByRole("button", { name: /^Density/ })).toHaveCount(0);

  await page.reload();
  await expect(page.locator(".main h1")).toHaveText("Applications");
  await expect(root).toHaveAttribute("data-theme", other);
  await expect(root).not.toHaveAttribute("data-density");
});

test("keyboard only: the sidebar reaches every destination in its group", async ({
  page,
}) => {
  test.skip(isNarrow(page), "The sidebar exists on wide screens.");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.locator(".nav-group > .eyebrow")).toHaveText([
    "Work",
    "Library",
    "System",
  ]);
  await expect(nav.getByRole("link")).toHaveText([
    /^Today/,
    /^Applications/,
    /^Jobs/,
    /^Career/,
    /^Preferences/,
    /^Templates/,
    /^Collection/,
    /^Settings/,
  ]);
  // Tab walks the links in order, starting after the brand.
  await page.getByRole("link", { name: "Openings", exact: true }).focus();
  const order: string[] = [];
  for (let index = 0; index < 8; index++) {
    await page.keyboard.press(tabKey(page));
    order.push((await focused(page)).split(":")[1]);
  }
  expect(order.map((label) => label.replace(/\d.*$/, ""))).toEqual([
    "Today",
    "Applications",
    "Jobs",
    "Career",
    "Preferences",
    "Templates",
    "Collection",
    "Settings",
  ]);
  await page.keyboard.press("Enter");
  await expect(page.locator(".main h1")).toHaveText("Settings");
  await expect(main(page)).toBeFocused();
});

test("keyboard only: More opens, keeps focus, closes with Escape and navigates", async ({
  page,
}) => {
  test.skip(!isNarrow(page), "The bottom bar exists on narrow screens.");
  const bar = page.getByRole("navigation", { name: "Main" });
  await expect(bar.getByRole("link")).toHaveText([
    /^Today/,
    /^Applications/,
    /^Jobs/,
    /^Career/,
  ]);
  const more = page.getByRole("button", { name: "More", exact: true });
  await more.focus();
  await page.keyboard.press("Enter");
  await expect(more).toHaveAttribute("aria-expanded", "true");
  const sheet = page.getByRole("dialog", { name: "More destinations" });
  const links = sheet.getByRole("navigation", { name: "More" });
  await expect(links.getByRole("link")).toHaveText([
    "Preferences",
    "Templates",
    "Collection",
    "Settings",
  ]);
  await expect(sheet.getByRole("link", { name: "Preferences" })).toBeFocused();
  await expect(main(page)).toHaveAttribute("inert", "");
  // Focus stays in the sheet in both directions: back from the first link to
  // the last one, then forward.
  await page.keyboard.press("Shift+Tab");
  await expect(sheet.getByRole("link").last()).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("link", { name: "Preferences" })).toBeFocused();
  // Escape closes it and focus returns to More.
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  await expect(more).toBeFocused();
  await expect(more).toHaveAttribute("aria-expanded", "false");
  await expect(main(page)).not.toHaveAttribute("inert", "");
  // Open again and go to Templates: the sheet closes, the screen takes focus
  // and More is the current tab.
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("link", { name: "Templates" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".main h1")).toHaveText("Templates");
  await expect(sheet).toHaveCount(0);
  await expect(main(page)).toBeFocused();
  await expect(more).toHaveAttribute("aria-current", "page");
  await expect(
    page.evaluate(() => document.documentElement.scrollWidth),
  ).resolves.toBeLessThanOrEqual(page.viewportSize()!.width);
});

test("each screen has one address; an unknown or retired one opens Today", async ({
  page,
}) => {
  const [first] = (
    await page.evaluate(() =>
      fetch("/api/v1/applications?stage=applied&limit=1").then((response) =>
        response.json(),
      ),
    )
  ).items;
  await go(page, `review?application=${first.id}&tab=timeline`);
  await expect(page.locator(".main h1")).toHaveText(first.job.title);
  await expect(page.getByRole("tab", { name: "Timeline" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // Names of earlier versions are no longer rewritten.
  for (const route of ["overview", "inbox", "shortlist", "no-such-screen"]) {
    await go(page, route);
    await expect(page.locator(".main h1")).toHaveText("Today");
    await expect(page).toHaveURL(new RegExp(`#${route}$`));
  }
  // The Activity page is gone: its address opens Today, and no link leads to it.
  await go(page, "activity?section=runs");
  await expect(page.locator(".main h1")).toHaveText("Today");
  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link", {
      name: /^Activity/,
    }),
  ).toHaveCount(0);
});

test("navigation counts come from the workspace", async ({ page }) => {
  const api = (path: string) =>
    page.evaluate(
      (path) => fetch("/api/v1" + path).then((response) => response.json()),
      path,
    );
  const ready = (await api("/applications?limit=1")).stage_counts.ready;
  const applications = page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: /^Applications/ });
  if (ready)
    await expect(applications).toHaveAccessibleName(
      // Browsers differ on a space before the comma of the hidden count.
      new RegExp(`^Applications ?, ${ready} application`),
    );
  else await expect(applications.locator(".count")).toHaveCount(0);
  const fresh = (await api("/jobs?triage=new&limit=1")).total;
  await expect(
    page
      .getByRole("navigation", { name: "Main" })
      .getByRole("link", { name: /^Jobs/ }),
  ).toHaveAccessibleName(new RegExp(`^Jobs ?, ${fresh} new jobs?$`));
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
  await expect(page.locator(".main h1")).toHaveText("Templates");
  await expect(
    page.getByRole("region", { name: "Templates by kind" }),
  ).toBeVisible();
});

// One test per width, so the workers share them.
for (const width of [360, 390, 600, 860, 861, 1024, 1280, 1600])
  test(`no horizontal page scroll at ${width} px on every screen`, async ({
    page,
  }) => {
    test.skip(
      test.info().project.name !== "chromium",
      "Widths are set by the test; one project is enough.",
    );
    test.setTimeout(60000);
    const api = (path: string) =>
      page.evaluate(
        (path) => fetch("/api/v1" + path).then((response) => response.json()),
        path,
      );
    const ready = (await api("/applications?stage=ready&limit=1")).items[0];
    const sent = (await api("/applications?stage=interview&limit=1")).items[0];
    // A job with every kind of signal: a likely duplicate of a job in progress.
    const flagged = (await api("/jobs?signal=likely_duplicate&limit=1"))
      .items[0];
    await page.setViewportSize({ width, height: 900 });
    for (const [route, title] of [
      ["today", "Today"],
      ["applications", "Applications"],
      ["applications?section=stats", "Applications"],
      [`review?application=${ready.id}`, ready.job.title],
      [`review?application=${sent.id}&tab=timeline`, sent.job.title],
      [`review?application=${ready.id}&tab=details`, ready.job.title],
      ["jobs", "Jobs"],
      [`jobs?job=${flagged.id}`, "Jobs"],
      ["jobs?section=dismissed", "Jobs"],
      ["jobs?section=all", "Jobs"],
      ["career?section=knowledge", "Career"],
      ["career?section=claims", "Career"],
      ["preferences", "Preferences"],
      ["templates", "Templates"],
      ["templates?section=rules", "Templates"],
      ["collection", "Collection"],
      ["collection?section=runs", "Collection"],
      ["collection?section=providers", "Collection"],
      ["settings", "Settings"],
      ["settings?section=skills", "Settings"],
      ["settings?section=backup", "Settings"],
      ["settings?section=workspace", "Settings"],
    ]) {
      await page.goto("/#" + route);
      await expect(page.locator(".main h1")).toHaveText(title);
      await expect(page.locator(".loading")).toHaveCount(0);
      await page.waitForLoadState("networkidle");
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
        `${route} at ${width}px`,
      ).toBeLessThanOrEqual(width);
    }
  });
