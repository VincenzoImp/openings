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

// The full Chromium shows PDFs in a frame, as the owner's browser does; the
// headless shell cannot. Fall back to it when only the shell is installed.
const browser = await chromium
  .launch({ channel: "chromium" })
  .catch(() => chromium.launch());
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

async function open(hash) {
  await page.goto("/#" + hash);
  await page.reload();
  await page.locator(".main h1").waitFor();
  await settle();
}
async function settle() {
  // A PDF in a frame may keep the network busy in a browser without a viewer.
  await page
    .waitForLoadState("networkidle", { timeout: 8000 })
    .catch(() => {});
  await page.waitForTimeout(400);
}
async function shot(name) {
  await settle();
  await page.evaluate(() => document.activeElement?.blur());
  // No hover state from the last click.
  await page.mouse.move(0, 0);
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
async function applicationId(company, title) {
  return page.evaluate(
    async ([company, title]) => {
      const response = await fetch("/api/v1/applications?limit=200");
      const { items } = await response.json();
      return items.find(
        (item) =>
          item.job?.company === company && (!title || item.job?.title === title),
      ).id;
    },
    [company, title],
  );
}
/** The id of a job by company and title; `duplicate` picks a flagged copy. */
async function jobId(company, title, duplicate = false) {
  return page.evaluate(
    async ([company, title, duplicate]) => {
      const response = await fetch(
        "/api/v1/jobs?limit=200&q=" + encodeURIComponent(company),
      );
      const { items } = await response.json();
      return items.find(
        (item) =>
          item.company === company &&
          item.title === title &&
          (!duplicate || item.signals?.duplicate),
      ).id;
    },
    [company, title, duplicate],
  );
}
/** The review page has read its record and its documents. */
async function review(id, tab = "") {
  await page.goto(`/#review?application=${id}${tab ? "&tab=" + tab : ""}`);
  await page.reload();
  await page.locator(".main h1").waitFor();
  await page.waitForLoadState("load");
  await page.locator(".loading").first().waitFor({ state: "detached" }).catch(() => {});
  await page.waitForTimeout(1500);
}

await open("today");
await page.getByRole("heading", { name: "Ready to apply" }).waitFor();
await shot("today");

await open(`jobs?job=${await jobId("Alpenlicht Software", "Backend-Entwickler")}`);
await page.locator("#job-title").waitFor();
await shot("jobs");

await open("jobs?section=shortlist");
await shot("shortlist");

await open(
  `jobs?job=${await jobId("Brightline AI", "Machine Learning Engineer", true)}`,
);
await page.locator("#duplicate-title").waitFor();
await page
  .locator("#duplicate-title")
  .evaluate((heading) =>
    window.scrollTo(0, heading.getBoundingClientRect().top + window.scrollY - 160),
  );
await shot("duplicates");

await open("applications?sort=deadline");
await shot("applications");

await open("applications?stage=preparing&sort=deadline");
const boxes = page.locator("[role=table] [role=rowgroup] input[type=checkbox]");
await boxes.nth(1).check();
await boxes.nth(3).check();
await shot("applications-planning");

await open("applications?view=board");
await shot("applications-board");

await open("applications?stage=applied&sort=applied");
await page
  .getByRole("row")
  .filter({ hasText: "Tidewater Energy" })
  .getByRole("button", { name: /^Record response/ })
  .click();
await page.getByRole("button", { name: "Rejection", exact: true }).click();
await page.getByLabel("Note").fill("The role was filled internally.");
await page.evaluate(() => document.activeElement?.blur());
await shot("respond");

await open("applications?section=insights");
await shot("insights");

await review(await applicationId("Fjord Analytics", "Python Engineer"));
await shot("review");

await review(await applicationId("Northstar Labs", "Python Engineer"), "documents");
await page
  .getByRole("list", { name: "Document revisions" })
  .getByRole("button", { name: /^Open Engineering CV — updated/ })
  .click();
await settle();
await page.getByRole("button", { name: "Compare with revision 1" }).click();
await settle();
await page.locator("#more").evaluate((tabs) => tabs.scrollIntoView());
await shot("documents");

await review(await applicationId("Lumen Health"), "requirements");
await page.locator("#more").evaluate((tabs) => tabs.scrollIntoView());
await shot("requirements");

await review(await applicationId("Orbit Works"), "details");
await page.locator("#more").evaluate((tabs) => tabs.scrollIntoView());
await shot("application-ready");

await open("collection");
await shot("collection");
await page
  .getByRole("table", { name: "Sources" })
  .getByRole("button", { name: "Edit", exact: true })
  .first()
  .click();
// The source form opens under the list; show it once its fields are there.
await page.locator("section:has(#source-editor) [name=name]").waitFor();
await settle();
await page
  .locator("#source-editor")
  .evaluate((heading) =>
    window.scrollTo(0, heading.getBoundingClientRect().top + window.scrollY - 88),
  );
await shot("collection-settings");

await open("collection?section=yield");
await page.getByRole("table", { name: /Yield by source/ }).waitFor();
await shot("yield");

await open("career?section=knowledge");
// Show the record with one entry open; the Profile is above it.
await page
  .getByRole("heading", { name: "Career record" })
  .evaluate((heading) => heading.scrollIntoView({ block: "start" }));
await page.evaluate(() => window.scrollBy(0, -72));
await shot("career");

await open("policy");
await shot("policy");

await open("templates?section=rules");
await shot("templates");

// The setup guide on this workspace: the record, with the Policy basics open.
await open("setup?step=record");
await page
  .getByRole("list", { name: "Your record" })
  .getByRole("button", { name: /the policy$/ })
  .click();
await page
  .getByRole("form", { name: "Add a fact employers ask about" })
  .waitFor();
await shot("setup");

await open("settings?section=agents");
await shot("agent-access");
// A new token is shown once; the screenshot shows an example in its place.
await page.getByLabel("Token name").fill("interview-agent");
await page.getByLabel("Token name").press("Enter");
await page.locator("pre.secret").waitFor();
await page
  .locator("pre.secret")
  .evaluate((secret) => (secret.textContent = "op_EXAMPLE0000000000000000000000"));
// The confirmation toast would cover the form.
await page.locator(".toast button").click();
await shot("access-tokens");

await open("settings?section=skills&skill=review-inbox");
await page.locator("section.skill pre.skill-text").waitFor();
await shot("skills");

await open("activity");
await page.getByRole("heading", { name: "Activity", exact: true }).waitFor();
await shot("activity-questions");

await open("activity?section=requests");
await page.getByRole("article").first().waitFor();
await shot("activity-requests");

await open("activity?section=runs");
await page
  .getByRole("button", { name: /review-inbox/ })
  .first()
  .click();
await page
  .locator("article.report")
  .getByRole("heading", { name: "Summary" })
  .waitFor();
await shot("activity-run");

await open("activity?section=timeline");
await page.getByRole("heading", { name: "Today", exact: true }).waitFor();
await shot("activity-timeline");

await review(await applicationId("Sable Insurance"), "timeline");
await page.locator("#more").evaluate((tabs) => tabs.scrollIntoView());
await shot("application-history");

await browser.close();
if (errors.length) {
  console.error("Page errors:\n" + errors.join("\n"));
  process.exit(1);
}
