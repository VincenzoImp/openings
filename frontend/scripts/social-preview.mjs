// `node scripts/social-preview.mjs [--small <file.png>]`: render the GitHub
// social preview, docs/images/social-preview.png (1280×640, under 1 MB).
//
// The card is an HTML page drawn by Playwright's Chromium: the wordmark with
// the Doorway mark (docs/brand/), the tagline, the short form, three claims of
// the register (docs/brand/README.md) and the slug, beside a crop of the real
// Ready screen of the demo workspace. That crop is docs/images/ready.png, which
// `npm run screenshots -- --docs` writes: run it first after a change to the
// screens. Colours, type, radii and shadows are the dashboard's own tokens,
// read from src/ui/tokens.css, and the font is its own Inter, weights 400-600.
//
// --small also writes the card at 600 px wide, the size of a LinkedIn or X
// card, to check that it reads there.
import { chromium } from "@playwright/test";
import { readFileSync, statSync } from "node:fs";

const at = (path) => new URL(`../../${path}`, import.meta.url);
const dataUrl = (path, type) =>
  `data:${type};base64,${readFileSync(at(path)).toString("base64")}`;
const OUT = at("docs/images/social-preview.png");
const MAX_BYTES = 1_000_000;

const tokens = readFileSync(at("frontend/src/ui/tokens.css"), "utf8");
const font = dataUrl(
  "frontend/node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  "font/woff2",
);
const wordmark = dataUrl("docs/brand/wordmark-mark.svg", "image/svg+xml");
const ready = dataUrl("docs/images/ready.png", "image/png");

// Every sentence is in the claims register or the message of docs/brand.
const TAGLINE = [
  "Every new job, filtered,",
  "prepared and ranked.",
  "You just apply.",
];
const STEPS = ["Collect", "Prepare", "Rank", "You apply"];
const CLAIMS = [
  "Nothing in Openings submits to an employer.",
  "No AI inside, no account, no telemetry.",
  "One container, one SQLite file, on your machine.",
];
const SLUG = "github.com/VincenzoImp/openings-job-search";

const arrow = `<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 8h11M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const check = `<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><style>
${tokens}
@font-face { font-family: "Inter Variable"; font-weight: 400 600; src: url(${font}) format("woff2"); }
* { box-sizing: border-box; margin: 0; }
html, body { width: 1280px; height: 640px; overflow: hidden; }
body { background: var(--bg); color: var(--text); font-family: var(--font); position: relative; }
.left { position: absolute; left: 64px; top: 56px; width: 560px; }
.wordmark { height: 48px; display: block; }
h1 { margin-top: 40px; font-size: 44px; line-height: 52px; font-weight: var(--w-semibold); letter-spacing: var(--tr-3xl); }
.steps { display: flex; align-items: center; gap: var(--s-2); margin-top: 28px; color: var(--text-3); }
.step { font-size: 20px; line-height: 24px; font-weight: var(--w-medium); padding: 8px 14px; border-radius: var(--r-lg); color: var(--accent-text); background: var(--accent-soft); border: 1.5px solid var(--accent); }
.step.you { color: var(--on-primary); background: var(--primary); border-color: var(--primary); }
ul { list-style: none; padding: 0; margin-top: 32px; display: grid; gap: 14px; }
li { display: flex; gap: 12px; align-items: center; font-size: 20px; line-height: 26px; font-weight: var(--w-medium); color: var(--text); }
li svg { color: var(--accent); flex: none; }
.slug { position: absolute; left: 64px; bottom: 44px; font-size: 18px; line-height: 24px; color: var(--text-2); }
.shot { position: absolute; left: 660px; top: 64px; width: 700px; height: 620px; overflow: hidden; border-radius: var(--r-xl); border: 1px solid var(--border-strong); box-shadow: var(--shadow-lg); background: var(--bg); }
.shot img { display: block; width: 792px; margin-left: -132px; }
</style></head><body>
<div class="left">
  <img class="wordmark" src="${wordmark}" alt="Openings">
  <h1>${TAGLINE.join("<br>")}</h1>
  <div class="steps">${STEPS.map((step, index) => `<span class="step${index === STEPS.length - 1 ? " you" : ""}">${step}</span>`).join(arrow)}</div>
  <ul>${CLAIMS.map((claim) => `<li>${check}${claim}</li>`).join("")}</ul>
</div>
<div class="slug">${SLUG}</div>
<div class="shot"><img src="${ready}" alt=""></div>
</body></html>`;

const args = process.argv.slice(2);
const small = args.includes("--small")
  ? args[args.indexOf("--small") + 1]
  : null;
const browser = await chromium.launch();
try {
  for (const [path, scale] of [
    [OUT, 1],
    ...(small ? [[small, 600 / 1280]] : []),
  ]) {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 640 },
      deviceScaleFactor: scale,
    });
    await page.setContent(html);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path instanceof URL ? path.pathname : path });
    await page.close();
  }
} finally {
  await browser.close();
}
const size = statSync(OUT).size;
console.log(`docs/images/social-preview.png: ${Math.round(size / 1000)} kB`);
if (size >= MAX_BYTES) {
  console.error("The social preview must stay under 1 MB.");
  process.exit(1);
}
