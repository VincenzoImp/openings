import { expect, test } from "@playwright/test";

import { Api, uniqueUrl } from "./api";
import { isPhone, openJob, toast } from "./helpers";

test.describe("Job page", () => {
  test("shows the posting, its material and the timeline", async ({ page }) => {
    const api = await Api.plain();
    const job = await api.find("E2E Site Reliability Engineer");
    await api.dispose();
    expect(job).not.toBeNull();

    await openJob(page, job!.job_id);
    await expect(
      page.getByRole("heading", { name: "E2E Site Reliability Engineer" }),
    ).toBeVisible();
    await expect(page.getByText("Applied", { exact: true }).first()).toBeVisible();
    await expect(
      page.locator(".markdown").getByText("Keep the distributed systems up."),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Postings", exact: true })).toBeVisible();
    await expect(page.getByText("Embeddings are disabled")).toBeVisible();

    await page.getByRole("tab", { name: /Application/ }).click();
    await expect(page).toHaveURL(/tab=application/);
    await expect(page.getByRole("button", { name: "cv.txt", exact: true })).toBeVisible();
    await expect(page.getByText("Why do you want to join?")).toBeVisible();
    await expect(page.getByText("Applied through the careers page")).toBeVisible();

    await page.getByRole("tab", { name: /Activity/ }).click();
    await expect(page.getByText(/Ingested|Added by hand|added/i).first()).toBeVisible();
    await expect(page.getByText("Applied through the careers page")).toBeVisible();
  });

  test("adds a label, a note and edits the posting", async ({ page }) => {
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Editable Posting",
      company: "Xi",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "Before the edit.",
      status: "shortlisted",
    });
    try {
      await openJob(page, id);
      await page.getByLabel("Add label").fill("e2e-label");
      await page.getByLabel("Add label").press("Enter");
      await expect(page.getByText("e2e-label")).toBeVisible();

      await page.getByRole("tab", { name: /Application/ }).click();
      await page
        .getByRole("textbox", { name: "Note", exact: true })
        .fill("A note from the browser.");
      await page.getByRole("button", { name: "Add note" }).click();
      await expect(page.getByText("A note from the browser.")).toBeVisible();

      await page.getByRole("button", { name: "Actions" }).click();
      await page.getByRole("menuitem", { name: "Edit posting" }).click();
      const dialog = page.getByRole("dialog", { name: "Edit Posting" });
      await dialog.getByLabel("Location").fill("Basel, Switzerland");
      await dialog.getByLabel("Description (markdown)").fill("After the edit.");
      await dialog.getByRole("button", { name: "Save Changes" }).click();
      await toast(page, "Posting saved");
      await expect(page.getByText("Basel, Switzerland")).toBeVisible();
      await page.getByRole("tab", { name: "Posting" }).click();
      await expect(page.getByText("After the edit.")).toBeVisible();

      const stored = await api.job(id);
      expect(stored.labels).toContain("e2e-label");
      expect(stored.notes).toHaveLength(1);
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });

  test("uploads, previews, downloads and deletes an attachment", async ({ page }) => {
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Attachment Host",
      company: "Omicron",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "files",
      status: "applied",
    });
    try {
      await openJob(page, id, "application");
      await page.getByLabel("Kind").first().selectOption("cover_letter");
      await page.getByLabel("File note").fill("draft v1");
      await page.getByLabel("Choose files").setInputFiles({
        name: "letter.md",
        mimeType: "text/markdown",
        buffer: Buffer.from("# Dear team\n\nHere is my **letter**.\n", "utf-8"),
      });
      await toast(page, "Attached letter.md");
      const row = page.locator("li").filter({ hasText: "letter.md" }).first();
      await expect(row).toContainText("Cover Letter");
      await expect(row).toContainText("draft v1");

      await row.getByRole("button", { name: "Preview letter.md" }).click();
      const preview = page.getByRole("dialog", { name: "letter.md" });
      await expect(preview.getByRole("heading", { name: "Dear team" })).toBeVisible();
      await preview.getByRole("button", { name: "Close" }).click();

      const download = page.waitForEvent("download");
      await row.getByRole("button", { name: "Download letter.md" }).click();
      expect((await download).suggestedFilename()).toBe("letter.md");

      const bundle = page.waitForEvent("download");
      await page.getByRole("button", { name: "Download bundle" }).click();
      expect((await bundle).suggestedFilename()).toMatch(/\.zip$/);

      await row.getByRole("button", { name: "Delete letter.md" }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
      await expect(page.getByRole("button", { name: "letter.md", exact: true })).toHaveCount(0);
      expect((await api.job(id)).attachments).toHaveLength(0);
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });

  test("blacklists from the page and restores", async ({ page }) => {
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Page Blacklist",
      company: "Pi",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "bye",
      status: "new",
    });
    try {
      await openJob(page, id);
      await page.getByRole("button", { name: "Actions" }).click();
      await page.getByRole("menuitem", { name: "Blacklist…" }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Blacklist" }).click();
      await expect(page.getByText("Blacklisted.")).toBeVisible();
      expect((await api.job(id)).status).toBe("blacklisted");
      await page.getByRole("button", { name: "Restore" }).click();
      await expect(page.getByText("Blacklisted.")).toHaveCount(0);
      expect((await api.job(id)).status).toBe("new");
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });

  test("steps to the neighbour with ] after opening from the inbox", async ({ page }) => {
    test.skip(isPhone(page), "bracket keys are a keyboard workflow");
    await page.goto("/?view=inbox&sort=title&direction=asc");
    const rows = page.getByTestId("job-row");
    await expect(rows.first()).toBeVisible();
    const firstTitle = (await rows.nth(0).getByRole("button").first().textContent()) ?? "";
    const secondTitle = (await rows.nth(1).getByRole("button").first().textContent()) ?? "";
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: firstTitle })).toBeVisible();
    await expect(page.getByText(/1 of \d+/)).toBeVisible();
    await page.keyboard.press("]");
    await expect(page.getByRole("heading", { name: secondTitle })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  });
});
