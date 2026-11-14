import { test, expect } from "./fixtures";
import { call, go, ownerSession } from "./session";

const OUT =
  "/private/tmp/claude-501/-Users-vincenzo-Projects-openings/9ea408e0-cb98-4ae2-a6ae-efb20d9f2c6d/scratchpad/screens-224/scratch";

for (const width of [360, 390, 800, 1440])
  test(`overflow ${width}`, async ({ page }) => {
    test.skip(test.info().project.name !== "chromium");
    await page.context().addCookies(ownerSession());
    await page.setViewportSize({ width, height: 844 });
    await go(page, "today");
    const ready = (await call(page, "/applications?stage=ready&sort=deadline&limit=1")).items[0].id;
    const prep = (await call(page, "/applications?stage=shortlisted&needs=documents&limit=1")).items[0].id;
    const sent = (await call(page, "/applications?stage=interview&q=Research&limit=1")).items[0].id;
    for (const route of [
      "today",
      "jobs",
      "applications",
      "applications?section=stats",
      `applications/${ready}`,
      `applications/${prep}`,
      `applications/${sent}`,
    ]) {
      await go(page, route);
      await expect(page.locator(".ui-skeleton")).toHaveCount(0);
      await page.waitForTimeout(300);
      const wide = await page.evaluate(() => {
        const w = document.documentElement.clientWidth;
        const box = document.getElementById("content")!;
        const out = [] as string[];
        for (const el of document.querySelectorAll("*")) {
          const r = el.getBoundingClientRect();
          if (r.right > w + 1)
            out.push(`${el.tagName}.${(el as HTMLElement).className} ${Math.round(r.right)}`);
        }
        return [document.documentElement.scrollWidth, box.scrollWidth - box.clientWidth, out.slice(0, 8)];
      });
      console.log(width, route, JSON.stringify(wide));
      await page.screenshot({ path: `${OUT}/${width}-${route.replace(/[/?=]/g, "_")}.png` });
    }
  });
