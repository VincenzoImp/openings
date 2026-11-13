import { createHash } from "node:crypto";
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
      const setup = { "X-Openings-E2E-Setup": "1" };
      const session = await fetch("/api/v1/auth/session", {
        headers: setup,
      }).then((response) => response.json());
      const body = Uint8Array.from(atob(data), (char) => char.charCodeAt(0));
      const ticket = await fetch("/api/v1/files/uploads", {
        method: "POST",
        headers: {
          ...setup,
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
        headers: { ...setup, ...ticket.headers },
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
