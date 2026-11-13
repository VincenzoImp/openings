import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "./fixtures";

// The design system gallery (ui.html, src/ui): every primitive renders in
// both themes without errors, axe findings or horizontal scroll, and the
// keyboard models work. The dashboard never serves ui.html, so the test hands
// the built page to the browser; its scripts and styles come from /assets.
const GALLERY = resolve(import.meta.dirname, "../dist/ui.html");
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function open(page: Page, theme: "light" | "dark" = "light") {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/ui.html", (route) =>
    route.fulfill({ path: GALLERY, contentType: "text/html" }),
  );
  await page.addInitScript((value) => {
    try {
      localStorage.setItem("openings-theme", value);
    } catch {}
  }, theme);
  await page.goto("/ui.html");
  await expect(
    page.getByRole("heading", { name: "Openings design system" }),
  ).toBeVisible();
  return errors;
}

for (const theme of ["light", "dark"] as const)
  test(`every primitive renders in the ${theme} theme`, async ({ page }) => {
    const errors = await open(page, theme);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBe(0);
    const { violations } = await new AxeBuilder({ page })
      .withTags(TAGS)
      .analyze();
    expect(
      violations.map(
        (v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`,
      ),
    ).toEqual([]);
    expect(errors).toEqual([]);
  });

test("no horizontal scroll from 360 to 1600 px", async ({ page }) => {
  await open(page);
  for (const width of [360, 720, 1024, 1600]) {
    await page.setViewportSize({ width, height: 900 });
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow, `${width} px`).toBe(0);
  }
});

test("the theme switch sets the theme of the page", async ({ page }) => {
  await open(page);
  await page
    .getByRole("radiogroup", { name: "Theme" })
    .getByRole("radio", { name: "Dark" })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("a list moves with j/k, dismisses with d and undoes with ⌘Z", async ({
  page,
}) => {
  await open(page);
  const list = page.getByRole("region", { name: "Jobs to review" });
  const current = list.locator("[aria-current=true]");
  await current.focus();
  await expect(current).toContainText("Data Engineer, Grid Platform");
  await page.keyboard.press("j");
  await expect(current).toContainText("Python Engineer");
  await expect(current).toBeFocused();
  await page.keyboard.press("k");
  await page.keyboard.press("j");
  await page.keyboard.press("d");
  await expect(page.locator(".ui-toast-region [role=status]")).toContainText(
    "Dismissed “Python Engineer”",
  );
  await expect(list.getByText("Python Engineer")).toHaveCount(0);
  await page.keyboard.press("ControlOrMeta+z");
  await expect(list.getByText("Python Engineer")).toHaveCount(1);
});

test("a menu opens from the keyboard, moves with arrows and closes with Esc", async ({
  page,
}) => {
  await open(page);
  const trigger = page.getByRole("button", { name: "Open the menu" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const menu = page.getByRole("menu", { name: "Job actions", exact: true });
  await expect(menu).toBeVisible();
  await expect(
    menu.getByRole("menuitem", { name: "Open posting" }),
  ).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(menu.getByRole("menuitem", { name: /Add note/ })).toBeFocused();
  await page.keyboard.press("m");
  await expect(
    menu.getByRole("menuitem", { name: "Mark as duplicate…" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("a confirm dialog focuses Cancel, closes on Esc and returns focus", async ({
  page,
}) => {
  await open(page);
  const trigger = page.getByRole("button", { name: "Delete…" });
  await trigger.click();
  const dialog = page.getByRole("dialog", {
    name: "Delete this job permanently?",
  });
  await expect(dialog.locator("button", { hasText: "Cancel" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("read first, edit on purpose: save bar and the leave question", async ({
  page,
}) => {
  await open(page);
  const block = page.getByRole("region", { name: "Profile" }).first();
  await expect(block.locator("input")).toHaveCount(0);
  await block.getByRole("button", { name: "Edit" }).click();
  await block.getByLabel("Name").fill("Alex M. Morgan");
  await expect(block.getByText("1 unsaved change")).toBeVisible();
  await block.getByRole("button", { name: "Cancel" }).click();
  const leave = page.getByRole("dialog", { name: "Discard unsaved changes?" });
  await leave.getByRole("button", { name: "Keep editing" }).click();
  await expect(block.getByLabel("Name")).toHaveValue("Alex M. Morgan");
  await block.getByLabel("Name").press("ControlOrMeta+Enter");
  await expect(block.getByText("Alex M. Morgan")).toBeVisible();
  await expect(block.locator("input")).toHaveCount(0);
});

test("every Tab stop shows a focus ring", async ({ page, browserName }) => {
  test.skip(browserName === "webkit", "Safari skips links on Tab");
  // Reduced motion: no transition delays the ring.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);
  const unmarked: string[] = [];
  for (let stop = 0; stop < 60; stop++) {
    await page.keyboard.press("Tab");
    const missing = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      // The ring is what changes when the element loses focus.
      const host = el.closest(".ui-search") ?? el;
      const look = () =>
        [el, host]
          .map((node) => {
            const style = getComputedStyle(node);
            return `${style.boxShadow}|${style.outlineStyle}|${style.borderColor}`;
          })
          .join(" ");
      const focused = look();
      // The next Tab continues from here, focused or not.
      el.blur();
      const blurred = look();
      return focused !== blurred
        ? null
        : `${el.tagName.toLowerCase()} ${
            el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 30)
          }`;
    });
    if (missing) unmarked.push(missing);
  }
  expect(unmarked).toEqual([]);
});
