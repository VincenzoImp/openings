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

/**
 * A REST call of the test itself, as the owner or with an API token. The
 * header marks it as setup, so it is not evidence of a dashboard path.
 */
export async function call(
  page: Page,
  path: string,
  method = "GET",
  body?: unknown,
  token?: string,
) {
  return page.evaluate(
    async ({ path, method, body, token }) => {
      const setup = { "X-Openings-E2E-Setup": "1" };
      const session = await fetch("/api/v1/auth/session", {
        headers: setup,
      }).then((response) => response.json());
      const response = await fetch("/api/v1" + path, {
        method,
        credentials: token ? "omit" : "same-origin",
        headers: {
          ...setup,
          "Content-Type": "application/json",
          ...(token
            ? { Authorization: "Bearer " + token }
            : { "X-CSRF-Token": session.csrf_token }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const value = await response.json();
      if (!response.ok) throw Error(JSON.stringify(value));
      return value;
    },
    { path, method, body, token },
  );
}

/** A card of a screen, by its heading. */
export const card = (page: Page, title: string) =>
  page.locator("section.card").filter({
    has: page.getByRole("heading", { name: title, exact: true }),
  });

/** The page never scrolls sideways. */
export async function fitsViewport(page: Page) {
  const width = page.viewportSize()!.width;
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(width);
}
