import { test, expect } from "./fixtures";
import { call, findings, go, isPhone, settled, useTheme } from "./session";

// Automated accessibility checks (axe, `findings` in session.ts) on every
// screen; the Playwright projects supply the desktop and the narrow width.
// The dark theme runs on `chromium` only: contrast.test.mjs proves the
// tokens of both themes. The budget: no serious or critical finding against
// WCAG 2.2 AA.

// Every screen, grouped by area so that a test reads a few screens in a row.
const SCREENS: Record<string, string[]> = {
  "Today and Applications": [
    "today",
    "applications",
    "applications?stage=applied",
    "applications?section=stats",
  ],
  Jobs: [
    "jobs",
    "jobs?section=dismissed",
    "jobs?section=dismissed&dismissed_by=agent",
    "jobs?section=all",
    "jobs?signal=likely_duplicate",
  ],
  "Profile, Preferences and Templates": [
    "profile",
    "preferences",
    "templates",
    "templates?tab=source",
    "templates?tab=files",
    "templates?tab=limits",
  ],
  "Sources and Settings": [
    "sources",
    "settings",
    "settings?section=agents",
    "settings?section=data",
    "settings?section=advanced",
  ],
  Setup: ["setup", "setup?step=jobs", "setup?step=cv", "setup?step=done"],
};

for (const theme of ["light", "dark"]) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      test.skip(
        theme === "dark" && test.info().project.name !== "chromium",
        "The dark theme runs on chromium only.",
      );
      await useTheme(page, theme);
    });

    test.describe("signed out", () => {
      test.use({ signedIn: false });
      test("the sign-in screen has no serious accessibility finding", async ({
        page,
      }) => {
        await page.goto("/");
        await expect(page.locator("input[name=password]")).toBeVisible();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        expect(await findings(page)).toEqual([]);
      });
    });

    for (const [area, screens] of Object.entries(SCREENS))
      test(`${area} have no serious accessibility finding`, async ({
        page,
      }) => {
        test.setTimeout(90000);
        for (const screen of screens) {
          // A fresh load per screen, as a reader arriving at its address.
          await page.goto("about:blank");
          await go(page, screen);
          await settled(page);
          await expect(page.locator("html")).toHaveAttribute(
            "data-theme",
            theme,
          );
          expect(await findings(page), screen).toEqual([]);
        }
      });

    test("Today's reply form and a focused row with its actions have no serious accessibility finding", async ({
      page,
    }) => {
      await go(page, "today");
      await settled(page);
      const waiting = page
        .getByRole("region", { name: "Applications waiting for a reply" })
        .getByRole("link")
        .first();
      await waiting.focus();
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("r");
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page)).toEqual([]);
    });

    test("a job with its details, the dismissed job, the dialogs and the selection have no serious accessibility finding", async ({
      page,
    }) => {
      test.setTimeout(90000);
      await go(page, "today");
      const api = (path: string) =>
        page.evaluate(
          (path) => fetch("/api/v1" + path).then((response) => response.json()),
          path,
        );
      const flagged = (await api("/jobs?signal=likely_duplicate&limit=1"))
        .items[0];
      const dismissed = (await api("/jobs?triage=dismissed&limit=1")).items[0];
      // A likely duplicate with its notes and history open.
      await go(page, `jobs?job=${flagged.id}`);
      await settled(page);
      await expect(page.locator(".jobs-callout")).toBeVisible();
      await page.getByText("Notes and history").click();
      await settled(page);
      expect(await findings(page)).toEqual([]);
      await go(page, `jobs?section=dismissed&job=${dismissed.id}`);
      await settled(page);
      expect(await findings(page)).toEqual([]);
      // The … menu's dialogs: correct details, merge with another job.
      await go(page, `jobs?job=${flagged.id}`);
      await settled(page);
      const more = page
        .getByRole("button", { name: "More actions" })
        .filter({ visible: true });
      await more.click();
      await page.getByRole("menuitem", { name: /^Correct details/ }).click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page)).toEqual([]);
      await page
        .locator("dialog[open]")
        .getByRole("button", { name: "Cancel" })
        .click();
      await expect(page.locator("dialog[open]")).toHaveCount(0);
      await more.click();
      await page.getByRole("menuitem", { name: /^Merge with another/ }).click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page)).toEqual([]);
      await page
        .locator("dialog[open]")
        .getByRole("button", { name: "Cancel" })
        .click();
      await expect(page.locator("dialog[open]")).toHaveCount(0);
      // The list: the filters, then a dismissal's toast with its reason.
      await go(page, "jobs");
      await settled(page);
      if (isPhone(page))
        await page.getByRole("button", { name: "Filter and sort" }).click();
      else await page.getByRole("button", { name: "Filter" }).click();
      await settled(page);
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("Escape");
      await page.keyboard.press("d");
      await page.getByRole("button", { name: "Add reason" }).click();
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("Escape");
      // Selected rows with the bulk actions.
      await page.locator(".jobs-list .ui-row-main").first().focus();
      await page.keyboard.press("x");
      await page.keyboard.press("Shift+J");
      await expect(
        page.getByRole("toolbar", { name: "2 selected" }),
      ).toBeVisible();
      expect(await findings(page)).toEqual([]);
    });

    test("the application page in each stage, its dialogs and the list's bulk bar have no serious accessibility finding", async ({
      page,
    }) => {
      test.setTimeout(90000);
      await go(page, "today");
      const first = async (query: string) =>
        (await call(page, `/applications?${query}&limit=1`)).items[0].id;
      const pages = [
        ["ready", await first("stage=ready&sort=deadline")],
        ["shortlisted", await first("stage=shortlisted&needs=documents")],
        ["interview", await first("stage=interview&q=Research")],
        ["closed", await first("stage=closed&outcome=rejected")],
      ];
      for (const [stage, id] of pages) {
        await go(page, `applications/${id}`);
        await expect(page.locator(".ui-skeleton")).toHaveCount(0);
        await settled(page);
        expect(await findings(page)).toEqual([]);
      }
      // The Record reply dialog, and a stage's menu.
      await go(page, `applications/${pages[2][1]}`);
      await page
        .getByRole("button", { name: /^Record reply/ })
        .filter({ visible: true })
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("Escape");
      await page
        .getByRole("button", { name: "More actions" })
        .filter({ visible: true })
        .click();
      await expect(
        page
          .getByRole("menu", { name: "Application actions" })
          .filter({ visible: true }),
      ).toBeVisible();
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("Escape");
      // Selected rows with the bulk bar (a desktop pattern).
      if (!isPhone(page)) {
        await go(page, "applications?stage=applied");
        await settled(page);
        await page
          .locator(".ui-list [data-row-id]")
          .first()
          .click({ modifiers: ["ControlOrMeta"] });
        await expect(
          page.getByRole("toolbar", { name: "1 selected" }),
        ).toBeVisible();
        expect(await findings(page)).toEqual([]);
      }
    });

    test("the shell: the More menu, the account menu, the palette, Add job and the shortcuts have no serious accessibility finding", async ({
      page,
    }) => {
      await go(page, "templates");
      await settled(page);
      expect(await findings(page)).toEqual([]);
      const navigation = page
        .getByRole("navigation", { name: "Main" })
        .filter({ visible: true });
      if (isPhone(page)) {
        await navigation.getByRole("button", { name: "More" }).click();
        await expect(page.getByRole("menu", { name: "More" })).toBeVisible();
        expect(await findings(page)).toEqual([]);
      } else {
        await navigation
          .getByRole("button", { name: /Alex Morgan|You/ })
          .click();
        await expect(page.getByRole("menu", { name: "Account" })).toBeVisible();
        expect(await findings(page)).toEqual([]);
      }
      await page.keyboard.press("Escape");
      // The palette with results of both kinds.
      await page.keyboard.press("/");
      const palette = page.getByRole("dialog", { name: "Search and commands" });
      await palette.getByRole("combobox").fill("engineer");
      await expect(
        palette.getByRole("group", { name: "Jobs" }).getByRole("option"),
      ).not.toHaveCount(0);
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("Escape");
      await page.keyboard.press("n");
      const add = page.getByRole("dialog", { name: "Add a job" });
      await add.getByText("More details").click();
      await expect(add.getByLabel("Company")).toBeVisible();
      expect(await findings(page)).toEqual([]);
      await page.keyboard.press("Escape");
      await page.keyboard.press("?");
      await expect(
        page.getByRole("dialog", { name: "Keyboard shortcuts" }),
      ).toBeVisible();
      expect(await findings(page)).toEqual([]);
    });
  });
}
