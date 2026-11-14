import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "./fixtures";
import {
  call,
  go,
  isPhone,
  ownerSession,
  syntheticTex,
  upload,
  type Cookies,
} from "./session";

// Automated accessibility checks (axe) on every screen, in both themes; the
// Playwright projects supply the desktop and the narrow width. The budget: no
// serious or critical finding against WCAG 2.2 AA.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

const SCREENS = [
  "today",
  "applications",
  "applications?stage=applied",
  "applications?section=stats",
  "jobs",
  "jobs?section=shortlisted",
  "jobs?section=dismissed",
  "jobs?section=dismissed&dismissed_by=agent",
  "jobs?section=all",
  "jobs?signal=likely_duplicate",
  "profile",
  "preferences",
  "templates",
  "templates?section=rules",
  "templates?section=assets",
  "templates?section=preview",
  "sources",
  "sources?section=runs",
  "sources?section=runs&view=tasks",
  "sources?section=providers",
  "settings",
  "settings?section=skills",
  "settings?section=backup",
  "settings?section=workspace",
  "setup",
  "setup?step=record",
  "setup?step=next",
];

const cookies: Cookies = ownerSession();

async function findings(page: Page, key: string) {
  // A menu or dialog that is still fading in would be measured half blended.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter(
          (animation) => animation.effect?.getTiming().iterations !== Infinity,
        )
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );
  const { violations } = await new AxeBuilder({ page })
    .withTags(TAGS)
    .analyze();
  const found: string[] = [];
  for (const violation of violations) {
    if (violation.impact !== "serious" && violation.impact !== "critical")
      continue;
    for (const node of violation.nodes) {
      const target = node.target.join(" ");
      // On a phone a fixed action bar covers whatever reaches the edge of the
      // content, which axe reads as a small target.
      // Scroll the target to the middle and check its size and spacing again.
      const covered =
        violation.id === "target-size" &&
        (await visibleTargetFits(page, target));
      if (!covered)
        found.push(
          `${violation.id}: ${target}\n    ${node.failureSummary?.replaceAll("\n", "\n    ")}`,
        );
    }
  }
  return found;
}

/** The target passes the target-size rule once nothing fixed covers it. */
async function visibleTargetFits(page: Page, target: string) {
  const element = page.locator(target).first();
  const covered = await element
    .evaluate((el) => {
      const box = el.getBoundingClientRect();
      const fixed = ".ui-bottombar, .sticky-actions, .ui-topbar";
      const rects = (selector: string) =>
        [...document.querySelectorAll(selector)]
          .map((bar) => bar.getBoundingClientRect())
          .filter((rect) => rect.height > 0);
      const bottom = Math.min(
        window.innerHeight,
        ...rects(".ui-bottombar, .sticky-actions").map((rect) => rect.top),
      );
      // The phone's top bar sits above the content.
      const top = Math.max(
        0,
        ...rects(".ui-topbar").map((rect) => rect.bottom),
      );
      return (box.bottom > bottom || box.top < top) && !el.closest(fixed);
    })
    .catch(() => false);
  if (!covered) return false;
  await element.evaluate((el) => el.scrollIntoView({ block: "center" }));
  const { violations } = await new AxeBuilder({ page })
    .include(target)
    .withRules(["target-size"])
    .analyze();
  await page.evaluate(() => document.getElementById("content")?.scrollTo(0, 0));
  return violations.length === 0;
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

    test("the setup guide with its forms open has no serious accessibility finding", async ({
      page,
    }) => {
      await page.context().addCookies(cookies);
      await go(page, "setup?step=record");
      await settled(page);
      const record = page.getByRole("list", { name: "Your record" });
      for (const [button, key] of [
        [/the profile$/, "setup-profile"],
        [/the preferences$/, "setup-preferences"],
        [/^Add a search$/, "setup-search"],
      ] as const) {
        await record.getByRole("button", { name: button }).click();
        await expect(record.locator(".inline-form")).toBeVisible();
        await settled(page);
        expect(await findings(page, key)).toEqual([]);
        await record
          .getByRole("button", { name: /^Close/, expanded: true })
          .click();
      }
    });

    test("a job with its details, the dismissed job, the dialogs and the selection have no serious accessibility finding", async ({
      page,
    }) => {
      test.setTimeout(90000);
      await page.context().addCookies(cookies);
      await go(page, "today");
      const api = (path: string) =>
        page.evaluate(
          (path) => fetch("/api/v1" + path).then((response) => response.json()),
          path,
        );
      const flagged = (await api("/jobs?signal=likely_duplicate&limit=1"))
        .items[0];
      const dismissed = (await api("/jobs?triage=dismissed&limit=1")).items[0];
      // A likely duplicate with every detail section open.
      await go(page, `jobs?job=${flagged.id}`);
      await settled(page);
      await expect(page.locator(".job-detail .duplicate")).toBeVisible();
      for (const summary of await page
        .locator(".job-detail details > summary")
        .all())
        await summary.click();
      await settled(page);
      expect(await findings(page, "job")).toEqual([]);
      await go(page, `jobs?section=dismissed&job=${dismissed.id}`);
      await settled(page);
      expect(await findings(page, "dismissed-job")).toEqual([]);
      // Dismiss with a reason, merge, add a job.
      await go(page, `jobs?job=${flagged.id}`);
      await settled(page);
      await page
        .getByRole("group", { name: "Actions on this job" })
        .getByRole("button", { name: "Dismiss…" })
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page, "dismiss")).toEqual([]);
      await page.keyboard.press("Escape");
      await page
        .getByRole("button", { name: "Merge into one job", exact: true })
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page, "merge")).toEqual([]);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Add a job" }).click();
      await expect(
        page.locator("dialog[open] textarea[name=posting]"),
      ).toBeVisible();
      expect(await findings(page, "add-job")).toEqual([]);
      await page.keyboard.press("Escape");
      // Selected rows with the bulk actions.
      await go(page, "jobs");
      await settled(page);
      await page.locator(".job-list input[type=checkbox]").first().check();
      await expect(
        page.getByRole("group", { name: "Selected jobs" }),
      ).toBeVisible();
      expect(await findings(page, "jobs-bulk")).toEqual([]);
    });

    test("the review page, each of its tabs and the response form have no serious accessibility finding", async ({
      page,
    }) => {
      test.setTimeout(90000);
      await page.context().addCookies(cookies);
      await go(page, "today");
      const api = (path: string) =>
        page.evaluate(
          (path) => fetch("/api/v1" + path).then((response) => response.json()),
          path,
        );
      const ready = (
        await api("/applications?stage=ready&sort=deadline&limit=1")
      ).items[0];
      const sent = (await api("/applications?stage=interview&limit=1"))
        .items[0];
      for (const [id, tab] of [
        [ready.id, "answers"],
        [ready.id, "requirements"],
        [ready.id, "documents"],
        [ready.id, "details"],
        [sent.id, "timeline"],
      ]) {
        await go(page, `applications/${id}?tab=${tab}`);
        await settled(page);
        expect(await findings(page, `review-${tab}`)).toEqual([]);
      }
      // The pane switch on a phone, and the documents in a revision.
      await go(page, `applications/${ready.id}?tab=documents`);
      await settled(page);
      await page
        .getByRole("list", { name: "Document revisions" })
        .getByRole("button", { name: /^Open/ })
        .first()
        .click();
      await settled(page);
      expect(await findings(page, "review-revision")).toEqual([]);
      // A CV revision compared with the one it replaces.
      const job = await call(page, "/jobs", "POST", {
        title: `Compared CV ${test.info().project.name} ${Date.now()}`,
        company: "Example Labs",
        posting: "Build reliable services with a small team.",
      });
      const application = await call(page, "/applications", "POST", {
        job_id: job.id,
      });
      let previous = null;
      for (const wording of ["First wording.", "Second wording."]) {
        previous = await call(page, "/documents", "POST", {
          application_id: application.id,
          kind: "cv",
          title: "CV",
          previous_id: previous?.id ?? null,
        });
        // Sources only: Chromium's PDF viewer would keep the network busy.
        await upload(
          page,
          "document",
          previous.id,
          "cv.tex",
          syntheticTex(`${wording}\n\nA kept line.`),
          "application/x-tex",
        );
      }
      await go(page, `applications/${application.id}?tab=documents`);
      await settled(page);
      await page
        .getByRole("list", { name: "Document revisions" })
        .getByRole("button", { name: /^Open/ })
        .first()
        .click();
      await page
        .getByRole("button", { name: "Compare with revision 1" })
        .click();
      await expect(
        page.getByRole("list", { name: "Changes since revision 1" }),
      ).toBeVisible();
      expect(await findings(page, "review-comparison")).toEqual([]);
      // The form that records an employer reply, under its row.
      await go(page, "applications?stage=interview");
      await settled(page);
      await page
        .getByRole("button", { name: /^Record reply/ })
        .first()
        .click();
      await expect(page.locator("form.respond")).toBeVisible();
      expect(await findings(page, "respond")).toEqual([]);
      // Selected rows with the bulk actions.
      await page.locator(".grid-row input[type=checkbox]").nth(1).check();
      await expect(
        page.getByRole("group", { name: "Selected applications" }),
      ).toBeVisible();
      expect(await findings(page, "bulk")).toEqual([]);
    });

    test("the shell: the More menu, the account menu, the palette, Add job and the shortcuts have no serious accessibility finding", async ({
      page,
    }) => {
      await page.context().addCookies(cookies);
      await go(page, "templates");
      await settled(page);
      expect(await findings(page, "shell")).toEqual([]);
      const navigation = page
        .getByRole("navigation", { name: "Main" })
        .filter({ visible: true });
      if (isPhone(page)) {
        await navigation.getByRole("button", { name: "More" }).click();
        await expect(page.getByRole("menu", { name: "More" })).toBeVisible();
        expect(await findings(page, "more")).toEqual([]);
      } else {
        await navigation
          .getByRole("button", { name: /Alex Morgan|You/ })
          .click();
        await expect(page.getByRole("menu", { name: "Account" })).toBeVisible();
        expect(await findings(page, "account")).toEqual([]);
      }
      await page.keyboard.press("Escape");
      // The palette with results of both kinds.
      await page.keyboard.press("/");
      const palette = page.getByRole("dialog", { name: "Search and commands" });
      await palette.getByRole("combobox").fill("engineer");
      await expect(
        palette.getByRole("group", { name: "Jobs" }).getByRole("option"),
      ).not.toHaveCount(0);
      expect(await findings(page, "palette")).toEqual([]);
      await page.keyboard.press("Escape");
      await page.keyboard.press("n");
      const add = page.getByRole("dialog", { name: "Add a job" });
      await add.getByText("More details").click();
      await expect(add.getByLabel("Company")).toBeVisible();
      expect(await findings(page, "add-job-details")).toEqual([]);
      await page.keyboard.press("Escape");
      await page.keyboard.press("?");
      await expect(
        page.getByRole("dialog", { name: "Keyboard shortcuts" }),
      ).toBeVisible();
      expect(await findings(page, "shortcuts")).toEqual([]);
    });
  });
}
