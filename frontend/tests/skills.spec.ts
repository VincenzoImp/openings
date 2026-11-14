import { test, expect, type Page } from "./fixtures";
import { call, fitsViewport, go, ownerSession, type Cookies } from "./session";

// Settings, Skills: what the owner can ask their agent, read from the skills
// this version ships (a title, one sentence and an example each). The
// dashboard shows no skill text and offers no editor. Each test starts from
// the seeded workspace (fixtures.ts).
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
  await go(page, "today");
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

interface Skill {
  name: string;
  title: string;
  summary: string;
  example: string;
}

test("What you can ask your agent lists every skill with a title, a sentence and an example", async ({
  page,
}) => {
  const skills = (await call(page, "/skills")).items as Skill[];
  expect(skills.length).toBeGreaterThan(0);
  await go(page, "settings?section=skills");
  await expect(
    page.getByRole("heading", { name: "What you can ask your agent" }),
  ).toBeVisible();
  const list = page.getByRole("list", { name: "What you can ask your agent" });
  const items = list.getByRole("listitem");
  await expect(items).toHaveCount(skills.length);
  for (const [index, skill] of skills.entries()) {
    expect(skill.title, skill.name).toBeTruthy();
    expect(skill.summary, skill.name).toBeTruthy();
    expect(skill.example, skill.name).toBeTruthy();
    const item = items.nth(index);
    await expect(item.getByRole("heading", { level: 3 })).toHaveText(
      skill.title,
    );
    await expect(item).toContainText(skill.summary);
    await expect(item).toContainText(`For example: “${skill.example}”`);
  }
  // Read-only: no skill text, no editor, no link to a skill's files.
  await expect(page.locator("main textarea")).toHaveCount(0);
  await expect(page.locator("main pre")).toHaveCount(0);
  await expect(list.getByRole("link")).toHaveCount(0);
  await expect(list.getByRole("button")).toHaveCount(0);
  await expect(page.getByText("Local notes")).toHaveCount(0);
  await fitsViewport(page);
});

test("keyboard only: reach Skills from the Settings tabs", async ({ page }) => {
  await go(page, "settings");
  const tab = page.getByRole("tab", { name: "Agent access" });
  await tab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Skills" })).toBeFocused();
  await expect(page).toHaveURL(/#settings\?section=skills$/);
  await expect(
    page.getByRole("heading", { name: "What you can ask your agent" }),
  ).toBeVisible();
  // An old address of one skill opens the list.
  await go(page, "settings?section=skills&skill=prepare-shortlist");
  await expect(
    page.getByRole("list", { name: "What you can ask your agent" }),
  ).toBeVisible();
});
