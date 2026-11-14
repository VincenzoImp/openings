import { test, expect, type Page } from "./fixtures";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// The Library screens built with the design system: Preferences, Career and
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

test("the profile is saved with typed fields and keeps its metadata", async ({
  page,
}) => {
  const headline = unique("Engineer");
  const before = await call(page, "/career/profile");
  await go(page, "career");
  const profile = page.getByRole("form", { name: "Profile" });
  await profile.getByLabel("Headline").fill(headline);
  // Target roles and preferences are Preferences statements, not Profile fields.
  await expect(profile.getByLabel("Target roles")).toHaveCount(0);
  await expect(profile.getByLabel("Preferences")).toHaveCount(0);
  // No free-form editor and no JSON text box.
  await expect(profile.getByText("Other details")).toHaveCount(0);
  await expect(page.locator("textarea[name=metadata]")).toHaveCount(0);
  await profile.getByRole("button", { name: "Save profile" }).click();
  await saved(page, "Profile saved.");
  const stored = await call(page, "/career/profile");
  expect(stored.headline).toBe(headline);
  expect(stored).not.toHaveProperty("roles");
  expect(stored).not.toHaveProperty("preferences");
  // Metadata stays in the API: saving here does not change it.
  expect(stored.metadata).toEqual(before.metadata);
});

test("a career entry with claims, the star, files and import is managed end to end", async ({
  page,
}) => {
  const title = unique("Staff engineer");
  await go(page, "career?section=knowledge");
  await page
    .getByRole("button", { name: "Add an entry", exact: true })
    .first()
    .click();
  const editor = page.locator("section.detail");
  await expect(
    editor.getByRole("heading", { name: "New entry" }),
  ).toBeVisible();
  await editor.getByLabel("Job title").fill(title);
  await editor.getByLabel("Organization (optional)").fill("Example Labs");
  await editor.getByLabel("Dates").selectOption("period");
  await editor.getByLabel("From year").fill("2020");
  await editor.getByLabel("From month").selectOption("03");
  await editor.getByLabel("Until today").check();
  await editor.getByLabel("Add a skill").fill("Rust");
  await page.keyboard.press("Enter");
  await editor.getByLabel("Add a skill").fill("Go, SQL");
  await page.keyboard.press("Enter");
  await editor.getByLabel("Description").fill("Built storage services.");
  await expect(editor.getByText("Other details")).toHaveCount(0);
  await editor.getByRole("button", { name: "Save entry" }).click();
  await expect(
    editor.getByRole("heading", { name: `Edit entry: ${title}` }),
  ).toBeVisible();
  const list = page.getByRole("region", { name: "Entries by kind" });
  const item = list.locator("li").filter({ hasText: title });
  await show(page, "Record");
  await expect(item).toContainText("Example Labs · Mar 2020 – Present");
  await expect(item).toContainText("No claims yet");
  await show(page, "Selected entry");
  const entry = (
    await call(
      page,
      `/career/knowledge?summary=false&q=${encodeURIComponent(title)}`,
    )
  ).items[0];
  expect([entry.skills, entry.dates.start]).toEqual([
    ["Rust", "Go", "SQL"],
    "2020-03",
  ]);

  // A claim: added as a draft, approved, then starred.
  const text = `Cut storage cost by a third (${Date.now()}).`;
  await editor.getByRole("button", { name: "Add a claim" }).click();
  await expect(dialog(page).getByLabel("Order")).toHaveCount(0);
  await dialog(page).getByLabel("Claim", { exact: true }).fill(text);
  await dialog(page).getByRole("button", { name: "Save claim" }).click();
  const claim = editor.locator(".claim").filter({ hasText: text });
  await expect(claim.locator(".tag")).toHaveText("Not approved");
  await claim.getByRole("button", { name: /^Approve: / }).click();
  await expect(claim.locator(".tag")).toHaveText("Approved");
  await expect(claim.getByRole("button", { name: /^Approve: / })).toHaveCount(
    0,
  );
  const star = claim.getByRole("button", {
    name: /^Always include in my CV: /,
  });
  await expect(star).toHaveAttribute("aria-pressed", "false");
  await star.click();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  // No role, group or order on the row.
  await expect(claim.locator("select, input")).toHaveCount(0);
  const read = async () =>
    (await call(page, `/career/claims?summary=false&knowledge_id=${entry.id}`))
      .items[0];
  let stored = await read();
  expect([stored.approved, stored.always_include]).toEqual([true, true]);
  expect(stored).not.toHaveProperty("role");
  expect(stored).not.toHaveProperty("group");
  await show(page, "Record");
  await expect(item).toContainText("1 claim");
  await show(page, "Selected entry");

  // The editor of a claim, from its menu: what an agent keeps in its
  // metadata survives an edit here.
  await call(page, `/career/claims/${stored.id}`, "PATCH", {
    expected_version: stored.version,
    metadata: { source: "Synthetic review" },
  });
  await claim
    .getByRole("button", { name: /^More actions for claim: / })
    .click();
  await claim.getByRole("button", { name: /^Edit claim: / }).click();
  await expect(dialog(page).getByText("Other details")).toHaveCount(0);
  await expect(
    dialog(page).getByLabel("Always include in my CV"),
  ).toBeChecked();
  await dialog(page)
    .getByLabel("Claim", { exact: true })
    .fill(text + " Twice.");
  await dialog(page).getByRole("button", { name: "Save claim" }).click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  stored = await read();
  expect([stored.text, stored.always_include, stored.metadata]).toEqual([
    text + " Twice.",
    true,
    { source: "Synthetic review" },
  ]);

  // Every claim of the record is searched in one list.
  await page.getByRole("tab", { name: "All claims" }).click();
  await page.getByLabel("Search the record").fill("Twice");
  const found = page.locator(".claims .claim").filter({ hasText: "Twice." });
  await expect(found).toContainText(`${title} · Example Labs`);
  await page.getByLabel("Approval").selectOption("false");
  await expect(found).toHaveCount(0);
  await page.getByLabel("Approval").selectOption("true");
  // Approval is withdrawn in the editor.
  await found
    .getByRole("button", { name: /^More actions for claim: / })
    .click();
  await found.getByRole("button", { name: /^Edit claim: / }).click();
  await dialog(page)
    .getByLabel("I have checked and approve this claim")
    .uncheck();
  await dialog(page).getByRole("button", { name: "Save claim" }).click();
  await expect(found).toHaveCount(0);
  await page.getByRole("tab", { name: "Entries" }).click();
  await show(page, "Record");
  await page.getByLabel("Search the record").fill(title);
  await item.getByRole("button", { name: /^Open / }).click();

  // Files of the entry: added, opened, downloaded and removed after asking.
  await editor.getByLabel("Files to add").setInputFiles({
    name: "reference.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic reference letter."),
  });
  const file = editor.locator("tr").filter({ hasText: "reference.txt" });
  await expect(file).toBeVisible();
  await file
    .getByRole("button", { name: "reference.txt", exact: true })
    .click();
  await expect(dialog(page).getByRole("region")).toHaveText(
    "Synthetic reference letter.",
  );
  await expect(dialog(page).locator("dl")).toContainText(/[0-9a-f]{64}/);
  await dialog(page)
    .getByRole("button", { name: "Close", exact: true })
    .click();
  const download = page.waitForEvent("download");
  await file.getByRole("button", { name: "Download reference.txt" }).click();
  expect((await download).suggestedFilename()).toBe("reference.txt");
  await file.getByRole("button", { name: "Remove reference.txt" }).click();
  await dialog(page).getByRole("button", { name: "Remove file" }).click();
  await expect(file).toHaveCount(0);

  // The claim and then the entry are removed with their versions.
  await claim
    .getByRole("button", { name: /^More actions for claim: / })
    .click();
  await claim.getByRole("button", { name: /^Delete claim: / }).click();
  await dialog(page).getByRole("button", { name: "Delete claim" }).click();
  await expect(claim).toHaveCount(0);
  await editor.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(dialog(page)).toContainText(`${title} · Example Labs`);
  await dialog(page).getByRole("button", { name: "Remove entry" }).click();
  await expect(item).toHaveCount(0);

  // Import: an example to start from, a preview, then the entries.
  const imported = unique("Imported project");
  await page.getByLabel("Search the record").fill("");
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await expect(
    dialog(page).getByRole("link", { name: "Download an example" }),
  ).toHaveAttribute("href", "/api/v1/examples/career.json");
  await dialog(page)
    .getByLabel("Text or JSON", { exact: true })
    .fill(JSON.stringify([{ kind: "project", title: imported }]));
  await dialog(page).getByRole("button", { name: "Preview import" }).click();
  await expect(dialog(page).getByRole("list")).toContainText(imported);
  await dialog(page).getByRole("button", { name: "Confirm import" }).click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await page.getByLabel("Search the record").fill(imported);
  await expect(list.locator("li").filter({ hasText: imported })).toBeVisible();
  const created = (
    await call(page, `/career/knowledge?q=${encodeURIComponent(imported)}`)
  ).items[0];
  await call(
    page,
    `/career/knowledge/${created.id}?expected_version=${created.version}`,
    "DELETE",
  );
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
  await go(page, "career?section=claims&q=claim 07");
  await expect(page.getByRole("tab", { name: "All claims" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.locator(".claims .claim")).toHaveCount(1);
  await go(page, "career?section=knowledge&q=project 07");
  if (isNarrow(page))
    await page
      .getByRole("button", { name: /^Open Synthetic project 07/ })
      .click();
  await expect(
    page.getByRole("heading", { name: "Edit entry: Synthetic project 07" }),
  ).toBeVisible();
  await go(page, "preferences");
  await expect(
    page.getByRole("heading", { name: "Preferences", level: 1 }),
  ).toBeVisible();
});
