import { expect, test } from "@playwright/test";

import { Api, uniqueUrl } from "./api";
import { gotoView, toast } from "./helpers";

test("adds a posting by hand, then updates it through the same URL", async ({ page }) => {
  const url = uniqueUrl();
  const api = await Api.plain();
  try {
    await gotoView(page, "inbox");
    await page.keyboard.press("n");
    const dialog = page.getByRole("dialog", { name: "Add a Posting" });
    await dialog.getByLabel("Title").fill("E2E Manual Posting");
    await dialog.getByLabel("Company").fill("Upsilon");
    await dialog.getByLabel("Location").fill("Remote");
    await dialog.getByLabel("Posting URL").fill(url);
    await dialog.getByLabel("Labels").fill("manual, e2e");
    await dialog.getByRole("button", { name: "Add Posting" }).click();
    await toast(page, "Posting added");
    await expect(page.getByRole("heading", { name: "E2E Manual Posting" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove label manual" })).toBeVisible();
    await expect(page).toHaveURL(/job=/);

    await page.keyboard.press("n");
    const again = page.getByRole("dialog", { name: "Add a Posting" });
    await again.getByLabel("Title").fill("E2E Manual Posting (renamed)");
    await again.getByLabel("Company").fill("Upsilon");
    await again.getByLabel("Posting URL").fill(url);
    await again.getByRole("button", { name: "Add Posting" }).click();
    await toast(page, "Posting updated");
    await expect(page.getByRole("heading", { name: "E2E Manual Posting (renamed)" })).toBeVisible();

    const job = await api.find("E2E Manual Posting (renamed)");
    expect(job?.labels).toEqual(expect.arrayContaining(["manual", "e2e"]));
    await api.delete(job ? [job.job_id] : []);
  } finally {
    await api.dispose();
  }
});
