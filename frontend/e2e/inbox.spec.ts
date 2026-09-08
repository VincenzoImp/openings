import { expect, test } from "@playwright/test";

import { Api, uniqueUrl } from "./api";
import { gotoView, isPhone, toast } from "./helpers";

test.describe("Inbox", () => {
  test("lists the new postings and opens one", async ({ page }) => {
    await gotoView(page, "inbox");
    const rows = page.getByTestId("job-row");
    await expect(rows.first()).toBeVisible();
    await expect(page.getByText(/^\d+ new$/)).toBeVisible();
    await expect(rows.filter({ hasText: "E2E Backend Engineer" })).toHaveCount(1);
    await expect(rows.filter({ hasText: "E2E Recruiter Spam" })).toHaveCount(0);

    await page.getByRole("button", { name: "E2E Backend Engineer", exact: true }).click();
    await expect(page.getByRole("heading", { name: "E2E Backend Engineer" })).toBeVisible();
    await expect(page.locator(".markdown").getByText("PostgreSQL")).toBeVisible();
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  });

  test("reads filters from the URL and clears them from the drawer", async ({ page }) => {
    await gotoView(page, "inbox", "&company=Acme");
    const rows = page.getByTestId("job-row");
    await expect(rows.first()).toBeVisible();
    for (const row of await rows.all()) {
      await expect(row).toContainText("Acme");
    }
    const filters = page.getByRole("button", { name: /Filters/ });
    await expect(filters).toContainText("1");
    await filters.click();
    const drawer = page.getByRole("dialog", { name: "Filters" });
    await expect(drawer.getByLabel("Company")).toHaveValue("Acme");
    await drawer.getByRole("button", { name: "Clear All" }).click();
    await drawer.getByRole("button", { name: "Done" }).click();
    await expect(page).not.toHaveURL(/company=/);
    await expect(rows.filter({ hasText: "Beta" }).first()).toBeVisible();
  });

  test("shortlists from the keyboard", async ({ page }) => {
    test.skip(isPhone(page), "keyboard triage is a desktop workflow");
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Keyboard Target",
      company: "Lambda",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "Backend engineer, Python.",
      status: "new",
    });
    try {
      await gotoView(page, "inbox", "&q=Keyboard+Target");
      const row = page.getByTestId("job-row").filter({ hasText: "E2E Keyboard Target" });
      await expect(row).toHaveAttribute("aria-current", "true");
      await page.keyboard.press("s");
      await toast(page, "1 moved to Shortlisted");
      await expect(page.getByText("No postings match")).toBeVisible();
      expect((await api.job(id)).status).toBe("shortlisted");
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });

  test("blacklists a selection and restores it from System", async ({ page }) => {
    const api = await Api.plain();
    const ids = [
      await api.addJob({
        title: "E2E Bulk Alpha",
        company: "Mu",
        location: "Remote",
        job_url: uniqueUrl(),
        description: "x",
        status: "new",
      }),
      await api.addJob({
        title: "E2E Bulk Beta",
        company: "Mu",
        location: "Remote",
        job_url: uniqueUrl(),
        description: "y",
        status: "new",
      }),
    ];
    try {
      await gotoView(page, "inbox", "&q=E2E+Bulk");
      await expect(page.getByTestId("job-row")).toHaveCount(2);
      await page.getByLabel("Select E2E Bulk Alpha").check();
      await page.getByLabel("Select E2E Bulk Beta").check();
      const toolbar = page.getByRole("toolbar", { name: "Bulk actions" });
      await expect(toolbar).toContainText("2 selected");
      await toolbar.getByRole("button", { name: "Blacklist" }).click();
      const dialog = page.getByRole("dialog", { name: "Blacklist 2 postings?" });
      await dialog.getByRole("button", { name: "Blacklist" }).click();
      await toast(page, "2 blacklisted");
      await expect(page.getByTestId("job-row")).toHaveCount(0);
      expect((await api.job(ids[0])).status).toBe("blacklisted");

      await gotoView(page, "system");
      await page.getByLabel("Search the blacklist").fill("E2E Bulk");
      const table = page.locator("table").filter({ hasText: "E2E Bulk Alpha" });
      await expect(table.getByRole("row").filter({ hasText: "E2E Bulk" })).toHaveCount(2);
      await table
        .getByRole("row")
        .filter({ hasText: "E2E Bulk Alpha" })
        .getByRole("button", { name: "Restore" })
        .click();
      await toast(page, "1 restored");
      await expect(table.getByRole("row").filter({ hasText: "E2E Bulk Alpha" })).toHaveCount(0);
      expect((await api.job(ids[0])).status).toBe("new");
    } finally {
      await api.delete(ids);
      await api.dispose();
    }
  });

  test("explains when semantic search is unavailable", async ({ page }) => {
    await gotoView(page, "inbox");
    await page.getByRole("textbox", { name: "Search" }).fill("~python services");
    await expect(page.getByRole("alert")).toContainText("Semantic search is not available");
  });

  test("changes status with a note from the bulk bar", async ({ page }) => {
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Status Note Target",
      company: "Nu",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "z",
      status: "new",
    });
    try {
      await gotoView(page, "inbox", "&q=Status+Note+Target");
      await page.getByLabel("Select E2E Status Note Target").check();
      await page.getByRole("toolbar").getByRole("button", { name: "Status…" }).click();
      const dialog = page.getByRole("dialog", { name: "Update status" });
      await dialog.getByLabel("Status").selectOption("applied");
      await dialog.getByLabel("Note for the timeline").fill("Sent through the portal.");
      await dialog.getByRole("button", { name: "Save", exact: true }).click();
      await toast(page, "1 moved to Applied");
      const job = await api.job(id);
      expect(job.status).toBe("applied");
      expect(JSON.stringify(job.events)).toContain("Sent through the portal.");
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });
});
