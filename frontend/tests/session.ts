import { createHash } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

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

/**
 * The key that moves focus to the next control, links included: WebKit on
 * macOS, as Safari, skips links on a plain Tab.
 */
export const tabKey = (page: Page) =>
  page.context().browser()?.browserType().name() === "webkit" &&
  process.platform === "darwin"
    ? "Alt+Tab"
    : "Tab";

/** The screen's requests are answered and its skeleton rows are gone. */
export async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".ui-skeleton-rows")).toHaveCount(0);
}

/** Open a hash route and wait for its screen. */
export async function go(page: Page, hash: string) {
  await page.goto("/#" + hash);
  // The screen's own h1 is drawn once its code and first data are in; on a
  // phone the top bar shows the title instead, so it is only attached.
  await expect(
    page.locator("#content [data-screen] h1").first(),
  ).toBeAttached();
  await expect(heading(page)).toBeVisible();
}

/**
 * The screen's title: the page's own h1 on wide screens, the phone's top
 * bar on narrow ones (each hides the other).
 */
export const heading = (page: Page) => page.locator("h1:visible");

/** The shell's phone layout: the top and bottom bars, no sidebar. */
export const isPhone = (page: Page) =>
  (page.viewportSize()?.width ?? 1440) < 720;

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
      const session = await fetch("/api/v1/auth/session").then((response) =>
        response.json(),
      );
      const response = await fetch("/api/v1" + path, {
        method,
        credentials: token ? "omit" : "same-origin",
        headers: {
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

/** A one-page PDF with one line of text. */
export function syntheticPdf(text = "Synthetic application CV") {
  const stream = `BT /F1 18 Tf 40 440 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 500] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let data = "%PDF-1.4\n";
  const offsets = [0];
  for (const [index, object] of objects.entries()) {
    offsets.push(Buffer.byteLength(data));
    data += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xref = Buffer.byteLength(data);
  data +=
    "xref\n0 6\n0000000000 65535 f \n" +
    offsets
      .slice(1)
      .map((offset) => String(offset).padStart(10, "0") + " 00000 n \n")
      .join("") +
    `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(data);
}

/** Attach a file to a record as the test's own setup, not as a dashboard path. */
export async function upload(
  page: Page,
  ownerType: string,
  ownerId: string,
  name: string,
  bytes: Buffer,
  mediaType = "application/pdf",
  sourceSha256?: string,
) {
  return page.evaluate(
    async ({ ownerType, ownerId, name, data, mediaType, sourceSha256 }) => {
      const session = await fetch("/api/v1/auth/session").then((response) =>
        response.json(),
      );
      const body = Uint8Array.from(atob(data), (char) => char.charCodeAt(0));
      const ticket = await fetch("/api/v1/files/uploads", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": session.csrf_token,
        },
        body: JSON.stringify({
          owner_type: ownerType,
          owner_id: ownerId,
          name,
          size: body.length,
          media_type: mediaType,
          ...(sourceSha256 ? { source_sha256: sourceSha256 } : {}),
        }),
      }).then(async (response) => {
        if (!response.ok) throw Error(await response.text());
        return response.json();
      });
      const response = await fetch(ticket.url, {
        method: ticket.method || "PUT",
        headers: ticket.headers,
        body,
      });
      // Read the answer: an unread body keeps the request open for the page.
      const answer = await response.text();
      if (!response.ok) throw Error(answer);
    },
    {
      ownerType,
      ownerId,
      name,
      data: bytes.toString("base64"),
      mediaType,
      sourceSha256,
    },
  );
}

/** A small LaTeX source whose text, as the server reads it, is `text`. */
export function syntheticTex(text = "Synthetic application CV") {
  return Buffer.from(
    `\\documentclass{article}\n\\begin{document}\n${text}\n\\end{document}\n`,
  );
}

/**
 * Give a CV or letter revision its source and the PDF built from it, as the
 * test's own setup: the PDF names the source's SHA-256.
 */
export async function attachSource(
  page: Page,
  documentId: string,
  text = "Synthetic application CV",
  name = "document",
) {
  const source = syntheticTex(text);
  await upload(
    page,
    "document",
    documentId,
    `${name}.tex`,
    source,
    "application/x-tex",
  );
  await upload(
    page,
    "document",
    documentId,
    `${name}.pdf`,
    syntheticPdf(text.replace(/\s+/g, " ")),
    "application/pdf",
    createHash("sha256").update(source).digest("hex"),
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

/**
 * A block's Edit or … button. At rest a phone shows the CV as text: a tap
 * on the block shows its actions first.
 */
export async function blockButton(page: Page, name: string) {
  const button = page.getByRole("button", {
    name,
    exact: true,
    includeHidden: true,
  });
  if (isPhone(page)) {
    await button
      .locator(
        "xpath=ancestor::div[contains(concat(' ', @class, ' '), ' pf-block ')][1]",
      )
      .click({ position: { x: 4, y: 4 } });
    await expect(button).toBeVisible();
  }
  await button.click();
}

/**
 * The themes an accessibility check covers: both on `chromium`, light only on
 * the other projects. Token contrast in both themes is proven by
 * contrast.test.mjs, so the dark pass is not repeated per browser and width.
 */
export const themes = (): ("light" | "dark")[] =>
  test.info().project.name === "chromium" ? ["light", "dark"] : ["light"];

/** Apply a theme from the next load on, as the dashboard stores it. */
export async function useTheme(page: Page, theme: string) {
  await page.addInitScript((value) => {
    try {
      localStorage.setItem("openings-theme", value);
    } catch {}
  }, theme);
}

export const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/**
 * The serious and critical axe findings against WCAG 2.2 AA of the page as
 * it is, once its animations end; `[]` when there is none.
 */
export async function findings(page: Page) {
  // A menu or dialog that is still fading in would be measured half blended.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter(
          (animation) => animation.effect?.getTiming().iterations !== Infinity,
        )
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );
  const { violations } = await new AxeBuilder({ page })
    .withTags(WCAG)
    .analyze();
  const found: string[] = [];
  for (const violation of violations) {
    if (violation.impact !== "serious" && violation.impact !== "critical")
      continue;
    for (const node of violation.nodes) {
      const target = node.target.join(" ");
      // On a phone a fixed action bar covers whatever reaches the edge of the
      // content, which axe reads as a small target.
      // Scroll the target to the middle and check its size and spacing again.
      const covered =
        violation.id === "target-size" &&
        (await visibleTargetFits(page, target));
      if (!covered)
        found.push(
          `${violation.id}: ${target}\n    ${node.failureSummary?.replaceAll("\n", "\n    ")}`,
        );
    }
  }
  return found;
}

/** The target passes the target-size rule once nothing fixed covers it. */
async function visibleTargetFits(page: Page, target: string) {
  const element = page.locator(target).first();
  const covered = await element
    .evaluate((el) => {
      const box = el.getBoundingClientRect();
      const fixed = ".ui-bottombar, .sticky-actions, .ui-topbar";
      const rects = (selector: string) =>
        [...document.querySelectorAll(selector)]
          .map((bar) => bar.getBoundingClientRect())
          .filter((rect) => rect.height > 0);
      const bottom = Math.min(
        window.innerHeight,
        ...rects(".ui-bottombar, .sticky-actions").map((rect) => rect.top),
      );
      // The phone's top bar sits above the content.
      const top = Math.max(
        0,
        ...rects(".ui-topbar").map((rect) => rect.bottom),
      );
      return (box.bottom > bottom || box.top < top) && !el.closest(fixed);
    })
    .catch(() => false);
  if (!covered) return false;
  await element.evaluate((el) => el.scrollIntoView({ block: "center" }));
  const { violations } = await new AxeBuilder({ page })
    .include(target)
    .withRules(["target-size"])
    .analyze();
  await page.evaluate(() => document.getElementById("content")?.scrollTo(0, 0));
  return violations.length === 0;
}
