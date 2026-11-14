import { test, expect, type Page } from "./fixtures";
import { call, go, isPhone, ownerSession } from "./session";

// Preferences: statements as lines of text in five sections, edited in
// place; the spoken languages and the no-reply period. Each test starts from
// the seeded workspace (fixtures.ts).
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(ownerSession());
  await go(page, "preferences");
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const texts = async (page: Page, name: string) =>
  (
    (await call(page, "/preferences")).sections.find(
      (section: { section: string }) => section.section === name,
    ).items as { text: string; scope?: string }[]
  ).map((item) => (item.scope ? `${item.text} [${item.scope}]` : item.text));
const lines = (page: Page, title: string) =>
  page.getByRole("list", { name: title, exact: true }).getByRole("listitem");
const line = (page: Page, title: string, text: string) =>
  lines(page, title).filter({ hasText: text });
const statement = (page: Page) =>
  page.getByRole("textbox", { name: "Statement" });

/** Open a line's `…` menu: a popover on wide screens, a sheet on a phone. */
async function more(page: Page, title: string, text: string) {
  const row = line(page, title, text);
  await row.hover();
  await row.getByRole("button", { name: /^More for/ }).click();
  return page
    .getByRole("menu", { name: /^Statement/ })
    .filter({ visible: true });
}

test("statements are added, edited, tagged, reordered, moved and deleted", async ({
  page,
}) => {
  // At rest the page is text: no field and no button on a line.
  await expect(
    page
      .locator(".prefs")
      .locator("input, textarea, select")
      .filter({ visible: true }),
  ).toHaveCount(0);
  await expect(page.locator(".pref-lines li").getByRole("button")).toHaveCount(
    0,
  );

  // + Add writes a line in place; Enter saves it and opens the next one.
  await page
    .getByRole("button", { name: "Add to What I'm looking for" })
    .click();
  await statement(page).fill("Synthetic: climate tech");
  await statement(page).press("Enter");
  await expect(statement(page)).toHaveValue("");
  await statement(page).fill("Synthetic: second line");
  await statement(page).press("Enter");
  await statement(page).press("Escape");
  await expect(statement(page)).toHaveCount(0);
  await expect
    .poll(() => texts(page, "looking_for"))
    .toEqual([
      "Data, backend and platform engineering roles at mid to senior level.",
      "On site in Zurich or Basel, or remote within Europe.",
      "Synthetic: climate tech",
      "Synthetic: second line",
    ]);

  // Edit: inline, with Save and Cancel.
  const climate = line(page, "What I'm looking for", "Synthetic: climate tech");
  await climate.hover();
  await climate.getByRole("button", { name: /^Edit/ }).click();
  await statement(page).fill("Synthetic: changed then cancelled");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(climate).toBeVisible();
  await climate.focus();
  await page.keyboard.press("Enter");
  await statement(page).fill("Synthetic: climate and energy tech");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    line(page, "What I'm looking for", "Synthetic: climate and energy tech"),
  ).toBeVisible();

  // Reorder with the keyboard: Alt+↑ moves the focused line up.
  await line(page, "What I'm looking for", "Synthetic: second line").focus();
  await page.keyboard.press("Alt+ArrowUp");
  await expect
    .poll(async () => (await texts(page, "looking_for")).slice(2))
    .toEqual(["Synthetic: second line", "Synthetic: climate and energy tech"]);

  // A writing rule is tagged All · CV · Letter.
  await page.getByRole("button", { name: "Add to Writing rules" }).click();
  await statement(page).fill("Synthetic: no photo on the CV");
  await page
    .getByRole("radiogroup", { name: "Applies to" })
    .getByRole("radio", { name: "CV" })
    .click();
  await statement(page).press("Enter");
  await statement(page).press("Escape");
  await expect(
    line(page, "Writing rules", "Synthetic: no photo on the CV"),
  ).toContainText("CV");
  await expect
    .poll(async () => (await texts(page, "writing")).at(-1))
    .toBe("Synthetic: no photo on the CV [cv]");

  // Move to another section from the … menu (a bottom sheet on a phone).
  const menu = await more(
    page,
    "What I'm looking for",
    "Synthetic: climate and energy tech",
  );
  await menu.getByRole("menuitem", { name: "What I rule out" }).click();
  await expect
    .poll(async () => (await texts(page, "ruled_out")).at(-1))
    .toBe("Synthetic: climate and energy tech");
  expect(await texts(page, "looking_for")).not.toContain(
    "Synthetic: climate and energy tech",
  );

  // Delete runs at once with Undo; the menu's Delete too.
  await line(
    page,
    "What I rule out",
    "Synthetic: climate and energy tech",
  ).focus();
  await page.keyboard.press("Delete");
  const toast = page.getByRole("status").filter({ hasText: "Deleted" });
  await toast.getByRole("button", { name: /Undo/ }).click();
  await expect
    .poll(async () => (await texts(page, "ruled_out")).at(-1))
    .toBe("Synthetic: climate and energy tech");
  const again = await more(
    page,
    "What I rule out",
    "Synthetic: climate and energy tech",
  );
  await again.getByRole("menuitem", { name: "Delete" }).click();
  await expect
    .poll(() => texts(page, "ruled_out"))
    .not.toContain("Synthetic: climate and energy tech");
});

test("a line is reordered by dragging its handle", async ({ page }) => {
  test.skip(isPhone(page), "Touch reorders the same way; one width is enough.");
  const first = line(page, "What I rule out", "Roles that need me");
  const second = line(page, "What I rule out", "Pure frontend roles");
  await first.hover();
  const grip = first.getByRole("button", { name: /^Reorder/ });
  const from = (await grip.boundingBox())!;
  const to = (await second.boundingBox())!;
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + 4, to.y + to.height - 2, { steps: 6 });
  await page.mouse.up();
  await expect
    .poll(() => texts(page, "ruled_out"))
    .toEqual([
      "Pure frontend roles and agencies that hire for clients.",
      "Roles that need me on site outside Zurich, Basel or remote Europe.",
    ]);
});

test("languages, the hidden new jobs and the no-reply period", async ({
  page,
}) => {
  const languages = page.getByRole("group", { name: "Languages I speak" });
  await expect(languages.getByText("English", { exact: true })).toBeVisible();
  await expect(languages.getByText("Italian", { exact: true })).toBeVisible();
  // The switch-like link is the Jobs filter, with what it would hide now.
  const report = await call(
    page,
    "/jobs?triage=new&limit=1&hide_unspoken_required=false",
  );
  const filter = languages.getByRole("link", {
    name: /Hide new jobs that require another language/,
  });
  await expect(filter).toHaveAttribute("href", "#jobs?hide_unspoken=true");
  await expect(filter).toContainText(
    `would hide ${report.unspoken_required.count} of the ${report.total} new jobs`,
  );

  await languages.getByRole("button", { name: "Edit languages" }).click();
  await languages.getByRole("button", { name: "Remove Italian" }).click();
  await expect
    .poll(
      async () => (await call(page, "/preferences")).settings.spoken_languages,
    )
    .toEqual(["en"]);
  await languages.getByLabel("Add a language").selectOption("de");
  await expect
    .poll(
      async () => (await call(page, "/preferences")).settings.spoken_languages,
    )
    .toEqual(["en", "de"]);
  await languages.getByRole("button", { name: "Done" }).click();
  await expect(languages.getByText("German", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /^No-reply period: 45 days/ }).click();
  const days = page.getByLabel("Count an application as no reply after");
  await days.fill("400");
  await days.press("Enter");
  await expect(
    page.getByText("Give a whole number of days from 1 to 365."),
  ).toBeVisible();
  await days.fill("30");
  await days.press("Enter");
  await expect(
    page.getByRole("button", { name: /^No-reply period: 30 days/ }),
  ).toBeVisible();
  expect((await call(page, "/preferences")).settings.no_reply_days).toBe(30);
});

test("a conflict keeps the draft; Keep editing saves it on the new version", async ({
  page,
}) => {
  const row = line(page, "Facts about me", "Available from February 2027.");
  await row.focus();
  await page.keyboard.press("Enter");
  await statement(page).fill("Available from March 2027.");
  // Another session changes the section meanwhile.
  const facts = (await call(page, "/preferences")).sections.find(
    (section: { section: string }) => section.section === "facts",
  );
  await call(page, "/preferences/facts", "PUT", {
    expected_version: facts.version,
    items: [...facts.items, { text: "Synthetic: added elsewhere." }],
  });
  await statement(page).press("Enter");
  await expect(page.getByText("Changed elsewhere")).toBeVisible();
  await expect(statement(page)).toHaveValue("Available from March 2027.");
  await page.getByRole("button", { name: "Keep editing" }).click();
  await statement(page).press("Enter");
  await expect
    .poll(() => texts(page, "facts"))
    .toEqual(
      expect.arrayContaining([
        "Available from March 2027.",
        "Synthetic: added elsewhere.",
      ]),
    );
  expect(await texts(page, "facts")).not.toContain(
    "Available from February 2027.",
  );
});

test("an empty section shows two examples; leaving a draft asks first", async ({
  page,
}) => {
  const section = (await call(page, "/preferences")).sections.find(
    (item: { section: string }) => item.section === "working_with_me",
  );
  await call(page, "/preferences/working_with_me", "PUT", {
    expected_version: section.version,
    items: [],
  });
  await page.reload();
  const examples = page.getByRole("list", {
    name: "Examples for Working with me",
  });
  await expect(examples.getByRole("listitem")).toHaveCount(2);
  await page.getByRole("button", { name: "Add to Working with me" }).click();
  await statement(page).fill(
    "Synthetic: ask before preparing anything in French.",
  );

  // A draft asks before the page changes.
  await page.goto("/#templates");
  const leave = page.getByRole("dialog", { name: "Discard unsaved changes?" });
  await expect(leave).toBeVisible();
  await leave.getByRole("button", { name: "Keep editing" }).click();
  await expect(statement(page)).toHaveValue(
    "Synthetic: ask before preparing anything in French.",
  );
  await statement(page).press("Enter");
  await statement(page).press("Escape");
  await expect(examples).toHaveCount(0);
  await expect
    .poll(() => texts(page, "working_with_me"))
    .toEqual(["Synthetic: ask before preparing anything in French."]);
});
