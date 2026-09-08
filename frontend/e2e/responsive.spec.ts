import { expect, test } from "@playwright/test";

import { Api } from "./api";
import { VIEWS, expectNoHorizontalOverflow, gotoView, isPhone, openJob } from "./helpers";

test.describe("Responsive layout", () => {
  for (const view of VIEWS) {
    test(`the ${view} view never scrolls sideways`, async ({ page }) => {
      await gotoView(page, view);
      await expectNoHorizontalOverflow(page);
      if (isPhone(page)) {
        await expect(page.locator("nav.fixed[aria-label='Views']")).toBeVisible();
        await expect(page.locator("aside")).toBeHidden();
      } else {
        await expect(page.locator("aside")).toBeVisible();
      }
    });
  }

  test("the job page and its dialogs fit the viewport", async ({ page }) => {
    const api = await Api.plain();
    const job = await api.find("E2E Site Reliability Engineer");
    await api.dispose();
    await openJob(page, job!.job_id, "application");
    await expectNoHorizontalOverflow(page);
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("menuitem", { name: "Edit posting" }).click();
    const dialog = page.getByRole("dialog", { name: "Edit Posting" });
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize()!;
    expect(box!.width).toBeLessThanOrEqual(viewport.width + 1);
    expect(box!.height).toBeLessThanOrEqual(viewport.height + 1);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });

  test("the bottom tabs switch views on phones", async ({ page }) => {
    test.skip(!isPhone(page), "phone only");
    await gotoView(page, "inbox");
    await page
      .locator("nav.fixed[aria-label='Views']")
      .getByRole("link", { name: /Pipeline/ })
      .click();
    await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
