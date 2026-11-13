import { test, expect, type Page } from "@playwright/test";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// The Library screens built with the design system: Policy, Career and
// Templates. Every dashboard path of their operations is exercised here; the
// four projects share one server, so each test names its own records.
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
      const setup = { "X-Openings-E2E-Setup": "1" };
      const session = await fetch("/api/v1/auth/session", {
        headers: setup,
      }).then((response) => response.json());
      const response = await fetch("/api/v1" + path, {
        method,
        credentials: token ? "omit" : "same-origin",
        headers: {
          ...setup,
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
const policyItem = async (page: Page, section: string, label: string) =>
  (await call(page, `/policy/${section}`)).items.find(
    (item: any) => item.label === label,
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

test("policy items are added, edited, confirmed, switched, moved, reordered and removed", async ({
  page,
}) => {
  const label = unique("Languages");
  await go(page, "policy");
  const facts = sectionCard(page, "Facts");
  await facts.getByRole("button", { name: "Add a fact" }).click();
  const form = facts.getByRole("form", { name: "New fact" });
  await form.getByLabel("Label").fill(label);
  await form.getByLabel("Statement").fill("Spoken at work.");
  await form.getByLabel("Kind of value").selectOption("list");
  await form.getByLabel("Value", { exact: true }).fill("English, Italian");
  await form.getByRole("button", { name: "Add a fact" }).click();
  const row = facts.locator("li").filter({ hasText: label });
  await expect(row).toContainText("English · Italian");
  await expect(row).toContainText("Confirmed");
  await expect(row.locator(".actor")).toHaveClass(/owner/);
  // REST returns the item the dashboard shows.
  const stored = await policyItem(page, "facts", label);
  expect([stored.value, stored.value_type, stored.confirmed]).toEqual([
    ["English", "Italian"],
    "list",
    true,
  ]);

  await row.getByRole("button", { name: `Edit ${label}` }).click();
  const edit = facts.getByRole("form", { name: `Edit the fact ${label}` });
  await edit.getByLabel("Statement").fill("Spoken and written at work.");
  await edit.getByLabel("Note").fill("Checked in the test.");
  await edit.getByRole("button", { name: "Save fact" }).click();
  await expect(row).toContainText("Spoken and written at work.");
  await expect(row).toContainText("Note: Checked in the test.");

  // It moves up from the keyboard-operable buttons, one place at a time.
  const before = (await call(page, "/policy/facts")).items.map(
    (item: any) => item.label,
  );
  await row.getByRole("button", { name: `Move ${label} up` }).click();
  await saved(page, "Order saved.");
  const after = (await call(page, "/policy/facts")).items.map(
    (item: any) => item.label,
  );
  expect(after.indexOf(label)).toBe(before.indexOf(label) - 1);

  // An agent proposes a rule on a signal and a fact; only the owner confirms.
  const agent = await call(page, "/tokens", "POST", {
    name: unique("Policy agent"),
    kind: "agent",
  });
  const rule = unique("No longer listed");
  const proposal = unique("Relocation");
  const decision = await call(page, "/policy/decision");
  await call(
    page,
    "/policy/decision/items",
    "POST",
    {
      expected_version: decision.version,
      label: rule,
      statement: "Dismiss jobs whose source stops listing them.",
      rule: {
        signal: "no_longer_listed",
        condition: { operator: "is", value: true },
        action: "dismiss",
      },
    },
    agent.token,
  );
  await call(
    page,
    "/policy/facts/items",
    "POST",
    {
      expected_version: (await call(page, "/policy/facts")).version,
      label: proposal,
      statement: "No relocation outside Switzerland.",
    },
    agent.token,
  );
  await page.reload();
  const ruleRow = sectionCard(page, "Decision")
    .locator("li")
    .filter({ hasText: rule });
  await expect(ruleRow).toContainText("Proposed");
  await expect(ruleRow).toContainText("Uses a signal: no longer listed");
  await expect(ruleRow).toContainText("Signals arrive in a later release");
  await expect(ruleRow.locator(".actor")).toHaveClass(/agent/);
  const toggle = ruleRow.getByRole("switch");
  await expect(toggle).not.toBeChecked();
  await ruleRow.getByRole("button", { name: `Confirm: ${rule}` }).click();
  await expect(ruleRow).toContainText("Confirmed");
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(ruleRow).toContainText("Applied automatically: on");
  const enabled = await policyItem(page, "decision", rule);
  expect([enabled.enabled, enabled.confirmed]).toEqual([true, true]);
  expect(enabled.confirmed_by.kind).toBe("owner");

  // A proposed fact is sorted into another section, then confirmed there.
  const proposed = page
    .locator("section.card li")
    .filter({ hasText: proposal });
  await proposed
    .getByLabel(`Move ${proposal} to a section`)
    .selectOption("eligibility");
  const moved = sectionCard(page, "Eligibility")
    .locator("li")
    .filter({ hasText: proposal });
  await expect(moved).toBeVisible();
  await moved
    .getByRole("button", { name: `Confirm as a fact: ${proposal}` })
    .click();
  await expect(moved).toContainText("Confirmed");
  expect((await policyItem(page, "eligibility", proposal)).confirmed).toBe(
    true,
  );

  // Removal asks first and names the item.
  for (const [section, name, noun] of [
    ["Facts", label, "fact"],
    ["Decision", rule, "rule"],
    ["Eligibility", proposal, "fact"],
  ]) {
    await sectionCard(page, section)
      .getByRole("button", { name: `Remove ${name}` })
      .click();
    await expect(dialog(page)).toContainText(name);
    await dialog(page)
      .getByRole("button", { name: `Remove ${noun}`, exact: true })
      .click();
    await expect(
      sectionCard(page, section).locator("li").filter({ hasText: name }),
    ).toHaveCount(0);
  }
  expect(await policyItem(page, "facts", label)).toBeUndefined();
});

test("keyboard only: a policy item is edited, saved and moved", async ({
  page,
}) => {
  const label = unique("Notice");
  const writing = await call(page, "/policy/writing");
  await call(page, "/policy/writing/items", "POST", {
    expected_version: writing.version,
    label,
    statement: "One month.",
  });
  await go(page, "policy");
  const section = sectionCard(page, "Writing");
  await section.getByRole("button", { name: `Edit ${label}` }).focus();
  await page.keyboard.press("Enter");
  // The form opens with focus in its first field.
  const form = section.getByRole("form", { name: `Edit the rule ${label}` });
  await expect(form.getByLabel("Label")).toBeFocused();
  // Safari reaches every control with Option+Tab; the other browsers with Tab.
  const tab =
    page.context().browser()?.browserType().name() === "webkit"
      ? "Alt+Tab"
      : "Tab";
  await page.keyboard.press(tab);
  await expect(form.getByLabel("Applies to")).toBeFocused();
  await page.keyboard.press(tab);
  await expect(form.getByLabel("Statement")).toBeFocused();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("Two months to the end of a month.");
  // Enter in a single-line field saves the form.
  await page.keyboard.press("Shift+" + tab);
  await page.keyboard.press("Shift+" + tab);
  await expect(form.getByLabel("Label")).toBeFocused();
  await page.keyboard.press("Enter");
  const row = section.locator("li").filter({ hasText: label });
  await expect(row).toContainText("Two months to the end of a month.");
  await expect(row.locator(".tag")).toHaveText("All documents");
  const stored = await policyItem(page, "writing", label);
  expect([stored.statement, stored.scope]).toEqual([
    "Two months to the end of a month.",
    "all",
  ]);

  // Reordering keeps focus on the button that was pressed.
  const up = row.getByRole("button", { name: `Move ${label} up` });
  await up.focus();
  await page.keyboard.press("Enter");
  await saved(page, "Order saved.");
  await expect(up).toBeFocused();
  const order = (await call(page, "/policy/writing")).items.map(
    (item: any) => item.label,
  );
  expect(order.indexOf(label)).toBe(order.length - 2);

  // Escape leaves the confirmation; Enter on its button removes the item.
  await row.getByRole("button", { name: `Remove ${label}` }).focus();
  await page.keyboard.press("Enter");
  await expect(dialog(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await row.getByRole("button", { name: `Remove ${label}` }).focus();
  await page.keyboard.press("Enter");
  await dialog(page).getByRole("button", { name: "Remove rule" }).focus();
  await page.keyboard.press("Enter");
  await expect(row).toHaveCount(0);
});

test("a policy conflict reloads the section and keeps the unsaved text", async ({
  page,
}) => {
  const label = unique("Salary");
  const other = unique("Elsewhere");
  const facts = await call(page, "/policy/facts");
  const created = await call(page, "/policy/facts/items", "POST", {
    expected_version: facts.version,
    label,
    statement: "Expected salary.",
  });
  await go(page, "policy");
  const section = sectionCard(page, "Facts");
  await section.getByRole("button", { name: `Edit ${label}` }).click();
  const form = section.getByRole("form", { name: `Edit the fact ${label}` });
  await form.getByLabel("Statement").fill("My unsaved statement.");
  // Another session adds an item: the section has a newer version.
  const added = await call(page, "/policy/facts/items", "POST", {
    expected_version: created.section.version,
    label: other,
  });
  await form.getByRole("button", { name: "Save fact" }).click();
  await expect(form.getByRole("alert")).toContainText(
    "changed in another session. Your text is kept",
  );
  await expect(form.getByLabel("Statement")).toHaveValue(
    "My unsaved statement.",
  );
  // The latest list is shown beside the form, and saving again succeeds.
  await expect(section.locator("li").filter({ hasText: other })).toBeVisible();
  await form.getByRole("button", { name: "Save fact" }).click();
  await expect(
    section.locator("li").filter({ hasText: "My unsaved statement." }),
  ).toBeVisible();
  // A button pressed on a stale section says so and shows the latest state.
  const current = await call(page, "/policy/facts");
  await call(
    page,
    `/policy/items/${added.item.id}?expected_version=${current.version}`,
    "DELETE",
  );
  await section.getByRole("button", { name: `Remove ${label}` }).click();
  await dialog(page).getByRole("button", { name: "Remove fact" }).click();
  await expect(page.locator(".toast.error").last()).toContainText(
    "changed in another session",
  );
  await expect(section.locator("li").filter({ hasText: other })).toHaveCount(0);
  await section.getByRole("button", { name: `Remove ${label}` }).click();
  await dialog(page).getByRole("button", { name: "Remove fact" }).click();
  await expect(section.locator("li").filter({ hasText: label })).toHaveCount(0);
});

test("the profile is saved with typed fields and free-form details edited as rows", async ({
  page,
}, info) => {
  const headline = unique("Engineer");
  const key = `badge_${info.project.name.replace("-", "_")}`;
  await go(page, "career");
  const profile = page.getByRole("form", { name: "Profile" });
  await profile.getByLabel("Headline").fill(headline);
  await profile
    .getByText("Target roles and preferences, kept from earlier versions")
    .click();
  await profile.getByLabel("Target roles").fill("Data engineer");
  const details = profile.getByRole("group", {
    name: "Other profile details as keys and values",
  });
  // No JSON text box anywhere.
  await expect(page.locator("textarea[name=metadata]")).toHaveCount(0);
  if (!(await details.getByLabel(`Type of ${key}`).count())) {
    await details.getByRole("button", { name: "Add a detail" }).click();
    await details.getByLabel("Key", { exact: true }).last().fill(key);
  }
  await details.getByLabel(`Type of ${key}`).selectOption("number");
  await details.getByLabel(`Value of ${key}`).fill("42");
  // A nested value is read-only until it is opened as fields, one level down.
  const nested = details.locator(".kv-row").filter({
    has: page.locator('input[value="interview_availability"]'),
  });
  await expect(nested.locator("summary")).toHaveText("3 fields");
  await nested.getByRole("button", { name: "Edit as fields" }).click();
  const fields = details.getByRole("group", {
    name: "Fields of interview_availability",
  });
  const hour = `${10 + (Date.now() % 9)}:00`;
  await fields.getByLabel("Value of from").fill(hour);
  await expect(fields.getByLabel("Type of days")).toHaveValue("list");
  await profile.getByRole("button", { name: "Save profile" }).click();
  await saved(page, "Profile saved.");
  const stored = await call(page, "/career/profile");
  expect(stored.headline).toBe(headline);
  expect(stored.roles).toBe("Data engineer");
  expect(stored.metadata[key]).toBe(42);
  expect(stored.metadata.interview_availability).toEqual({
    days: ["Tue", "Thu"],
    from: hour,
    timezone: "Europe/Zurich",
  });
  // A key used twice is refused before anything is sent.
  await details.getByRole("button", { name: "Add a detail" }).click();
  await details.getByLabel("Key", { exact: true }).last().fill(key);
  await expect(details.getByRole("status")).toContainText("is used twice");
  await profile.getByRole("button", { name: "Save profile" }).click();
  await expect(page.locator(".toast.error").last()).toContainText(
    "is used twice",
  );
  page.once("dialog", (confirm) => confirm.accept());
  await page.reload();
});

test("a career entry with claims, typed selection, files and import is managed end to end", async ({
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
  const other = editor.getByRole("group", {
    name: "Other details of the entry as keys and values",
  });
  await other.getByRole("button", { name: "Add a detail" }).click();
  await other.getByLabel("Key", { exact: true }).fill("team_size");
  await other.getByLabel("Type of team_size").selectOption("number");
  await other.getByLabel("Value of team_size").fill("6");
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
    await call(page, `/career/knowledge?q=${encodeURIComponent(title)}`)
  ).items[0];
  expect([entry.skills, entry.metadata, entry.dates.start]).toEqual([
    ["Rust", "Go", "SQL"],
    { team_size: 6 },
    "2020-03",
  ]);

  // A claim: added as a draft, approved, then selected with typed controls.
  const text = `Cut storage cost by a third (${Date.now()}).`;
  await editor.getByRole("button", { name: "Add a claim" }).click();
  await dialog(page).getByLabel("Claim", { exact: true }).fill(text);
  await dialog(page).getByRole("button", { name: "Save claim" }).click();
  const claim = editor.locator(".claim").filter({ hasText: text });
  await expect(claim).toContainText("Not approved by you");
  await expect(claim.getByRole("switch")).toBeDisabled();
  await claim.getByRole("button", { name: /^Approve: / }).click();
  await expect(claim.locator(".tag")).toHaveText("Approved");
  await claim.getByRole("switch").click();
  await expect(claim.getByRole("switch")).toBeChecked();
  await claim.getByLabel(/^Role of: /).selectOption("core");
  await saved(page, "Role saved.");
  await claim.getByLabel(/^Group of: /).fill("Impact");
  await page.keyboard.press("Enter");
  await saved(page, "Group saved.");
  const read = async () =>
    (await call(page, `/career/claims?knowledge_id=${entry.id}`)).items[0];
  let stored = await read();
  expect([
    stored.approved,
    stored.default_in_cv,
    stored.role,
    stored.group,
  ]).toEqual([true, true, "core", "Impact"]);
  await show(page, "Record");
  await expect(item).toContainText("1 claim");
  await show(page, "Selected entry");

  // The full editor of a claim: wording, role, order and free-form details.
  await claim.getByRole("button", { name: /^Edit claim: / }).click();
  await dialog(page)
    .getByLabel("Claim", { exact: true })
    .fill(text + " Twice.");
  await dialog(page).getByLabel("Role").selectOption("bench");
  await dialog(page).getByLabel("Order").fill("3");
  await dialog(page).getByRole("button", { name: "Add a detail" }).click();
  await dialog(page).getByLabel("Key", { exact: true }).fill("source");
  await dialog(page).getByLabel("Value of source").fill("Synthetic review");
  await dialog(page).getByRole("button", { name: "Save claim" }).click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  stored = await read();
  expect([stored.text, stored.role, stored.position, stored.metadata]).toEqual([
    text + " Twice.",
    "bench",
    3,
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
  await found.getByRole("button", { name: /^Mark as draft: / }).click();
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
  await claim.getByRole("button", { name: /^Remove claim: / }).click();
  await dialog(page).getByRole("button", { name: "Remove claim" }).click();
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
    dialog(page).getByRole("link", { name: "cover-letter.tex" }),
  ).toHaveAttribute("href", "/api/v1/examples/cover-letter.tex");
  await dialog(page).getByLabel("Name").fill(name);
  await dialog(page)
    .getByLabel("Document", { exact: true })
    .selectOption("cover_letter");
  await dialog(page).getByLabel("LaTeX source").fill("\\documentclass{letter}");
  await dialog(page).getByRole("button", { name: "Add template" }).click();
  const detail = page.locator("section.detail");
  await expect(
    detail.getByRole("heading", { name, exact: true }),
  ).toBeVisible();
  const read = async () =>
    (await call(page, `/templates?q=${encodeURIComponent(name)}`)).items[0];

  // Source: the text is edited in place and saved with the version.
  await detail.getByLabel("LaTeX source").fill("\\documentclass{letter}\n% v2");
  await detail.getByRole("button", { name: "Save source" }).click();
  await saved(page, "Source saved.");
  expect((await read()).tex).toBe("\\documentclass{letter}\n% v2");

  // Rules: limits, rule statements in order, and the free-form rest as rows.
  await detail.getByRole("tab", { name: "Rules" }).click();
  await expect(page.locator("textarea[name=rules]")).toHaveCount(0);
  await detail
    .getByLabel("Guidance for this template")
    .fill("Three paragraphs.");
  await detail.getByLabel("Pages").fill("1");
  for (const [label, rule] of [
    ["Opening", "Name the role first."],
    ["Closing", "End with availability."],
  ]) {
    await detail.getByRole("button", { name: "Add a rule" }).click();
    const group = detail.getByRole("group", { name: "Rule", exact: true });
    await group.getByLabel("Label").fill(label);
    await group.getByLabel("Rule").fill(rule);
    await detail.getByRole("button", { name: "Done", exact: true }).click();
  }
  await detail.getByRole("button", { name: "Move Closing up" }).click();
  const settings = detail.getByRole("group", {
    name: "Other settings as keys and values",
  });
  await settings.getByRole("button", { name: "Add a setting" }).click();
  await settings.getByLabel("Key", { exact: true }).fill("engine");
  await settings.getByLabel("Value of engine").fill("lualatex");
  await detail.getByRole("button", { name: "Save rules" }).click();
  await saved(page, "Rules saved.");
  let stored = await read();
  expect(stored.guidance).toBe("Three paragraphs.");
  expect(stored.rules.max_pages).toBe(1);
  expect(stored.rules.engine).toBe("lualatex");
  expect(
    stored.rules.statements.map((rule: any) => [rule.label, rule.position]),
  ).toEqual([
    ["Closing", 0],
    ["Opening", 1],
  ]);
  // A saved statement is edited and another removed.
  await detail.getByRole("button", { name: "Edit Opening" }).click();
  await detail
    .getByRole("group", { name: "Edit Opening" })
    .getByLabel("Rule")
    .fill("Name the role and one result.");
  await detail.getByRole("button", { name: "Done", exact: true }).click();
  await detail.getByRole("button", { name: "Remove Closing" }).click();
  await detail.getByRole("button", { name: "Save rules" }).click();
  await saved(page, "Rules saved.");
  stored = await read();
  expect(stored.rules.statements.map((rule: any) => rule.statement)).toEqual([
    "Name the role and one result.",
  ]);

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

  // Name, kind and default; the general instructions; removal.
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
  await page.getByRole("button", { name: "General instructions" }).click();
  const general = `Use clear international English. ${Date.now()}`;
  await dialog(page)
    .getByLabel("Instructions for every document")
    .fill(general);
  await dialog(page).getByRole("button", { name: "Save instructions" }).click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  expect((await call(page, "/instructions")).general).toBe(general);
  await detail.getByRole("button", { name: "Delete", exact: true }).click();
  await dialog(page).getByRole("button", { name: "Remove template" }).click();
  await expect(
    page
      .getByRole("region", { name: "Templates by kind" })
      .getByRole("button", { name: name + " renamed" }),
  ).toHaveCount(0);
  expect(await read()).toBeUndefined();
});

test("links of earlier versions open the rebuilt screens", async ({ page }) => {
  const template = (await call(page, "/templates?summary=true&limit=2"))
    .items[1];
  await go(page, `templates?template=${template.id}&section=instructions`);
  await expect(
    page.getByRole("heading", { name: template.name, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Rules" })).toHaveAttribute(
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
  await go(page, "policy");
  await expect(
    page.getByRole("heading", { name: "Policy", level: 1 }),
  ).toBeVisible();
});
