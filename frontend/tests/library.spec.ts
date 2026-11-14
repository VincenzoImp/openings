import { test, expect, type Page } from "./fixtures";
import { go, isNarrow, ownerSession, type Cookies } from "./session";

// The Library screen built with the design system: Career (Preferences and
// Templates have their own specs). Every dashboard path of their operations is exercised here. Each
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

test("the profile is saved with typed fields and keeps its metadata", async ({
  page,
}) => {
  const headline = unique("Engineer");
  const before = await call(page, "/career/profile");
  await go(page, "profile");
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
  await go(page, "profile?section=knowledge");
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
    (await call(page, `/career/claims?summary=false&career_id=${entry.id}`))
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

test("links of earlier versions open the rebuilt screens", async ({ page }) => {
  await go(page, "profile?section=claims&q=claim 07");
  await expect(page.getByRole("tab", { name: "All claims" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.locator(".claims .claim")).toHaveCount(1);
  await go(page, "profile?section=knowledge&q=project 07");
  if (isNarrow(page))
    await page
      .getByRole("button", { name: /^Open Synthetic project 07/ })
      .click();
  await expect(
    page.getByRole("heading", { name: "Edit entry: Synthetic project 07" }),
  ).toBeVisible();
});
