// Capture docs/images from a running synthetic workspace.
// Usage: node scripts/docs_screenshots.mjs BASE_URL PASSWORD OUTPUT_DIR
// Normally started by scripts/docs_screenshots.py, which seeds the workspace.
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { chromium } = require("@playwright/test");

const [base, password, out] = process.argv.slice(2);
if (!base || !password || !out) {
  console.error(
    "Usage: node scripts/docs_screenshots.mjs BASE_URL PASSWORD OUTPUT_DIR",
  );
  process.exit(2);
}

const browser = await chromium.launch();
const context = await browser.newContext({
  baseURL: base,
  viewport: { width: 1440, height: 1000 },
  colorScheme: "light",
  locale: "en-US",
  timezoneId: "Europe/Zurich",
});
await context.addInitScript(() => {
  try {
    localStorage.setItem("openings-theme", "light");
  } catch {}
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));

await page.goto("/");
await page.locator("input[name=password]").fill(password);
await page.getByRole("button", { name: "Sign in", exact: true }).click();
await page.locator(".main h1").waitFor();

const dialog = () => page.locator("dialog[open]").last();

async function open(hash) {
  await page.goto("/#" + hash);
  await page.reload();
  await page.locator(".main h1").waitFor();
  await settle();
}
async function settle() {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
}
async function shot(name) {
  await settle();
  await page.evaluate(() => document.activeElement?.blur());
  // Show the default address instead of the temporary port.
  await page.evaluate((origin) => {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    while (walker.nextNode())
      walker.currentNode.nodeValue = walker.currentNode.nodeValue.replaceAll(
        origin,
        "http://127.0.0.1:8080",
      );
  }, new URL(base).origin);
  await page.screenshot({ path: path.join(out, name + ".png") });
  console.log("captured", name);
}
async function applicationId(company) {
  return page.evaluate(async (company) => {
    const response = await fetch("/api/v1/applications?status=draft&limit=50");
    const { items } = await response.json();
    return items.find((item) => item.job?.company === company).id;
  }, company);
}

await open("overview");
await shot("overview");

await open("inbox");
await shot("inbox");

await open("shortlist");
await shot("shortlist");

await open("inbox?queue=duplicates");
if (!(await page.getByRole("heading", { name: "Possible duplicates" }).count()))
  await page.getByRole("tab", { name: "Possible duplicates" }).click();
await page.getByLabel("Confidence").selectOption("0.85");
await shot("duplicates");

await open("applications");
await page.getByRole("button", { name: "Board", exact: true }).click();
await page.getByLabel("Sort applications").selectOption("deadline");
await shot("applications");

await page.getByRole("button", { name: "List", exact: true }).click();
await settle();
await page.getByLabel("Filter application stage").selectOption("draft");
await page.getByLabel("Sort applications").selectOption("deadline");
await settle();
const boxes = page.locator(".application-select input");
await boxes.nth(0).check();
await boxes.nth(2).check();
await shot("applications-planning");

await open(`applications?application=${await applicationId("Northstar Labs")}`);
await dialog().waitFor();
await shot("documents");

await open(
  `applications?application=${await applicationId("Lumen Health")}&detail=requirements`,
);
await dialog().waitFor();
await shot("requirements");

await open("collection");
await shot("collection");
await page.getByRole("button", { name: "Edit settings" }).first().click();
await dialog().waitFor();
await shot("collection-settings");

await open("career?section=knowledge");
await shot("career");

await open("settings?section=agents");
await shot("agent-access");

await browser.close();
if (errors.length) {
  console.error("Page errors:\n" + errors.join("\n"));
  process.exit(1);
}
