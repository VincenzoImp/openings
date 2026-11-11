// Captures the static dashboard prototypes and checks them.
//
//   npm --prefix frontend ci
//   npx --prefix frontend playwright install chromium
//   node docs/developer/prototypes/screenshots.mjs
//
// Writes viewport-sized PNG files to docs/developer/prototypes/screens/ and exits
// with a non-zero status when a page has a JavaScript error or scrolls
// horizontally at one of the checked widths, in any of its tabs.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = join(here, "..", "..", "..", "frontend");
const { chromium } = createRequire(join(frontend, "package.json"))(
  "@playwright/test",
);

const PAGES = [
  "index",
  "today",
  "review",
  "applications",
  "jobs",
  "activity",
  "career",
  "policy",
  "templates",
  "collection",
  "settings",
  "onboarding",
];
const DARK = ["today", "review"];
const WIDTHS = [360, 390, 860, 1440, 1600];
const out = join(here, "screens");
mkdirSync(out, { recursive: true });

const url = (name, theme) =>
  `${pathToFileURL(join(here, `${name}.html`))}?theme=${theme}`;
const overflow = (page) =>
  page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );

const browser = await chromium.launch();
const failures = [];

async function open(name, theme, width, height) {
  const page = await browser.newPage({ viewport: { width, height } });
  page.on("pageerror", (error) =>
    failures.push(`${name} at ${width}px: JavaScript error: ${error.message}`),
  );
  page.on("console", (message) => {
    if (message.type() === "error")
      failures.push(`${name} at ${width}px: console error: ${message.text()}`);
  });
  await page.goto(url(name, theme));
  return page;
}

for (const name of PAGES) {
  const shots = [
    ["desktop", "light", 1440, 1000],
    ["mobile", "light", 390, 844],
    ...(DARK.includes(name) ? [["desktop", "dark", 1440, 1000]] : []),
  ];
  for (const [label, theme, width, height] of shots) {
    const page = await open(name, theme, width, height);
    await page.screenshot({ path: join(out, `${name}-${label}-${theme}.png`) });
    await page.close();
  }

  // Every tab of every tab list is opened once at every width.
  const widest = [];
  for (const width of WIDTHS) {
    const page = await open(name, "light", width, 900);
    let worst = await overflow(page);
    const count = await page.locator('[role="tab"]').count();
    for (let index = 0; index < count; index += 1) {
      // Open the tabs that contain this one first, then the tab itself.
      await page.evaluate((position) => {
        const chain = [];
        let tab = document.querySelectorAll('[role="tab"]')[position];
        while (tab) {
          chain.unshift(tab);
          const panel = tab.closest('[role="tabpanel"]');
          tab = panel
            ? document.querySelector(`[aria-controls="${panel.id}"]`)
            : null;
        }
        for (const item of chain) item.click();
      }, index);
      worst = Math.max(worst, await overflow(page));
    }
    if (worst > 0)
      failures.push(
        `${name} at ${width}px: scrolls horizontally by ${worst}px`,
      );
    widest.push(`${width}:${worst}`);
    await page.close();
  }
  console.log(`${name.padEnd(13)} overflow ${widest.join("  ")}`);
}
await browser.close();

if (failures.length) {
  console.error(`\n${failures.length} problem(s):`);
  for (const failure of failures) console.error(`  ${failure}`);
  process.exit(1);
}
console.log(
  `\n${PAGES.length} pages checked, no errors, no horizontal overflow.`,
);
