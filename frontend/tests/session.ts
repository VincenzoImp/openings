import {
  expect,
  type Browser,
  type BrowserContext,
  type Page,
  type TestInfo,
} from "@playwright/test";

export type Cookies = Parameters<BrowserContext["addCookies"]>[0];

/** Sign in once as the owner of the synthetic workspace; reuse the cookies. */
export async function ownerSession(
  browser: Browser,
  info: TestInfo,
): Promise<Cookies> {
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL,
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.locator("input[name=password]").fill("synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".main h1")).toBeVisible();
  const cookies = await context.cookies();
  await context.close();
  return cookies;
}

/** Open a hash route and wait for its screen. */
export async function go(page: Page, hash: string) {
  await page.goto("/#" + hash);
  await expect(page.locator(".main h1")).toBeVisible();
}

/** The narrow layout: bottom bar instead of the sidebar. */
export const isNarrow = (page: Page) =>
  (page.viewportSize()?.width ?? 1440) <= 860;
