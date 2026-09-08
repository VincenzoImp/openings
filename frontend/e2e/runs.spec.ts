import { expect, test } from "@playwright/test";

import { gotoView, toast } from "./helpers";

test("requests a run and reports it as pending", async ({ page }) => {
  await gotoView(page, "runs");
  await expect(page.getByText("No runs yet")).toBeVisible();
  await page.getByRole("button", { name: /Run now/ }).click();
  await toast(page, "Run requested");
  await expect(page.locator("p", { hasText: "Run requested; the scheduler starts" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Run now/ })).toBeDisabled();
});

test("lists the configured sources on the Companies view", async ({ page }) => {
  await gotoView(page, "companies");
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
  await expect(page.getByText("Pick a company", { exact: true })).toBeVisible();
  await page.getByLabel("Filter companies").fill("Acme");
  const size = page.viewportSize();
  if (size && size.width >= 1024) {
    await page.getByRole("button", { name: /^Acme/ }).click();
  } else {
    await page.getByLabel("Company", { exact: true }).selectOption("Acme");
  }
  await expect(page).toHaveURL(/company=Acme/);
  await expect(page.getByTestId("job-row").filter({ hasText: "E2E Backend Engineer" })).toHaveCount(
    1,
  );
  await expect(
    page.getByTestId("job-row").filter({ hasText: "E2E Platform Engineer" }),
  ).toHaveCount(1);
  await expect(page.getByText(/Shortlisted \d+/)).toBeVisible();
});
