import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export const VIEWS = ["inbox", "pipeline", "companies", "runs", "system"] as const;

export async function gotoView(
  page: Page,
  view: (typeof VIEWS)[number],
  params = "",
): Promise<void> {
  await page.goto(`/?view=${view}${params}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

export async function openJob(page: Page, jobId: string, tab?: string): Promise<void> {
  await page.goto(`/?view=inbox&job=${jobId}${tab ? `&tab=${tab}` : ""}`);
  await expect(page.getByRole("article")).toBeVisible();
}

/** The page must never scroll sideways, at any viewport. */
export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
}

export function isPhone(page: Page): boolean {
  const size = page.viewportSize();
  return size !== null && size.width < 768;
}

export async function toast(page: Page, text: string | RegExp): Promise<void> {
  await expect(page.getByRole("status").filter({ hasText: text }).first()).toBeVisible();
}
