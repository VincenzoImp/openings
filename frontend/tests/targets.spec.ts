import { test, expect, type Page } from "./fixtures";
import { call, go, isPhone, settled } from "./session";

// Two guards from the UI audit: a tooltip never reaches past the pane that
// scrolls it (it would be cut), and on a phone every control is a 44 px
// touch target, by its own box or by the ::before that extends it.

/** Each visible tooltip's box and the box of its nearest clipping ancestor. */
function tooltips(page: Page) {
  return page.evaluate(() => {
    const clipping = (element: Element) => {
      for (let node = element.parentElement; node; node = node.parentElement) {
        const style = getComputedStyle(node);
        if (style.overflowX !== "visible" || style.overflowY !== "visible")
          return node.getBoundingClientRect();
      }
      return new DOMRect(0, 0, innerWidth, innerHeight);
    };
    return [...document.querySelectorAll(".ui-icon-btn[data-tip]")]
      .filter((element) => element.getBoundingClientRect().width > 0)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const tip = getComputedStyle(element, "::after");
        const width = parseFloat(tip.width);
        const shift = new DOMMatrix(
          tip.transform === "none" ? undefined : tip.transform,
        ).m41;
        const left =
          (tip.left !== "auto"
            ? rect.left + parseFloat(tip.left)
            : rect.right - parseFloat(tip.right) - width) + shift;
        const pane = clipping(element);
        return {
          name: element.getAttribute("aria-label"),
          left,
          right: left + width,
          paneLeft: pane.left,
          paneRight: pane.right,
        };
      });
  });
}

test("a tooltip stays inside the pane that holds its button", async ({
  page,
}) => {
  test.skip(isPhone(page), "Phones show no tooltips.");
  await go(page, "today");
  const [job] = (await call(page, "/jobs?triage=new&limit=1")).items;
  const cut: string[] = [];
  for (const route of ["today", "jobs", `jobs?job=${job.id}`, "applications"]) {
    await go(page, route);
    await settled(page);
    const found = await tooltips(page);
    expect(found.length).toBeGreaterThan(0);
    for (const tip of found)
      if (tip.left < tip.paneLeft - 0.5 || tip.right > tip.paneRight + 0.5)
        cut.push(`${route}: ${tip.name}`);
  }
  expect([...new Set(cut)]).toEqual([]);
});

/** Every visible button and button link narrower or lower than 44 px. */
function smallTargets(page: Page) {
  return page.evaluate(() => {
    const small: string[] = [];
    const controls = document.querySelectorAll<HTMLElement>(
      "#content button, #content a.ui-btn, .ui-topbar button, .ui-app-bottom a",
    );
    for (const element of controls) {
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) continue;
      if (getComputedStyle(element).visibility === "hidden") continue;
      // Hidden by an ancestor that clips it to nothing (a visually hidden
      // field's control).
      if (element.closest("[inert], [aria-hidden=true]")) continue;
      // A ::before or ::after that extends the target (a 44 px ring, or a
      // row's whole area): its used size, which the style resolves to px.
      let width = rect.width;
      let height = rect.height;
      for (const pseudo of ["::before", "::after"]) {
        const style = getComputedStyle(element, pseudo);
        if (style.content === "none" || style.position !== "absolute") continue;
        width = Math.max(width, parseFloat(style.width) || 0);
        height = Math.max(height, parseFloat(style.height) || 0);
      }
      if (width < 43.5 || height < 43.5)
        small.push(
          `${element.getAttribute("aria-label") || element.textContent?.trim().slice(0, 30) || element.className} ${Math.round(width)}x${Math.round(height)}`,
        );
    }
    return small;
  });
}

test("on a phone every control is a 44 px touch target", async ({ page }) => {
  test.skip(!isPhone(page), "Touch targets are a phone's.");
  await go(page, "today");
  const [job] = (await call(page, "/jobs?triage=new&limit=1")).items;
  const [ready] = (await call(page, "/applications?stage=ready&limit=1")).items;
  const [template] = (await call(page, "/templates?limit=1")).items;
  const routes = [
    "today",
    "jobs",
    `jobs?job=${job.id}`,
    "applications",
    `applications/${ready.id}`,
    "profile",
    "preferences",
    "templates",
    `templates?template=${template.id}`,
    "sources",
    "settings",
  ];
  const found: string[] = [];
  for (const route of routes) {
    await go(page, route);
    await settled(page);
    for (const small of await smallTargets(page))
      found.push(`${route}: ${small}`);
  }
  expect(found).toEqual([]);
});
