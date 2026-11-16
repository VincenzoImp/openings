import { test, expect, type Page } from "./fixtures";
import { startServer, type Server } from "./server";

// A dashboard opened from a server or NAS by its own name, while agents and
// upload links use the public URL (127.0.0.1 by default): the owner sees which
// variable to set. Chromium resolves the synthetic name to this machine.
const NAS = "nas.example";
test.use({
  signedIn: false,
  launchOptions: { args: [`--host-resolver-rules=MAP ${NAS} 127.0.0.1`] },
});

let server: Server;
test.beforeAll(async () => {
  test.setTimeout(120_000);
  server = await startServer({
    empty: true,
    env: { OPENINGS_PUBLIC_URL: "http://127.0.0.1:8080" },
    timeout: 110_000,
  });
});
test.afterAll(async () => server?.stop());

async function signIn(page: Page, base: string) {
  await page.goto(base + "/");
  await page.locator("input[name=password]").fill("synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("h1:visible").first()).toBeVisible();
}

test("another address names OPENINGS_PUBLIC_URL; the server's own does not", async ({
  page,
}) => {
  const port = new URL(server.url).port;
  const nas = `http://${NAS}:${port}`;
  await signIn(page, nas);
  const notice = page.locator(".shell-address");
  await expect(notice).toContainText(
    "Agents and upload links use http://127.0.0.1:8080.",
  );
  await expect(notice).toContainText(`OPENINGS_PUBLIC_URL=${nas}`);

  await signIn(page, server.url);
  await expect(page.locator("h1:visible").first()).toBeVisible();
  await expect(page.locator(".shell-address")).toHaveCount(0);
});
