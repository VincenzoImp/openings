import { test, expect, type Page } from "@playwright/test";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// The shell: navigation groups, route aliases, theme and density, screens
// loaded on demand, and everything of it operated from the keyboard alone.
let cookies: Cookies = [];
test.beforeAll(async ({ browser }, info) => {
  cookies = await ownerSession(browser, info);
});
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
  await go(page, "overview");
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

test("keyboard only: skip link, navigation, theme and density", async ({
  page,
}) => {
  // The first Tab reaches the skip link; Enter moves focus to the content.
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(main(page)).toBeFocused();
  expect(page.url()).toContain("#overview");

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

  // Density: compact rows, also remembered.
  const density = page.getByRole("button", { name: /^Density:/ });
  await density.focus();
  await page.keyboard.press("Space");
  await expect(root).toHaveAttribute("data-density", "compact");
  await expect(density).toBeFocused();
  await expect(density).toHaveAccessibleName(
    "Density: compact. Switch to comfortable",
  );

  await page.reload();
  await expect(page.locator(".main h1")).toHaveText("Applications");
  await expect(root).toHaveAttribute("data-theme", other);
  await expect(root).toHaveAttribute("data-density", "compact");
  await page.getByRole("button", { name: /^Density:/ }).click();
  await expect(root).not.toHaveAttribute("data-density", "compact");
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
    /^Overview/,
    /^Applications/,
    /^Jobs/,
    /^Activity/,
    /^Career/,
    /^Templates/,
    /^Collection/,
    /^Settings/,
  ]);
  // Tab walks the links in order, starting after the brand.
  await page.getByRole("link", { name: "Openings", exact: true }).focus();
  const order: string[] = [];
  for (let index = 0; index < 8; index++) {
    await page.keyboard.press("Tab");
    order.push((await focused(page)).split(":")[1]);
  }
  expect(order.map((label) => label.replace(/\d.*$/, ""))).toEqual([
    "Overview",
    "Applications",
    "Jobs",
    "Activity",
    "Career",
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
    /^Overview/,
    /^Applications/,
    /^Jobs/,
    /^Activity/,
  ]);
  const more = page.getByRole("button", { name: "More", exact: true });
  await more.focus();
  await page.keyboard.press("Enter");
  await expect(more).toHaveAttribute("aria-expanded", "true");
  const sheet = page.getByRole("dialog", { name: "More destinations" });
  await expect(sheet.getByRole("link")).toHaveText([
    "Career",
    "Templates",
    "Collection",
    "Settings",
  ]);
  await expect(sheet.getByRole("link", { name: "Career" })).toBeFocused();
  await expect(main(page)).toHaveAttribute("inert", "");
  // Focus stays in the sheet in both directions.
  await page.keyboard.press("Shift+Tab");
  await expect(sheet.getByRole("link", { name: "Settings" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("link", { name: "Career" })).toBeFocused();
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

test("design names are aliases and old routes keep their deep links", async ({
  page,
}) => {
  await go(page, "today");
  await expect(page.locator(".main h1")).toHaveText("Overview");
  await expect(page).toHaveURL(/#overview$/);
  await go(page, "jobs?queue=dismissed");
  await expect(page).toHaveURL(/#inbox\?queue=dismissed$/);
  await expect(page.getByRole("tab", { name: "Dismissed" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // Inbox and Shortlist are two queues of the one Jobs destination.
  const jobs = page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: /^Jobs/ });
  for (const route of ["inbox", "shortlist"]) {
    await go(page, route);
    await expect(jobs).toHaveAttribute("aria-current", "page");
  }
  await go(page, "no-such-screen");
  await expect(page.locator(".main h1")).toHaveText("Overview");
});

test("navigation counts come from the workspace and the agent line shows an open run", async ({
  page,
}) => {
  const api = (path: string) =>
    page.evaluate(
      (path) =>
        fetch("/api/v1" + path, {
          headers: { "X-Openings-E2E-Setup": "1" },
        }).then((response) => response.json()),
      path,
    );
  const ready = (await api("/applications?status=draft&limit=1")).ready_count;
  const applications = page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: /^Applications/ });
  if (ready)
    await expect(applications).toHaveAccessibleName(
      new RegExp(`^Applications, ${ready} application`),
    );
  else await expect(applications.locator(".count")).toHaveCount(0);
  // No run is open in the synthetic workspace: the status line is absent.
  const runs = await api("/runs?status=open&limit=1");
  if (!isNarrow(page))
    await expect(page.locator(".sidebar-foot")).toHaveCount(runs.total ? 1 : 0);
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
  await expect(page.locator(".template-option").first()).toBeAttached();
});

test("no horizontal page scroll from 360 to 1600 px on every screen", async ({
  page,
}) => {
  test.skip(
    test.info().project.name !== "chromium",
    "Widths are set by the test; one project is enough.",
  );
  test.setTimeout(120000);
  for (const width of [360, 390, 600, 860, 861, 1024, 1280, 1600]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, title] of [
      ["overview", "Overview"],
      ["applications", "Applications"],
      ["applications?view=list", "Applications"],
      ["inbox", "Inbox"],
      ["activity", "Activity"],
      ["career?section=knowledge", "Career"],
      ["templates", "Templates"],
      ["collection", "Collection"],
      ["settings", "Settings"],
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
  }
});
