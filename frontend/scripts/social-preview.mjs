// `node scripts/social-preview.mjs [--small <file.png>]`: render the GitHub
// social preview, docs/images/social-preview.png (1280×640, under 1 MB).
//
// The card is an HTML page drawn by the capture browser (capture.mjs, which
// fails without a PDF viewer, as the screenshots do): the wordmark with
// the Doorway mark (docs/brand/), the tagline in two lines, three claims of
// the register (docs/brand/README.md) and the slug, beside a crop of the real
// Ready screen of the demo workspace: rank 1, "Priority 1", both PDFs. That crop is docs/images/ready.png, which
// `npm run screenshots -- --docs` writes: run it first after a change to the
// screens. Colours, type, radii and shadows are the dashboard's own tokens,
// read from src/ui/tokens.css, and the font is its own Inter, weights 400-600.
//
// --small also writes the card at 600 px wide, the size of a LinkedIn or X
// card, to check that it reads there.
import { chromium } from "@playwright/test";
import { CAPTURE_CHANNEL, expectPdfViewer } from "./capture.mjs";
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
  "Set up your job search once.",
  ["Your AI agent works it by your rules.", "You just apply."],
];
const CLAIMS = [
  "Your career, rules and templates, set up once",
  "Fresh jobs from your searches and 12 hiring platforms",
  "Your agent tailors each CV and letter, ranked best first",
];
const SLUG = "github.com/VincenzoImp/openings-job-search";

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
h1 { margin-top: 44px; font-size: 42px; line-height: 50px; font-weight: var(--w-semibold); letter-spacing: var(--tr-3xl); }
.lede { margin-top: 12px; font-size: 28px; line-height: 36px; font-weight: var(--w-medium); letter-spacing: var(--tr-3xl); color: var(--text-2); }
ul { list-style: none; padding: 0; margin-top: 40px; display: grid; gap: 16px; }
li { display: flex; gap: 12px; align-items: center; font-size: 20px; line-height: 26px; font-weight: var(--w-medium); color: var(--text); }
li svg { color: var(--accent); flex: none; }
.slug { position: absolute; left: 64px; bottom: 44px; font-size: 18px; line-height: 24px; color: var(--text-2); }
.shot { position: absolute; left: 656px; top: 64px; width: 660px; height: 620px; overflow: hidden; border-radius: var(--r-xl); border: 1px solid var(--border-strong); box-shadow: var(--shadow-lg); background: var(--bg); }
.shot img { display: block; width: 749px; margin-left: -125px; }
</style></head><body>
<div class="left">
  <img class="wordmark" src="${wordmark}" alt="Openings">
  <h1>${TAGLINE[0]}</h1>
  <p class="lede">${TAGLINE[1].join("<br>")}</p>
  <ul>${CLAIMS.map((claim) => `<li>${check}${claim}</li>`).join("")}</ul>
</div>
<div class="slug">${SLUG}</div>
<div class="shot"><img src="${ready}" alt=""></div>
</body></html>`;

const args = process.argv.slice(2);
const small = args.includes("--small")
  ? args[args.indexOf("--small") + 1]
  : null;
const browser = await chromium.launch({ channel: CAPTURE_CHANNEL });
try {
  await expectPdfViewer(browser);
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
