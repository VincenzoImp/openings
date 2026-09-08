import { expect, test } from "@playwright/test";

import { Api, uniqueUrl } from "./api";
import { gotoView, isPhone } from "./helpers";

test.describe("Pipeline", () => {
  test("shows every status column with the seeded jobs", async ({ page }) => {
    await gotoView(page, "pipeline");
    await expect(page.getByTestId("column-shortlisted")).toContainText("E2E Platform Engineer");
    await expect(page.getByTestId("column-applied")).toContainText("E2E Site Reliability Engineer");
    await expect(page.getByTestId("column-interviewing")).toContainText("E2E Security Engineer");
    await expect(page.getByTestId("column-rejected")).toContainText("E2E Mobile Engineer");
    await expect(page.getByTestId("column-withdrawn")).toBeVisible();
  });

  test("moves a card from its menu", async ({ page }) => {
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Menu Card",
      company: "Rho",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "menu",
      status: "shortlisted",
    });
    try {
      await gotoView(page, "pipeline", "&q=Menu+Card");
      const card = page.getByTestId("pipeline-card").filter({ hasText: "E2E Menu Card" });
      await card.getByRole("button", { name: /Actions for/ }).click();
      await page.getByRole("menuitem", { name: "Move to Interviewing" }).click();
      await expect(page.getByTestId("column-interviewing")).toContainText("E2E Menu Card");
      await expect.poll(async () => (await api.job(id)).status).toBe("interviewing");
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });

  test("moves a card by dragging it to another column", async ({ page }) => {
    test.skip(isPhone(page), "drag and drop is a pointer workflow");
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Drag Card",
      company: "Sigma",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "drag",
      status: "shortlisted",
    });
    try {
      await gotoView(page, "pipeline", "&q=Drag+Card");
      const card = page.getByTestId("pipeline-card").filter({ hasText: "E2E Drag Card" });
      await card.dragTo(page.getByTestId("column-applied"));
      await expect(page.getByTestId("column-applied")).toContainText("E2E Drag Card");
      await expect.poll(async () => (await api.job(id)).status).toBe("applied");
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });

  test("moves the selected card with ] and [", async ({ page }) => {
    test.skip(isPhone(page), "keyboard workflow");
    const api = await Api.plain();
    const id = await api.addJob({
      title: "E2E Bracket Card",
      company: "Tau",
      location: "Remote",
      job_url: uniqueUrl(),
      description: "bracket",
      status: "shortlisted",
    });
    try {
      await gotoView(page, "pipeline", "&q=Bracket+Card");
      await expect(page.getByTestId("column-shortlisted")).toContainText("E2E Bracket Card");
      await page.keyboard.press("]");
      await expect(page.getByTestId("column-applied")).toContainText("E2E Bracket Card");
      await page.keyboard.press("[");
      await expect(page.getByTestId("column-shortlisted")).toContainText("E2E Bracket Card");
    } finally {
      await api.delete([id]);
      await api.dispose();
    }
  });
});
