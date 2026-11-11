import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// Automated accessibility checks (axe) on every screen, in both themes; the
// Playwright projects supply the desktop and the narrow width. The budget in
// docs/developer/dashboard-design.md: no serious or critical finding against
// WCAG 2.2 AA.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

// Findings inside pages that a later stage of issue #135 rebuilds. Each entry
// names one rule inside one part of one screen and the stage that removes it.
// Never widen an entry to a whole screen or add one for the shell or a design
// component: fix those.
interface Exclusion {
  rule: string;
  within: string;
  stage: number;
  reason: string;
}
const EXCLUSIONS: Record<string, Exclusion[]> = {};

const SCREENS = [
  "overview",
  "applications",
  "applications?view=list",
  "inbox",
  "shortlist",
  "inbox?queue=dismissed",
  "inbox?queue=all",
  "inbox?queue=duplicates",
  "activity",
  "activity?section=requests",
  "activity?section=runs",
  "activity?section=changes",
  "career",
  "career?section=knowledge",
  "career?section=claims",
  "templates",
  "collection",
  "collection?section=companies",
  "settings",
  "settings?section=collection",
  "settings?section=activity",
  "settings?section=workspace",
];

let cookies: Cookies = [];
test.beforeAll(async ({ browser }, info) => {
  cookies = await ownerSession(browser, info);
});

async function findings(page: Page, key: string) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(TAGS)
    .analyze();
  const found: string[] = [];
  for (const violation of violations) {
    if (violation.impact !== "serious" && violation.impact !== "critical")
      continue;
    const excluded = (EXCLUSIONS[key] || []).filter(
      (item) => item.rule === violation.id,
    );
    for (const node of violation.nodes) {
      const target = node.target.join(" ");
      let skip = false;
      for (const item of excluded)
        skip ||= await page
          .locator(target)
          .first()
          .evaluate((el, within) => !!el.closest(within), item.within)
          .catch(() => false);
      if (!skip)
        found.push(
          `${violation.id}: ${target}\n    ${node.failureSummary?.replaceAll("\n", "\n    ")}`,
        );
    }
  }
  return found;
}

async function useTheme(page: Page, theme: string) {
  await page.addInitScript((value) => {
    try {
      localStorage.setItem("openings-theme", value);
    } catch {}
  }, theme);
}
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".loading")).toHaveCount(0);
}

for (const theme of ["light", "dark"]) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await useTheme(page, theme);
    });

    test("the sign-in screen has no serious accessibility finding", async ({
      page,
    }) => {
      await page.goto("/");
      await expect(page.locator("input[name=password]")).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      expect(await findings(page, "sign-in")).toEqual([]);
    });

    for (const screen of SCREENS)
      test(`${screen} has no serious accessibility finding`, async ({
        page,
      }) => {
        await page.context().addCookies(cookies);
        await go(page, screen);
        await settled(page);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        expect(await findings(page, screen)).toEqual([]);
      });

    test("an open job, an open application and the add-job dialog have no serious accessibility finding", async ({
      page,
    }) => {
      await page.context().addCookies(cookies);
      await go(page, "inbox");
      await settled(page);
      await page.locator(".jobmain").first().click();
      await expect(page.locator("dialog[open] .posting")).toBeVisible();
      expect(await findings(page, "job")).toEqual([]);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Add job" }).click();
      await expect(page.locator("dialog[open] input[name=url]")).toBeVisible();
      expect(await findings(page, "add-job")).toEqual([]);
      await page.keyboard.press("Escape");
      await go(page, "applications?view=list");
      await settled(page);
      await page.locator(".application-list .table-link").first().click();
      await expect(page.locator("dialog[open] [role=tablist]")).toBeVisible();
      await settled(page);
      expect(await findings(page, "application")).toEqual([]);
    });

    test("the More sheet has no serious accessibility finding", async ({
      page,
    }) => {
      test.skip(!isNarrow(page), "The More sheet exists on narrow screens.");
      await page.context().addCookies(cookies);
      await go(page, "career");
      await page.getByRole("button", { name: "More", exact: true }).click();
      await expect(page.locator("#more-sheet")).toBeVisible();
      expect(await findings(page, "more")).toEqual([]);
    });
  });
}
