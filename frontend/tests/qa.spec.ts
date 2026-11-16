import { test, expect } from "./fixtures";
import { go, heading, settled } from "./session";

// Regressions found by the interaction QA pass (docs/developer/qa-checklist.md).

// The widths of the QA checklist that shell.spec.ts does not already cover.
for (const width of [768, 1280, 1920, 2560])
  test(`no horizontal scroll at ${width} px on the main screens`, async ({
    page,
  }) => {
    test.skip(
      test.info().project.name !== "chromium",
      "Widths are set by the test; one project is enough.",
    );
    test.setTimeout(60000);
    await page.setViewportSize({ width, height: 1000 });
    for (const route of [
      "today",
      "jobs",
      "jobs?section=all",
      "applications",
      "applications?section=stats",
      "profile",
      "preferences",
      "templates",
      "sources",
      "settings?section=agents",
      "settings?section=advanced",
    ]) {
      await go(page, route);
      await settled(page);
      const scroll = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      expect(scroll, `${route} at ${width}px`).toBeLessThanOrEqual(width);
    }
  });

test("every stage tab of Applications is visible at tablet widths (#421)", async ({
  page,
}) => {
  test.skip(
    test.info().project.name !== "chromium",
    "Widths are set by the test; one project is enough.",
  );
  for (const width of [768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    await go(page, "applications");
    await settled(page);
    const hidden = await page
      .getByRole("tablist", { name: "Stage" })
      .evaluate((list) => {
        const edge = list.getBoundingClientRect();
        return [...list.querySelectorAll("[role=tab]")]
          .filter((tab) => {
            const box = tab.getBoundingClientRect();
            return box.left < edge.left - 1 || box.right > edge.right + 1;
          })
          .map((tab) => tab.textContent);
      });
    expect(hidden, `hidden stage tabs at ${width}px`).toEqual([]);
  }
});

test("j and x act on Applications without focusing a row first (#422)", async ({
  page,
}) => {
  test.skip(
    (page.viewportSize()?.width ?? 1440) < 720,
    "A phone has no list keys.",
  );
  await go(page, "applications");
  await settled(page);
  await expect(heading(page)).toHaveText("Applications");
  await page.keyboard.press("j");
  await page.keyboard.press("x");
  await expect(page.getByRole("toolbar", { name: "1 selected" })).toBeVisible({
    timeout: 2000,
  });
});
