// The browser of every capture: the screenshots, the demo reel, the video
// footage (playwright.config.ts) and the social preview. The Ready
// application shows its CV and letter in the browser's own PDF viewer, which
// Playwright's default headless shell does not have. Google Chrome is used
// when it is installed, otherwise Playwright's Chromium in the new headless
// mode; $OPENINGS_CAPTURE_CHANNEL names another Playwright channel.
import { expect } from "@playwright/test";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { inflateSync } from "node:zlib";

const CHROME = {
  darwin: ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
  linux: ["/opt/google/chrome/chrome"],
  win32: [process.env.PROGRAMFILES, process.env.LOCALAPPDATA]
    .filter(Boolean)
    .map((dir) => join(dir, "Google/Chrome/Application/chrome.exe")),
};

/** The Playwright channel of a capture. */
export const CAPTURE_CHANNEL =
  process.env.OPENINGS_CAPTURE_CHANNEL ||
  ((CHROME[process.platform] ?? []).some((path) => existsSync(path))
    ? "chrome"
    : "chromium");

/**
 * How the PDF in a well (its `box` in image pixels) shows in `image`:
 * `paper`, whether the page is drawn (white at the top centre), and `margin`,
 * how many pixels just inside the well's left, right and top edges show the
 * viewer's dark background (rgb 40, 40, 40) in runs of three or more.
 */
function pdfShown(image, box) {
  const left = Math.max(box.x + 2, 0);
  const right = Math.min(box.x + box.width - 3, image.width - 1);
  const top = Math.max(box.y + 2, 0);
  const bottom = Math.min(box.y + box.height - 1, image.height);
  const viewer = (x, y) =>
    image.rgb(x, y).every((value) => Math.abs(value - 40) <= 6);
  const run = (points) => {
    let count = 0;
    let streak = 0;
    for (const [x, y] of points) {
      streak = viewer(x, y) ? streak + 1 : 0;
      if (streak === 3) count += 3;
      else if (streak > 3) count += 1;
    }
    return count;
  };
  const range = (from, to) =>
    Array.from({ length: Math.max(to - from, 0) }, (_, i) => from + i);
  const column = (x) => range(top, bottom).map((y) => [x, y]);
  const row = (y) => range(left, right + 1).map((x) => [x, y]);
  return {
    paper: image
      .rgb(Math.round((left + right) / 2), top)
      .every((value) => value >= 252),
    margin: run(column(left)) + run(column(right)) + run(row(top)),
  };
}

/**
 * The pixels of a screenshot: an 8-bit RGB or RGBA PNG, not interlaced. The
 * image is read here, not in a page, so the captured page keeps its focus
 * and its PDFs stay drawn.
 */
function decodePng(png) {
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  const channels = { 2: 3, 6: 4 }[png[25]];
  if (png[24] !== 8 || !channels || png[28] !== 0)
    throw Error("The screenshot is not an 8-bit RGB(A) PNG.");
  const chunks = [];
  for (let at = 8; at < png.length;) {
    const length = png.readUInt32BE(at);
    if (png.toString("latin1", at + 4, at + 8) === "IDAT")
      chunks.push(png.subarray(at + 8, at + 8 + length));
    at += length + 12;
  }
  const raw = inflateSync(Buffer.concat(chunks));
  const stride = width * channels;
  const pixels = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const at = y * stride + x;
      const a = x >= channels ? pixels[at - channels] : 0;
      const b = y ? pixels[at - stride] : 0;
      const c = x >= channels && y ? pixels[at - stride - channels] : 0;
      const p = a + b - c;
      const pa = Math.abs(p - a);
      const pb = Math.abs(p - b);
      const pc = Math.abs(p - c);
      const predictor = [
        0,
        a,
        b,
        (a + b) >> 1,
        pa <= pb && pa <= pc ? a : pb <= pc ? b : c,
      ][filter];
      pixels[at] = (line[x] + predictor) & 255;
    }
  }
  const rgb = (x, y) => {
    const at = y * stride + x * channels;
    return [pixels[at], pixels[at + 1], pixels[at + 2]];
  };
  return { width, height, rgb };
}

/**
 * A screenshot of `page` (with Playwright's screenshot `options`, but no
 * path) in which every visible PDF of an application fills its well, taken
 * again until it does. The image itself is checked, not the page, because
 * the viewer may draw a page again at any moment.
 */
export async function screenshotWithPdfs(page, options = {}) {
  const wells = pdfWells(page);
  let image;
  await expect
    .poll(
      async () => {
        image = await page.screenshot(options);
        const pixels = decodePng(image);
        const shown = [];
        for (const well of await wells.all())
          shown.push(
            pdfShown(
              pixels,
              await well.evaluate((element, fullPage) => {
                const box = element.getBoundingClientRect();
                const [x, y] = fullPage ? [scrollX, scrollY] : [0, 0];
                const scale = devicePixelRatio;
                return {
                  x: Math.round((box.x + x) * scale),
                  y: Math.round((box.y + y) * scale),
                  width: Math.round(box.width * scale),
                  height: Math.round(box.height * scale),
                };
              }, !!options.fullPage),
            ),
          );
        return shown.every(({ paper, margin }) => paper && !margin)
          ? "shown"
          : JSON.stringify(shown);
      },
      {
        message: "Every PDF fills its well, with no viewer margin.",
        timeout: 15_000,
      },
    )
    .toBe("shown");
  return image;
}

const pdfWells = (page) =>
  page.locator(".ap-well:has(> .ap-pdf)").filter({ visible: true });

/** Wait until every visible PDF of an application fills its well. */
export async function expectPdfsShown(page) {
  if (await pdfWells(page).count()) await screenshotWithPdfs(page);
}

/** Fail unless pages of this browser show PDFs. */
export async function expectPdfViewer(browser) {
  const page = await browser.newPage();
  try {
    if (await page.evaluate(() => navigator.pdfViewerEnabled)) return;
  } finally {
    await page.close();
  }
  throw Error(
    `The capture browser (channel "${CAPTURE_CHANNEL}", ${browser.version()}) ` +
      "has no PDF viewer, so the Ready application would show no CV or letter. " +
      "Install Google Chrome, or Playwright's Chromium " +
      "(`npx --prefix frontend playwright install chromium`).",
  );
}
