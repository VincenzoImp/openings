import { expect, type BrowserContext, type Page } from "@playwright/test";

export type Cookies = Parameters<BrowserContext["addCookies"]>[0];

/** The owner session the global setup opened, as cookies for a context. */
export function ownerSession(): Cookies {
  const [name, ...value] = (process.env.OPENINGS_E2E_SESSION || "").split("=");
  if (!name || !value.length) throw Error("The global setup did not sign in.");
  return [
    {
      name,
      value: value.join("="),
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      sameSite: "Strict",
    },
  ];
}

/** Open a hash route and wait for its screen. */
export async function go(page: Page, hash: string) {
  await page.goto("/#" + hash);
  await expect(page.locator(".main h1")).toBeVisible();
}

/** The narrow layout: bottom bar instead of the sidebar. */
export const isNarrow = (page: Page) =>
  (page.viewportSize()?.width ?? 1440) <= 860;
