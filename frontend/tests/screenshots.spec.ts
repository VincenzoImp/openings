import { join, resolve } from "node:path";
import { test, expect, type Page } from "./fixtures";
import { call, go, ownerSession } from "./session";

// Images of every screen of the seeded workspace for visual review, not a
// pixel comparison: `npm run screenshots` writes them to frontend/screenshots/
// (desktop 1440×1000 and mobile 390×844, light and dark), and CI uploads them
// as the `screenshots` artifact of a pull request that changes the dashboard.
// `npm run screenshots -- --docs` writes the light desktop images the user
// documentation embeds to docs/images/ instead. A new screen or a key state
// (empty, populated, dialog open) gets one line in SCREENS.
type Screen = {
  name: string;
  /** The hash route, or a function of the seeded workspace that returns it. */
  route: string | ((page: Page) => Promise<string>);
  /** Make the state to capture once the screen is shown. */
  open?: (page: Page) => Promise<void>;
  /** The file name under docs/images, for an image the docs embed. */
  docs?: string;
  signedOut?: boolean;
};

const first = async (page: Page, path: string) =>
  (await call(page, path)).items[0].id as string;

const SCREENS: Screen[] = [
  { name: "sign-in", route: "today", signedOut: true },
  { name: "setup", route: "setup?step=record", docs: "setup" },
  { name: "today", route: "today", docs: "today" },
  {
    name: "palette",
    route: "today",
    open: async (page) => {
      await page.keyboard.press("/");
      const palette = page.getByRole("dialog", { name: "Search and commands" });
      await palette.getByRole("combobox").fill("engineer");
      await expect(
        palette.getByRole("group", { name: "Jobs" }).getByRole("option"),
      ).not.toHaveCount(0);
    },
  },
  {
    name: "shortcuts",
    route: "today",
    open: async (page) => {
      await page.keyboard.press("?");
      await expect(page.locator("dialog[open]")).toBeVisible();
    },
  },
  { name: "applications", route: "applications", docs: "applications" },
  { name: "applications-stats", route: "applications?section=stats" },
  {
    name: "review",
    route: async (page) =>
      `applications/${await first(page, "/applications?stage=ready&limit=1")}`,
    docs: "review",
  },
  { name: "jobs", route: "jobs", docs: "jobs" },
  {
    name: "jobs-selected",
    route: async (page) =>
      `jobs?job=${await first(page, "/jobs?signal=likely_duplicate&triage=new&limit=1")}`,
  },
  {
    name: "jobs-bulk",
    route: "jobs",
    open: async (page) => {
      await page.locator(".jobs-list .ui-row-main").first().focus();
      await page.keyboard.press("x");
      await page.keyboard.press("Shift+J");
      await page.keyboard.press("Shift+J");
      await expect(
        page.getByRole("toolbar", { name: "3 selected" }),
      ).toBeVisible();
    },
  },
  {
    name: "jobs-filter",
    route: "jobs",
    open: async (page) => {
      await page
        .getByRole("button", { name: /^Filter/ })
        .filter({ visible: true })
        .first()
        .click();
    },
  },
  {
    name: "jobs-dismissed",
    route: "jobs?section=dismissed&dismissed_by=agent",
  },
  { name: "jobs-all", route: "jobs?section=all" },
  { name: "jobs-empty", route: "jobs?q=no%20job%20has%20this%20title" },
  {
    name: "jobs-add-dialog",
    route: "jobs",
    open: async (page) => {
      await page
        .getByRole("button", { name: "Add job" })
        .filter({ visible: true })
        .first()
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
    },
  },
  { name: "profile", route: "profile?section=knowledge", docs: "career" },
  { name: "preferences", route: "preferences", docs: "preferences" },
  { name: "templates", route: "templates", docs: "templates" },
  { name: "sources", route: "sources", docs: "collection" },
  { name: "settings", route: "settings" },
  { name: "skills", route: "settings?section=skills", docs: "skills" },
  { name: "backup", route: "settings?section=backup" },
];

const ROOT = resolve(import.meta.dirname, "../..");
const DOCS = !!process.env.OPENINGS_SCREENSHOTS_DOCS;
const VIEWPORTS = {
  desktop: { width: 1440, height: 1000 },
  mobile: { width: 390, height: 844 },
};
const THEMES = ["light", "dark"] as const;

async function capture(page: Page, screen: Screen, path: string) {
  if (!screen.signedOut) await page.context().addCookies(ownerSession());
  // Open a page of the app first, so a route can read the workspace.
  await page.goto("/");
  const route =
    typeof screen.route === "string" ? screen.route : await screen.route(page);
  if (screen.signedOut)
    await expect(page.locator("input[name=password]")).toBeVisible();
  else await go(page, route);
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".loading")).toHaveCount(0);
  await screen.open?.(page);
  // The shell fills the viewport and its content scrolls inside it. For a
  // full-page image the frame grows with the content instead: the sidebar
  // spans the whole height and the phone's bars sit above and below it.
  await page.addStyleTag({ content: FULL_PAGE });
  await page.screenshot({ path, fullPage: true, animations: "disabled" });
}

const FULL_PAGE = `
  .ui-app { height: auto; min-height: 100dvh; }
  .ui-app-grid { min-height: 100dvh; }
  .ui-app-content { overflow: visible; flex: none; }
  .ui-app-side { height: auto; }
`;

for (const [size, viewport] of Object.entries(VIEWPORTS))
  for (const theme of THEMES) {
    if (DOCS && (size !== "desktop" || theme !== "light")) continue;
    test.describe(`${size} ${theme}`, () => {
      test.use({ viewport });
      test.beforeEach(async ({ page }) => {
        await page.addInitScript((value) => {
          try {
            localStorage.setItem("openings-theme", value);
          } catch {}
        }, theme);
      });
      for (const screen of SCREENS) {
        if (DOCS && !screen.docs) continue;
        test(screen.name, async ({ page }) => {
          const path = DOCS
            ? join(ROOT, "docs/images", `${screen.docs}.png`)
            : join(
                ROOT,
                "frontend/screenshots",
                `${size}-${theme}`,
                `${screen.name}.png`,
              );
          await capture(page, screen, path);
        });
      }
      // The design system gallery (ui.html), which the dashboard never serves.
      if (!DOCS)
        test("ui-gallery", async ({ page }) => {
          await page.route("**/ui.html", (route) =>
            route.fulfill({
              path: join(ROOT, "frontend/dist/ui.html"),
              contentType: "text/html",
            }),
          );
          await page.goto("/ui.html");
          await page.waitForLoadState("networkidle");
          await page.screenshot({
            path: join(
              ROOT,
              "frontend/screenshots",
              `${size}-${theme}`,
              "ui-gallery.png",
            ),
            fullPage: true,
            animations: "disabled",
          });
        });
    });
  }
