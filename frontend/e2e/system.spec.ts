import { expect, test } from "@playwright/test";

import { gotoView } from "./helpers";

test.describe("System", () => {
  test("shows the overview, the distribution and the settings summary", async ({ page }) => {
    await gotoView(page, "system");
    await expect(page.getByText("Jobs", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Score distribution" })).toBeVisible();
    await expect(page.locator("li").filter({ hasText: / to / }).first()).toBeVisible();
    await expect(page.getByText("Time zone")).toBeVisible();
    await expect(page.getByText("UTC", { exact: true })).toBeVisible();
    await expect(page.getByText("E2E", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Reference" }).click();
    await expect(page.locator("pre")).toContainText("profile");
  });

  test("asks with counts before the configured cleanup and can be cancelled", async ({ page }) => {
    await gotoView(page, "system");
    await page.getByRole("button", { name: "Run configured cleanup…" }).click();
    const dialog = page.getByRole("dialog", { name: "Run the configured cleanup?" });
    await expect(dialog).toContainText(/\d+ new jobs below the save threshold/);
    await expect(dialog.getByRole("button", { name: /Delete \d+/ })).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toHaveCount(0);
  });

  test("keeps the chosen theme across reloads", async ({ page }) => {
    await gotoView(page, "system");
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByRole("radio", { name: "Light" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.getByRole("radio", { name: "System" }).check();
    const expected = await page.evaluate(() =>
      window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
    );
    await expect(page.locator("html")).toHaveAttribute("data-theme", expected);
  });

  test("exports the selected statuses as CSV", async ({ page }) => {
    await gotoView(page, "system");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download", exact: true }).click();
    expect((await download).suggestedFilename()).toMatch(/\.csv$/);
  });

  test("lists the blacklist with the seeded entry", async ({ page }) => {
    await gotoView(page, "system");
    await page.getByLabel("Search the blacklist").fill("Recruiter Spam");
    await expect(page.getByRole("row").filter({ hasText: "E2E Recruiter Spam" })).toHaveCount(1);
  });
});
