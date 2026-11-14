import { test, expect, type Page } from "./fixtures";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// The Library screens built with the design system: Preferences and
// Templates. Every dashboard path of their operations is exercised here. Each
// test starts from the seeded workspace (fixtures.ts).
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

/** A REST call of the test itself, marked so that it is not dashboard evidence. */
async function call(
  page: Page,
  path: string,
  method = "GET",
  body?: unknown,
  token?: string,
) {
  return page.evaluate(
    async ({ path, method, body, token }) => {
      const session = await fetch("/api/v1/auth/session").then((response) =>
        response.json(),
      );
      const response = await fetch("/api/v1" + path, {
        method,
        credentials: token ? "omit" : "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(token
            ? { Authorization: "Bearer " + token }
            : { "X-CSRF-Token": session.csrf_token }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const value = await response.json();
      if (!response.ok) throw Error(JSON.stringify(value));
      return value;
    },
    { path, method, body, token },
  );
}
const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const sectionCard = (page: Page, title: string) =>
  page.locator("section.card").filter({
    has: page.getByRole("heading", { name: title, exact: true }),
  });
/** One section of Preferences, as REST returns it. */
const section = async (page: Page, name: string) =>
  (await call(page, "/preferences")).sections.find(
    (item: any) => item.section === name,
  );
/** On a narrow screen a list and its detail are shown one at a time. */
async function show(page: Page, pane: string) {
  if (isNarrow(page))
    await page
      .getByRole("group", { name: "Shown pane" })
      .getByRole("button", { name: pane, exact: true })
      .click();
}
const dialog = (page: Page) => page.locator("dialog[open]").last();
const saved = (page: Page, text: string | RegExp) =>
  expect(page.locator(".toast").last()).toContainText(text);

test("preferences statements are added, edited, scoped, reordered and deleted", async ({
  page,
}) => {
  const fact = unique("Fact");
  await go(page, "preferences");
  const facts = sectionCard(page, "Facts about me");
  // The statement an agent added is shown like any other.
  await expect(
    facts.locator("li").filter({
      hasText: "Interviews on Tuesday or Thursday after 16:00.",
    }),
  ).toBeVisible();
  await facts.getByRole("button", { name: "Add to Facts about me" }).click();
  const form = facts.getByRole("form", {
    name: "New statement in Facts about me",
  });
  await form.getByLabel("Statement").fill(fact);
  await form.getByRole("button", { name: "Save" }).click();
  await saved(page, "Added to Facts about me.");
  const row = facts.locator("li").filter({ hasText: fact });
  await expect(row).toBeVisible();
  // REST returns what the dashboard shows, at the end of the section.
  expect((await section(page, "facts")).items.at(-1)).toEqual({ text: fact });

  const edited = unique("Edited");
  await row.getByRole("button", { name: `Edit ${fact}` }).click();
  const edit = facts.getByRole("form", { name: `Edit the statement ${fact}` });
  await edit.getByLabel("Statement").fill(edited);
  await edit.getByRole("button", { name: "Save" }).click();
  const editedRow = facts.locator("li").filter({ hasText: edited });
  await expect(editedRow).toBeVisible();
  await expect(facts.locator("li").filter({ hasText: fact })).toHaveCount(0);

  // It moves up from the keyboard-operable buttons, one place at a time.
  const before = (await section(page, "facts")).items.map(
    (item: any) => item.text,
  );
  await editedRow.getByRole("button", { name: `Move ${edited} up` }).click();
  await saved(page, "Order saved.");
  const after = (await section(page, "facts")).items.map(
    (item: any) => item.text,
  );
  expect(after.indexOf(edited)).toBe(before.indexOf(edited) - 1);
  expect(after.length).toBe(before.length);

  // Only a writing rule has a scope.
  await expect(facts.getByLabel("Applies to")).toHaveCount(0);
  const rule = unique("Rule");
  const writing = sectionCard(page, "Writing rules");
  await writing.getByRole("button", { name: "Add to Writing rules" }).click();
  const ruleForm = writing.getByRole("form", {
    name: "New statement in Writing rules",
  });
  await ruleForm.getByLabel("Statement").fill(rule);
  await ruleForm.getByLabel("Applies to").selectOption("cv");
  await ruleForm.getByRole("button", { name: "Save" }).click();
  const ruleRow = writing.locator("li").filter({ hasText: rule });
  await expect(ruleRow.locator(".tag")).toHaveText("CV");
  expect((await section(page, "writing")).items.at(-1)).toEqual({
    text: rule,
    scope: "cv",
  });

  // Deleting is in the statement's menu, and asks first.
  for (const [card, text] of [
    [facts, edited],
    [writing, rule],
  ] as const) {
    const item = card.locator("li").filter({ hasText: text });
    await item
      .getByRole("button", { name: `More actions for ${text}` })
      .click();
    await item.getByRole("button", { name: `Delete ${text}` }).click();
    await expect(dialog(page)).toContainText(text);
    await dialog(page)
      .getByRole("button", { name: "Delete statement", exact: true })
      .click();
    await expect(card.locator("li").filter({ hasText: text })).toHaveCount(0);
  }
  expect((await section(page, "facts")).items).toEqual(
    before
      .filter((text: string) => text !== edited)
      .map((text: string) => ({
        text,
      })),
  );
});

test("the languages spoken and the no-reply period are set under Facts about me", async ({
  page,
}) => {
  await go(page, "preferences");
  const facts = sectionCard(page, "Facts about me");
  const spoken = facts.getByRole("list", { name: "Languages I speak" });
  await expect(spoken.getByRole("button")).toHaveText(["English", "Italian"]);
  await spoken.getByRole("button", { name: "Remove Italian" }).click();
  await saved(page, "Italian removed.");
  await expect(spoken.getByRole("button")).toHaveText(["English"]);
  const add = facts.getByRole("form", { name: "Add a language" });
  await add.getByLabel("Language").selectOption("de");
  await add.getByRole("button", { name: "Add language" }).click();
  await expect(spoken.getByRole("button")).toHaveText(["English", "German"]);
  const days = facts.getByLabel("Count an application as no reply after");
  await expect(days).toHaveValue("45");
  await days.fill("60");
  await facts
    .getByRole("form", { name: "Following up" })
    .getByRole("button", { name: "Save" })
    .click();
  await saved(page, "after 60 days count as no reply");
  const settings = (await call(page, "/preferences")).settings;
  expect([settings.spoken_languages, settings.no_reply_days]).toEqual([
    ["en", "de"],
    60,
  ]);
  // The applications read the period from the settings.
  expect((await call(page, "/applications?limit=1")).no_reply).toMatchObject({
    days: 60,
    source: "settings",
  });
});

test("keyboard only: a statement is edited, saved, moved and deleted", async ({
  page,
}) => {
  const text = unique("Notice");
  const writing = await section(page, "writing");
  await call(page, "/preferences/writing", "PUT", {
    expected_version: writing.version,
    items: [...writing.items, { text, scope: "all" }],
  });
  await go(page, "preferences");
  const card = sectionCard(page, "Writing rules");
  await card.getByRole("button", { name: `Edit ${text}` }).focus();
  await page.keyboard.press("Enter");
  // The form opens with focus in its text.
  const form = card.getByRole("form", { name: `Edit the statement ${text}` });
  await expect(form.getByLabel("Statement")).toBeFocused();
  const changed = unique("Two months");
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(changed);
  // Safari reaches every control with Option+Tab; the other browsers with Tab.
  const tab =
    page.context().browser()?.browserType().name() === "webkit"
      ? "Alt+Tab"
      : "Tab";
  await page.keyboard.press(tab);
  await expect(form.getByLabel("Applies to")).toBeFocused();
  await page.keyboard.press(tab);
  await expect(form.getByRole("button", { name: "Save" })).toBeFocused();
  await page.keyboard.press("Enter");
  const row = card.locator("li").filter({ hasText: changed });
  await expect(row.locator(".prose")).toHaveText(changed);
  await expect(row.locator(".tag")).toHaveText("All documents");
  expect((await section(page, "writing")).items.at(-1)).toEqual({
    text: changed,
    scope: "all",
  });

  // Reordering keeps focus on the button that was pressed.
  const up = row.getByRole("button", { name: `Move ${changed} up` });
  await up.focus();
  await page.keyboard.press("Enter");
  await saved(page, "Order saved.");
  await expect(up).toBeFocused();
  const order = (await section(page, "writing")).items.map(
    (item: any) => item.text,
  );
  expect(order.indexOf(changed)).toBe(order.length - 2);

  // Escape leaves the confirmation; Enter on its button deletes the statement.
  const more = row.getByRole("button", { name: `More actions for ${changed}` });
  await more.focus();
  await page.keyboard.press("Enter");
  await expect(more).toHaveAttribute("aria-expanded", "true");
  await row.getByRole("button", { name: `Delete ${changed}` }).focus();
  await page.keyboard.press("Enter");
  await expect(dialog(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await more.focus();
  await page.keyboard.press("Enter");
  await row.getByRole("button", { name: `Delete ${changed}` }).focus();
  await page.keyboard.press("Enter");
  await dialog(page).getByRole("button", { name: "Delete statement" }).focus();
  await page.keyboard.press("Enter");
  await expect(row).toHaveCount(0);
});

test("a preferences conflict reloads the section and keeps the unsaved text", async ({
  page,
}) => {
  const text = unique("Salary");
  const other = unique("Elsewhere");
  const facts = await section(page, "facts");
  const created = await call(page, "/preferences/facts", "PUT", {
    expected_version: facts.version,
    items: [...facts.items, { text }],
  });
  await go(page, "preferences");
  const card = sectionCard(page, "Facts about me");
  await card.getByRole("button", { name: `Edit ${text}` }).click();
  const form = card.getByRole("form", { name: `Edit the statement ${text}` });
  await form.getByLabel("Statement").fill("My unsaved statement.");
  // Another session adds a statement: the section has a newer version.
  const added = await call(page, "/preferences/facts", "PUT", {
    expected_version: created.version,
    items: [...created.items, { text: other }],
  });
  await form.getByRole("button", { name: "Save" }).click();
  await expect(form.getByRole("alert")).toContainText(
    "changed in another session. Your text is kept",
  );
  await expect(form.getByLabel("Statement")).toHaveValue(
    "My unsaved statement.",
  );
  // The latest list is shown beside the form, and saving again succeeds.
  await expect(card.locator("li").filter({ hasText: other })).toBeVisible();
  await form.getByRole("button", { name: "Save" }).click();
  await expect(
    card.locator("li").filter({ hasText: "My unsaved statement." }),
  ).toBeVisible();
  await expect(card.locator("li").filter({ hasText: text })).toHaveCount(0);
  // A button pressed on a stale section says so and shows the latest state.
  // The save above may still be finishing, so read the version once it has.
  await page.waitForLoadState("networkidle");
  const current = await section(page, "facts");
  expect(current.items.map((item: any) => item.text)).toEqual([
    ...added.items
      .map((item: any) => item.text)
      .filter((item: string) => item !== other && item !== text),
    "My unsaved statement.",
    other,
  ]);
  await call(page, "/preferences/facts", "PUT", {
    expected_version: current.version,
    items: current.items.filter((item: any) => item.text !== other),
  });
  const mine = card.locator("li").filter({ hasText: "My unsaved statement." });
  await mine
    .getByRole("button", { name: "Move My unsaved statement. down" })
    .click();
  await expect(page.locator(".toast.error").last()).toContainText(
    "changed in another session",
  );
  await expect(card.locator("li").filter({ hasText: other })).toHaveCount(0);
  await expect(
    mine.getByRole("button", { name: "Move My unsaved statement. down" }),
  ).toBeDisabled();
});

test("a template's source, typed rules, assets and sample are managed end to end", async ({
  page,
}) => {
  const name = unique("Letter");
  await go(page, "templates");
  await page.getByRole("button", { name: "Add a template" }).click();
  await expect(
    dialog(page).getByRole("link", { name: "letter.tex" }),
  ).toHaveAttribute("href", "/api/v1/examples/letter.tex");
  await dialog(page).getByLabel("Name").fill(name);
  await dialog(page)
    .getByLabel("Document", { exact: true })
    .selectOption("letter");
  await dialog(page).getByLabel("LaTeX source").fill("\\documentclass{letter}");
  await dialog(page).getByRole("button", { name: "Add template" }).click();
  const detail = page.locator("section.detail");
  await expect(
    detail.getByRole("heading", { name, exact: true }),
  ).toBeVisible();
  const read = async () =>
    (await call(page, `/templates?summary=false&q=${encodeURIComponent(name)}`))
      .items[0];

  // Source: the text is edited in place and saved with the version.
  await detail.getByLabel("LaTeX source").fill("\\documentclass{letter}\n% v2");
  await detail.getByRole("button", { name: "Save source" }).click();
  await saved(page, "Source saved.");
  expect((await read()).tex).toBe("\\documentclass{letter}\n% v2");

  // Guidance: the text and the limits. Other keys (an agent's engine) are
  // not shown and are kept; writing rules live in Preferences.
  const current = await read();
  await call(page, `/templates/${current.id}`, "PATCH", {
    expected_version: current.version,
    rules: { engine: "lualatex" },
  });
  await page.reload();
  await expect(page.locator(".page-head")).toContainText(
    "Writing rules live in Preferences.",
  );
  await expect(
    page.locator(".page-head").getByRole("link", { name: "Preferences" }),
  ).toHaveAttribute("href", "#preferences");
  await detail.getByRole("tab", { name: "Guidance" }).click();
  await expect(page.locator("textarea[name=rules]")).toHaveCount(0);
  await expect(detail.getByText("Other settings")).toHaveCount(0);
  await detail
    .getByLabel("Guidance for this template")
    .fill("Three paragraphs.");
  await detail.getByLabel("Pages").fill("1");
  await detail.getByRole("button", { name: "Save", exact: true }).click();
  await saved(page, "Saved. Applications that were already prepared");
  await expect
    .poll(async () => (await read()).rules)
    .toEqual({
      engine: "lualatex",
      max_pages: 1,
    });
  expect((await read()).guidance).toBe("Three paragraphs.");

  // Assets: files are added and listed; a PDF becomes the sample under Preview.
  await detail.getByRole("tab", { name: /^Assets/ }).click();
  await detail.getByLabel("Files to add").setInputFiles([
    {
      name: "letter.cls",
      mimeType: "text/plain",
      buffer: Buffer.from("% synthetic class"),
    },
    {
      name: "sample.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n% synthetic sample\n%%EOF"),
    },
  ]);
  await expect(detail.locator("tbody tr")).toHaveCount(2);
  await expect(detail.getByRole("tab", { name: /^Assets/ })).toContainText("2");
  await detail.getByRole("tab", { name: "Preview" }).click();
  await expect(
    detail.locator(`iframe[title="Sample of ${name}"]`),
  ).toBeVisible();
  await detail.getByRole("tab", { name: /^Assets/ }).click();
  await detail.getByRole("button", { name: "Remove sample.pdf" }).click();
  await dialog(page).getByRole("button", { name: "Remove file" }).click();
  await expect(detail.locator("tbody tr")).toHaveCount(1);
  await detail.getByRole("tab", { name: "Preview" }).click();
  await expect(detail.getByText("No preview yet")).toBeVisible();

  // Name, kind and default; removal.
  await detail.getByRole("button", { name: "Rename" }).click();
  await dialog(page)
    .getByLabel("Name")
    .fill(name + " renamed");
  await dialog(page).getByRole("button", { name: "Save template" }).click();
  await expect(
    detail.getByRole("heading", { name: name + " renamed", exact: true }),
  ).toBeVisible();
  await detail.getByRole("button", { name: "Make default" }).click();
  await expect(detail.locator("header .tag")).toHaveText("Default Letter");
  await expect(
    page.getByRole("button", { name: "General instructions" }),
  ).toHaveCount(0);
  await detail.getByRole("button", { name: "Delete", exact: true }).click();
  await dialog(page).getByRole("button", { name: "Remove template" }).click();
  await expect(
    page
      .getByRole("region", { name: "Templates by kind" })
      .getByRole("button", { name: name + " renamed" }),
  ).toHaveCount(0);
  await expect.poll(read).toBeUndefined();
});

test("links of earlier versions open the rebuilt screens", async ({ page }) => {
  const template = (await call(page, "/templates?summary=true&limit=2"))
    .items[1];
  await go(page, `templates?template=${template.id}&section=instructions`);
  await expect(
    page.getByRole("heading", { name: template.name, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Guidance" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await go(page, `templates?template=${template.id}&section=assets`);
  await expect(page.getByRole("tab", { name: /^Assets/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await go(page, "preferences");
  await expect(
    page.getByRole("heading", { name: "Preferences", level: 1 }),
  ).toBeVisible();
});
