import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { Api } from "./api";
import { VIEWS, gotoView, openJob } from "./helpers";

async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(
    blocking.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.slice(0, 3).map((node) => node.html),
    })),
  ).toEqual([]);
}

test.describe("Accessibility", () => {
  for (const view of VIEWS) {
    test(`the ${view} view has no serious axe violations`, async ({ page }) => {
      await gotoView(page, view);
      await page.waitForLoadState("networkidle");
      await expectAccessible(page);
    });
  }

  test("the job page has no serious axe violations", async ({ page }) => {
    const api = await Api.plain();
    const job = await api.find("E2E Site Reliability Engineer");
    await api.dispose();
    await openJob(page, job!.job_id, "application");
    await page.waitForLoadState("networkidle");
    await expectAccessible(page);
  });

  test("dialogs have no serious axe violations", async ({ page }) => {
    await gotoView(page, "inbox");
    await page.keyboard.press("?");
    await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
    await expectAccessible(page);
  });
});
