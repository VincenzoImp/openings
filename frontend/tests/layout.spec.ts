import { test, expect, type Page } from "./fixtures";
import { call, fitsViewport, go, settled } from "./session";

// One layout rule (tokens.css, --content): a pane holds a list or a
// document. A list spans its pane; a document is one column of at most
// --content plus the pane padding, centred in its pane. Checked at the widths
// where a left-anchored column read as unfinished.
const DOCUMENTS = [
  { route: "today", block: ".today", max: 808 },
  { route: "preferences", block: ".prefs", max: 808 },
  { route: "profile", block: ".pf", max: 1016 },
  { route: "settings", block: ".set-screen", max: 1000 },
];
const LISTS = [
  { route: "applications", row: ".ap-body .ui-row" },
  { route: "sources", row: ".src-row" },
];

type Box = { left: number; right: number; width: number };

/** The inner box of `pane` (without its scrollbar) and the box of `block`. */
function measure(page: Page, pane: string, block: string) {
  return page.evaluate(
    ([pane, block]) => {
      const outer = document.querySelector(pane)!;
      const rect = outer.getBoundingClientRect();
      const left = rect.left + outer.clientLeft;
      const inner = { left, right: left + outer.clientWidth };
      const box = document.querySelector(block)!.getBoundingClientRect();
      return [
        { ...inner, width: inner.right - inner.left },
        { left: box.left, right: box.right, width: box.width },
      ] as [Box, Box];
    },
    [pane, block],
  );
}

const gaps = (pane: Box, box: Box) =>
  Math.abs(box.left - pane.left - (pane.right - box.right));

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name.endsWith("mobile"),
    "The widths are set per block; a phone project would repeat them.",
  );
});

for (const width of [1280, 1728, 1920, 2560])
  test.describe(`${width} px`, () => {
    test.use({ viewport: { width, height: 1000 } });

    for (const { route, block, max } of DOCUMENTS)
      test(`${route} is a centred document`, async ({ page }) => {
        await go(page, route);
        await settled(page);
        const [pane, box] = await measure(page, ".ui-app-content", block);
        expect(box.width).toBeLessThanOrEqual(max);
        expect(gaps(pane, box)).toBeLessThanOrEqual(1);
        await fitsViewport(page);
      });

    for (const { route, row } of LISTS)
      test(`${route} rows span the pane`, async ({ page }) => {
        await go(page, route);
        await settled(page);
        const [pane, box] = await measure(page, ".ui-app-content", row);
        expect(Math.abs(box.right - pane.right)).toBeLessThanOrEqual(1);
      });

    test("jobs: the list and the job fill the pane, the job read centred", async ({
      page,
    }) => {
      await go(page, "jobs?section=all");
      await settled(page);
      const [pane, split] = await measure(page, ".ui-app-content", ".ui-split");
      expect(Math.abs(split.right - pane.right)).toBeLessThanOrEqual(1);
      await expect(page.locator(".ui-detail-body h2").first()).toBeVisible();
      const [detail, body] = await measure(
        page,
        ".ui-split-detail",
        ".ui-detail-body",
      );
      expect(body.width).toBeLessThanOrEqual(808);
      expect(gaps(detail, body)).toBeLessThanOrEqual(1);
      await fitsViewport(page);
    });
  });

test.describe("720 px", () => {
  test.use({ viewport: { width: 720, height: 1000 } });
  test("a document fills a narrow pane", async ({ page }) => {
    await go(page, "today");
    await settled(page);
    const [pane, box] = await measure(page, ".ui-app-content", ".today");
    expect(Math.abs(box.width - Math.min(pane.width, 808))).toBeLessThanOrEqual(
      1,
    );
    await fitsViewport(page);
  });
});

test.describe("390 px", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("an application's CV text uses the phone's width, as the posting does", async ({
    page,
  }) => {
    await go(page, "today");
    const ready = await call(page, "/applications?stage=ready&limit=1");
    await go(page, `applications/${ready.items[0].id}`);
    await settled(page);
    await page.getByRole("tab", { name: "CV" }).click();
    const cv = page.getByRole("region", { name: "CV" });
    await cv.getByRole("radio", { name: "Text" }).click();
    const paper = cv.locator(".ap-paper");
    await expect(paper).toBeVisible();
    // Characters a line: the text's inner width over one character's width.
    const perLine = await paper.evaluate((element) => {
      const probe = document.createElement("span");
      probe.style.position = "absolute";
      probe.style.whiteSpace = "nowrap";
      probe.textContent = "abcdefghijklmnopqrstuvwxyz".repeat(4);
      element.append(probe);
      const char = probe.getBoundingClientRect().width / 104;
      probe.remove();
      const style = getComputedStyle(element);
      const inner =
        element.clientWidth -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight);
      return Math.floor(inner / char);
    });
    expect(perLine).toBeGreaterThanOrEqual(40);
    await fitsViewport(page);
  });
});
