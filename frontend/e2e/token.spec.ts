import { expect, test } from "@playwright/test";

import { API_TOKEN } from "../playwright.config";

test.describe("Token gate", () => {
  test("asks for the token, rejects a wrong one and loads with the right one", async ({ page }) => {
    await page.goto("/?view=inbox");
    const dialog = page.getByRole("dialog", { name: "API token required" });
    await expect(dialog).toBeVisible();

    await dialog.getByLabel("Token").fill("wrong");
    await dialog.getByRole("button", { name: "Save token" }).click();
    await expect(page.getByRole("dialog", { name: "API token required" })).toBeVisible();

    await page.getByRole("dialog").getByLabel("Token").fill(API_TOKEN);
    await page.getByRole("dialog").getByRole("button", { name: "Save token" }).click();
    await expect(page.getByRole("dialog", { name: "API token required" })).toHaveCount(0);
    await expect(
      page.getByTestId("job-row").filter({ hasText: "E2E Token Gated Posting" }),
    ).toHaveCount(1);

    await page.reload();
    await expect(
      page.getByTestId("job-row").filter({ hasText: "E2E Token Gated Posting" }),
    ).toHaveCount(1);
  });

  test("the MCP endpoint refuses requests without the token", async ({ request }) => {
    const response = await request.post("/mcp", {
      data: { jsonrpc: "2.0", id: 1, method: "tools/list" },
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      },
    });
    expect(response.status()).toBe(401);
  });

  test("the token can be cleared from System", async ({ page }) => {
    await page.goto("/?view=system");
    await page.getByRole("dialog").getByLabel("Token").fill(API_TOKEN);
    await page.getByRole("dialog").getByRole("button", { name: "Save token" }).click();
    await expect(page.getByText("One is stored in this browser.")).toBeVisible();
    await page.getByRole("button", { name: "Clear", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "API token required" })).toBeVisible();
  });
});
