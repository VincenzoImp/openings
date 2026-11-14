import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "./fixtures";
import { call, go, isPhone, ownerSession, upload } from "./session";

// Profile (#profile): the career record read as a CV, one block edited at a
// time. Each test starts from the seeded workspace (fixtures.ts); the same
// journeys run at desktop width (in place, with the save bar) and on a phone
// (a full-screen sheet with Cancel and Save in its header).
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(ownerSession());
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const SENIOR = "Senior data engineer";
const toast = (page: Page, text: string | RegExp) =>
  expect(page.getByRole("status").filter({ hasText: text })).toBeVisible();
const form = (page: Page, name: string) =>
  page.getByRole("form", { name, exact: true });
const save = (page: Page) =>
  page.getByRole("button", { name: /^Save( ⌘↵)?$/ }).click();
/**
 * A block's Edit or … button. At rest a phone shows the CV as text: a tap
 * on the block shows its actions first.
 */
async function blockButton(page: Page, name: string) {
  const button = page.getByRole("button", {
    name,
    exact: true,
    includeHidden: true,
  });
  if (isPhone(page)) {
    await button
      .locator(
        "xpath=ancestor::div[contains(concat(' ', @class, ' '), ' pf-block ')][1]",
      )
      .click({ position: { x: 4, y: 4 } });
    await expect(button).toBeVisible();
  }
  await button.click();
}
async function entryByTitle(page: Page, title: string) {
  const { items } = await call(
    page,
    `/career/knowledge?summary=false&q=${encodeURIComponent(title)}`,
  );
  return items.find((item: { title: string }) => item.title === title);
}
const highlightsOf = async (page: Page, id: string) =>
  (await call(page, `/career/claims?summary=false&career_id=${id}`)).items;

test("the profile reads as a CV: no fields, one primary button, no internals", async ({
  page,
}) => {
  await go(page, "profile");
  const main = page.locator("#content");
  await expect(main.getByText("Alex Morgan", { exact: true })).toBeVisible();
  await expect(
    main.getByRole("heading", { name: SENIOR, exact: true }),
  ).toBeVisible();
  await expect(main.getByText("Feb 2022 – Present")).toBeVisible();
  await expect(main.locator("input:visible, textarea:visible")).toHaveCount(0);
  await expect(main.locator(".ui-btn[data-variant=primary]")).toHaveCount(0);
  await expect(main.getByText(/Version \d|Order|team_size/)).toHaveCount(0);
  // An unapproved highlight says so; a starred one carries ★.
  await expect(main.getByText("Not approved").first()).toBeVisible();
  await expect(
    main.getByRole("img", { name: "Always include in my CV" }).first(),
  ).toBeVisible();
  // A long section shows its first entries, then all.
  await main.getByRole("button", { name: "Show all 35" }).click();
  await expect(
    main.getByRole("heading", { name: "Synthetic project 34" }),
  ).toBeVisible();
  // The skills of the whole record, once each.
  await expect(
    main.locator("#pf-skills").getByText("Python", { exact: true }),
  ).toHaveCount(1);
});

test("the header is edited and cancelled; leaving with changes asks first", async ({
  page,
}) => {
  await go(page, "profile");
  await blockButton(page, "Edit header");
  const header = form(page, "Edit header");
  await header.getByLabel("Headline").fill("Changed headline");
  if (!isPhone(page))
    await expect(page.getByText("1 unsaved change")).toBeVisible();
  // Another block cannot open over unsaved changes without asking.
  if (!isPhone(page)) {
    await page.getByRole("button", { name: "Add experience" }).click();
    const ask = page.getByRole("dialog", { name: "Discard unsaved changes?" });
    await ask.getByRole("button", { name: "Keep editing" }).click();
    await expect(header.getByLabel("Headline")).toHaveValue("Changed headline");
  }
  await header.getByLabel("Headline").press("Escape");
  await page
    .getByRole("dialog", { name: "Discard unsaved changes?" })
    .getByRole("button", { name: "Discard" })
    .click();
  await expect(header).toHaveCount(0);
  await expect(page.getByText("Senior data engineer").first()).toBeVisible();
  expect((await call(page, "/career/profile")).headline).toBe(SENIOR);
  // Saving keeps the metadata the API holds.
  const before = await call(page, "/career/profile");
  await blockButton(page, "Edit header");
  await form(page, "Edit header").getByLabel("Phone").fill("+41 00 000 00 00");
  await save(page);
  await toast(page, "Saved the header");
  const stored = await call(page, "/career/profile");
  expect(stored.phone).toBe("+41 00 000 00 00");
  expect(stored.metadata).toEqual(before.metadata);
  await expect(
    page.locator("#content").getByText("+41 00 000 00 00"),
  ).toBeVisible();
});

test("an entry is edited and saved, with its place and dates", async ({
  page,
}) => {
  await go(page, "profile");
  await blockButton(page, `Edit ${SENIOR}`);
  const entry = form(page, `Edit ${SENIOR}`);
  await entry.getByLabel("Organization").fill("Example Energy");
  await entry.getByLabel("Location").fill("Basel");
  await entry.getByRole("checkbox", { name: "Present" }).uncheck();
  await entry.getByLabel("End year").fill("2025");
  await entry.getByLabel("End month").selectOption("06");
  await entry.getByLabel("Description").press("ControlOrMeta+Enter");
  await toast(page, `Saved “${SENIOR}”`);
  const stored = await entryByTitle(page, SENIOR);
  expect(stored.organization).toBe("Example Energy");
  expect(stored.dates).toMatchObject({
    kind: "period",
    start: "2022-02",
    end: "2025-06",
  });
  expect(stored.metadata.location).toBe("Basel");
  expect(stored.metadata.team_size).toBe(6);
  await expect(page.getByText("Example Energy · Basel")).toBeVisible();
  await expect(page.getByText("Feb 2022 – Jun 2025")).toBeVisible();
});

test("highlights are added, approved, starred and reordered inside their entry", async ({
  page,
}) => {
  await go(page, "profile");
  const id = (await entryByTitle(page, SENIOR)).id;
  await blockButton(page, `Edit ${SENIOR}`);
  const entry = form(page, `Edit ${SENIOR}`);
  await entry.getByRole("button", { name: "Approve highlight 4" }).click();
  await entry.getByRole("button", { name: "Add highlight" }).click();
  await entry
    .getByRole("textbox", { name: "Highlight 5", exact: true })
    .fill("Mentored two junior engineers.");
  await entry
    .getByRole("button", { name: "Always include in my CV" })
    .nth(4)
    .click();
  // Move the first highlight down, from its handle's menu.
  await entry
    .getByRole("button", { name: "Move highlight 1", exact: true })
    .click();
  await page.getByRole("menuitem", { name: "Move down" }).click();
  await save(page);
  await toast(page, `Saved “${SENIOR}”`);
  const items = await highlightsOf(page, id);
  const texts = items
    .sort((a: any, b: any) => a.position - b.position)
    .map((item: any) => item.text);
  expect(texts.slice(0, 2)).toEqual([
    "Moved reporting queries to PostgreSQL and cut their time by 70%.",
    "Built Python pipelines that process 40 million measurements a day.",
  ]);
  const added = items.find((item: any) => item.text.startsWith("Mentored"));
  expect(added).toMatchObject({ approved: true, always_include: true });
  expect(items.every((item: any) => item.approved)).toBe(true);
});

test("a highlight is approved from the read view", async ({ page }) => {
  await go(page, "profile");
  const id = (await entryByTitle(page, SENIOR)).id;
  await page
    .getByRole("button", {
      name: "Approve: Led the migration of 14 pipelines to a new scheduler.",
    })
    .first()
    .click();
  await toast(page, "Approved the highlight");
  expect(
    (await highlightsOf(page, id)).every((item: any) => item.approved),
  ).toBe(true);
});

test("an entry is added where its dates put it", async ({ page }) => {
  await go(page, "profile");
  await page.getByRole("button", { name: "Add experience" }).click();
  const entry = form(page, "New experience");
  // A title is needed; the error says so.
  if (isPhone(page)) await save(page);
  else {
    await entry.getByLabel("Title").fill("Staff engineer");
    await entry.getByLabel("Title").fill("");
    await entry.getByLabel("Organization").focus();
  }
  await expect(entry.getByText("Add a title.")).toBeVisible();
  await entry.getByLabel("Title").fill("Staff engineer");
  await entry.getByLabel("Organization").fill("Example Fusion");
  await entry.getByLabel("Start year").fill("2024");
  await entry.getByRole("checkbox", { name: "Present" }).check();
  await entry.getByRole("button", { name: "Add highlight" }).click();
  await entry
    .getByRole("textbox", { name: "Highlight 1", exact: true })
    .fill("Set up the data platform.");
  await save(page);
  await toast(page, "Added “Staff engineer”");
  const experience = page.locator("#pf-experience h3");
  await expect(experience.first()).toHaveText("Staff engineer");
  const stored = await entryByTitle(page, "Staff engineer");
  expect(stored).toMatchObject({
    kind: "experience",
    organization: "Example Fusion",
  });
  expect(await highlightsOf(page, stored.id)).toHaveLength(1);
});

test("an entry is deleted permanently after the dialog lists what goes", async ({
  page,
}) => {
  await go(page, "profile");
  const stored = await entryByTitle(page, "Synthetic project 03");
  await upload(
    page,
    "career",
    stored.id,
    "reference.txt",
    Buffer.from("Ref"),
    "text/plain",
  );
  await page.reload();
  await expect(page.getByText("reference.txt")).toBeVisible();
  await blockButton(page, "More actions for Synthetic project 03");
  await page.getByRole("menuitem", { name: "Delete permanently…" }).click();
  const ask = page.getByRole("dialog", {
    name: "Delete “Synthetic project 03” permanently?",
  });
  await expect(ask).toContainText("Synthetic claim 03");
  await expect(ask).toContainText("reference.txt");
  await ask.getByRole("button", { name: "Delete permanently" }).click();
  await toast(page, "Deleted “Synthetic project 03”");
  expect(await entryByTitle(page, "Synthetic project 03")).toBeUndefined();
});

test("CV text is imported only after its preview is confirmed", async ({
  page,
}) => {
  await go(page, "profile");
  const before = (await call(page, "/career/knowledge?limit=1")).total;
  if (isPhone(page))
    await page.getByRole("button", { name: "Import CV text" }).last().click();
  else await page.getByRole("button", { name: "Import CV text" }).click();
  const drawer = page.getByRole("dialog", { name: "Import CV text" });
  await drawer
    .getByRole("textbox", { name: "CV text" })
    .fill(
      [
        "## Experience",
        "### Data analyst — Example Retail",
        "2016 – 2019 · Porto",
        "- Built the weekly sales dashboard.",
        "- Cleaned ten years of store data.",
      ].join("\n"),
    );
  await drawer.getByRole("button", { name: "Preview" }).click();
  const preview = page.getByRole("dialog", { name: "Check what was found" });
  await expect(preview).toContainText("1 entry and 2 highlights");
  await expect(preview).toContainText("Example Retail · 2016 – 2019 · Porto");
  await expect(preview).toContainText("Cleaned ten years of store data.");
  expect((await call(page, "/career/knowledge?limit=1")).total).toBe(before);
  await preview.getByRole("button", { name: "Add 1 entry" }).click();
  await toast(page, "Imported 1 entry");
  const stored = await entryByTitle(page, "Data analyst");
  expect(stored).toMatchObject({
    kind: "experience",
    organization: "Example Retail",
    metadata: { location: "Porto" },
  });
  expect(
    (await highlightsOf(page, stored.id)).map((item: any) => item.text),
  ).toEqual([
    "Built the weekly sales dashboard.",
    "Cleaned ten years of store data.",
  ]);
});

test("a block changed elsewhere keeps the draft: Keep editing, then save", async ({
  page,
}) => {
  await go(page, "profile");
  await blockButton(page, "Edit header");
  const header = form(page, "Edit header");
  await header.getByLabel("Headline").fill("My unsaved headline");
  const current = await call(page, "/career/profile");
  await call(page, "/career/profile", "PATCH", {
    expected_version: current.version,
    location: "Geneva",
  });
  await save(page);
  await expect(page.getByText("Changed elsewhere")).toBeVisible();
  await expect(header.getByLabel("Headline")).toHaveValue(
    "My unsaved headline",
  );
  await page.getByRole("button", { name: "Keep editing" }).click();
  await save(page);
  await toast(page, "Saved the header");
  const stored = await call(page, "/career/profile");
  expect(stored.headline).toBe("My unsaved headline");
  // The change made elsewhere to another field stays.
  expect(stored.location).toBe("Geneva");
});

test("editing is a sheet on a phone and in place on a wide screen; both pass axe", async ({
  page,
}) => {
  await go(page, "profile");
  await blockButton(page, `Edit ${SENIOR}`);
  const sheet = page.locator("dialog.pf-sheet[open]");
  if (isPhone(page)) {
    await expect(sheet).toBeVisible();
    await expect(
      sheet.getByRole("heading", { name: `Edit ${SENIOR}` }),
    ).toBeVisible();
    await expect(sheet.getByRole("button", { name: "Save" })).toBeVisible();
  } else await expect(sheet).toHaveCount(0);
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(
    violations
      .filter((item) => item.impact === "serious" || item.impact === "critical")
      .map((item) => item.id),
  ).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  await expect(form(page, `Edit ${SENIOR}`)).toHaveCount(0);
});
