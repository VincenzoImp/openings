import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "./fixtures";
import {
  call,
  go,
  isNarrow,
  ownerSession,
  syntheticTex,
  upload,
  type Cookies,
} from "./session";

// Automated accessibility checks (axe) on every screen, in both themes; the
// Playwright projects supply the desktop and the narrow width. The budget in
// docs/developer/dashboard-design.md: no serious or critical finding against
// WCAG 2.2 AA.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

const SCREENS = [
  "today",
  "applications",
  "applications?view=board",
  "applications?stage=applied",
  "applications?section=insights",
  "jobs",
  "jobs?section=shortlist",
  "jobs?section=dismissed",
  "jobs?section=all",
  "jobs?signal=likely_duplicate",
  "activity",
  "activity?section=requests",
  "activity?section=runs",
  "activity?section=timeline",
  "career",
  "career?section=knowledge",
  "career?section=claims",
  "policy",
  "templates",
  "templates?section=rules",
  "templates?section=assets",
  "templates?section=preview",
  "collection",
  "collection?section=yield",
  "collection?section=runs",
  "collection?section=runs&view=tasks",
  "collection?section=providers",
  "settings",
  "settings?section=skills",
  "settings?section=skills&skill=prepare-shortlist",
  "settings?section=backup",
  "settings?section=workspace",
  "setup",
  "setup?step=record",
  "setup?step=next",
];

const cookies: Cookies = ownerSession();

async function findings(page: Page, key: string) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(TAGS)
    .analyze();
  const found: string[] = [];
  for (const violation of violations) {
    if (violation.impact !== "serious" && violation.impact !== "critical")
      continue;
    for (const node of violation.nodes) {
      const target = node.target.join(" ");
      // On a phone the fixed bottom bar, and the sticky top bar, cover whatever
      // reaches the edge of the viewport, which axe reads as a small target.
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
      const fixed = ".tabbar, .sticky-actions, .topbar";
      const rects = (selector: string) =>
        [...document.querySelectorAll(selector)]
          .map((bar) => bar.getBoundingClientRect())
          .filter((rect) => rect.height > 0);
      const bottom = Math.min(
        window.innerHeight,
        ...rects(".tabbar, .sticky-actions").map((rect) => rect.top),
      );
      // The sticky top bar covers whatever scrolled under it.
      const top = Math.max(0, ...rects(".topbar").map((rect) => rect.bottom));
      return (box.bottom > bottom || box.top < top) && !el.closest(fixed);
    })
    .catch(() => false);
  if (!covered) return false;
  await element.evaluate((el) => el.scrollIntoView({ block: "center" }));
  const { violations } = await new AxeBuilder({ page })
    .include(target)
    .withRules(["target-size"])
    .analyze();
  await page.evaluate(() => window.scrollTo(0, 0));
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

// An agent run stays open for the rest of the suite, so every screen below is
// checked with the agent's status line in the navigation.
test("an agent opens a run and the navigation shows its status line", async ({
  page,
}, info) => {
  await page.context().addCookies(cookies);
  await go(page, "today");
  const workflow = `accessibility ${info.project.name} ${Date.now()}`;
  await page.evaluate(async (workflow) => {
    const setup = { "X-Openings-E2E-Setup": "1" };
    const json = { ...setup, "Content-Type": "application/json" };
    const session = await fetch("/api/v1/auth/session", {
      headers: setup,
    }).then((response) => response.json());
    const agent = await fetch("/api/v1/tokens", {
      method: "POST",
      headers: { ...json, "X-CSRF-Token": session.csrf_token },
      body: JSON.stringify({ name: `Agent ${workflow}`, kind: "agent" }),
    }).then((response) => response.json());
    const run = await fetch("/api/v1/runs", {
      method: "POST",
      credentials: "omit",
      headers: { ...json, Authorization: "Bearer " + agent.token },
      body: JSON.stringify({ workflow, scope: "Synthetic open run." }),
    });
    if (!run.ok) throw Error(await run.text());
  }, workflow);
  await page.reload();
  if (isNarrow(page))
    await page.getByRole("button", { name: "More", exact: true }).click();
  const status = page.locator(".sidebar-foot");
  await expect(status).toContainText("Run in progress:");
  await expect(status.locator(".actor")).toHaveClass(/agent/);
  await expect(status.locator(".actor")).toContainText("Agent accessibility");
  expect(await findings(page, "status")).toEqual([]);
});

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
        [/the policy$/, "setup-policy"],
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
          (path) =>
            fetch("/api/v1" + path, {
              headers: { "X-Openings-E2E-Setup": "1" },
            }).then((response) => response.json()),
          path,
        );
      const flagged = (await api("/jobs?signal=likely_duplicate&limit=1"))
        .items[0];
      const ruled = (
        await api("/jobs?queue=dismissed&dismissed_by=rule&limit=1")
      ).items[0];
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
      await go(page, `jobs?section=dismissed&job=${ruled.id}`);
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
        .getByRole("button", { name: "Same vacancy: merge", exact: true })
        .click();
      await expect(page.locator("dialog[open]")).toBeVisible();
      expect(await findings(page, "merge")).toEqual([]);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Add a job" }).click();
      await expect(page.locator("dialog[open] input[name=url]")).toBeVisible();
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
          (path) =>
            fetch("/api/v1" + path, {
              headers: { "X-Openings-E2E-Setup": "1" },
            }).then((response) => response.json()),
          path,
        );
      const ready = (
        await api("/applications?status=draft&ready=true&sort=deadline&limit=1")
      ).items[0];
      const sent = (await api("/applications?status=interview&limit=1"))
        .items[0];
      for (const [id, tab] of [
        [ready.id, "answers"],
        [ready.id, "requirements"],
        [ready.id, "inputs"],
        [ready.id, "documents"],
        [ready.id, "details"],
        [sent.id, "timeline"],
      ]) {
        await go(page, `review?application=${id}&tab=${tab}`);
        await settled(page);
        expect(await findings(page, `review-${tab}`)).toEqual([]);
      }
      // The pane switch on a phone, and the documents in a revision.
      await go(page, `review?application=${ready.id}&tab=documents`);
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
          kind: "resume",
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
      await go(page, `review?application=${application.id}&tab=documents`);
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
      // The form that records an employer response, under its row.
      await go(page, "applications?stage=interview");
      await settled(page);
      await page
        .getByRole("button", { name: /^Record response/ })
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
