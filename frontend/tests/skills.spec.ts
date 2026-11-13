import { test, expect, type Page } from "./fixtures";
import {
  call,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  type Cookies,
} from "./session";

// Settings, Skills: the text and reference files of each served skill, and
// its local notes, which are added after the shipped text whenever an agent
// reads the skill. The four projects share one server, so each test reads the
// current version of the notes it changes and writes text of its own.
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

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const toast = (page: Page, text: string) =>
  expect(page.locator(".toast").last()).toContainText(text);
// WebKit on macOS moves focus to buttons with Alt+Tab.
const tabKey = (page: Page) =>
  page.context().browser()?.browserType().name() === "webkit"
    ? "Alt+Tab"
    : "Tab";
const notes = (page: Page) =>
  page.getByRole("textbox", { name: /^Local notes for / });

/** A tools/call or prompts/get over MCP with an API token, as an agent sends it. */
async function mcp(
  page: Page,
  token: string,
  method: string,
  params: Record<string, unknown>,
) {
  return page.evaluate(
    async ({ token, method, params }) => {
      const response = await fetch("/mcp/", {
        method: "POST",
        credentials: "omit",
        headers: {
          "X-Openings-E2E-Setup": "1",
          "Content-Type": "application/json",
          Accept: "application/json, text/event-stream",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      });
      const value = await response.json();
      if (!response.ok || value.error) throw Error(JSON.stringify(value));
      return value.result;
    },
    { token, method, params },
  );
}
async function agentToken(page: Page) {
  return (await call(page, "/tokens", "POST", {
    name: unique("Skill reader"),
    kind: "agent",
  })) as { id: string; token: string };
}
/** On a narrow screen the list and the open skill are shown one at a time. */
async function showSkill(page: Page) {
  if (isNarrow(page))
    await expect(
      page
        .getByRole("group", { name: "Shown pane" })
        .getByRole("button")
        .last(),
    ).toHaveAttribute("aria-pressed", "true");
}

test("a local note added in the dashboard appears in the skill an agent reads over MCP", async ({
  page,
}) => {
  const skill = "track-applications";
  const text = unique("Follow up after ten working days, not seven.");
  await go(page, `settings?section=skills&skill=${skill}`);
  await showSkill(page);
  const panel = page.locator("section.skill");
  await expect(panel.getByRole("heading", { level: 2 })).toHaveText(skill);
  await expect(panel.locator("pre.skill-text")).toContainText(
    "# Track applications",
  );
  await notes(page).fill(text);
  await expect(
    panel.getByText(`${text.length} of 2000 characters`),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Save notes", exact: true }).click();
  await toast(page, "Local notes saved");
  const saved = await call(page, `/skills/${skill}/notes`);
  expect(saved.text).toBe(text);
  await expect(panel).toContainText(`Version ${saved.version}`);
  await expect(
    panel.getByRole("button", { name: "Save notes" }),
  ).toBeDisabled();

  // The agent reads the skill with its notes after the shipped text, alike
  // over MCP (tool and prompt) and REST; the shipped text is unchanged.
  const agent = await agentToken(page);
  const tool = await mcp(page, agent.token, "tools/call", {
    name: "skills_get",
    arguments: { name: skill },
  });
  const served = (tool.structuredContent || JSON.parse(tool.content[0].text))
    .content as string;
  const section = served.indexOf("## Local notes for this workspace");
  expect(section).toBeGreaterThan(0);
  expect(served.slice(section)).toContain(text);
  expect(served.slice(section)).toContain(`version ${saved.version}`);
  const rest = await call(
    page,
    `/skills/${skill}`,
    "GET",
    undefined,
    agent.token,
  );
  expect(rest.content).toBe(served);
  const prompt = await mcp(page, agent.token, "prompts/get", { name: skill });
  expect(prompt.messages[0].content.text).toContain(served);
  const shipped = await call(page, `/skills/${skill}?local_notes=false`);
  expect(shipped.content).not.toContain(text);
  expect(served.startsWith(shipped.content.trimEnd())).toBe(true);

  // The list marks the skill, and the change is attributed in the timeline.
  if (!isNarrow(page))
    await expect(
      page
        .getByRole("list", { name: "Skills" })
        .locator("li", { hasText: skill })
        .getByText("Local notes"),
    ).toHaveCount(1);
  await call(page, `/tokens/${agent.id}`, "DELETE");
  await fitsViewport(page);
});

test("earlier versions are kept and a conflict keeps the draft", async ({
  page,
}) => {
  const skill = "maintain-career";
  const first = unique("Keep project entries in reverse order.");
  let current = await call(page, `/skills/${skill}/notes`);
  current = await call(page, `/skills/${skill}/notes`, "PUT", {
    expected_version: current.version,
    text: first,
  });
  await go(page, `settings?section=skills&skill=${skill}`);
  const panel = page.locator("section.skill");
  await expect(notes(page)).toHaveValue(first);
  // An agent saves its own addition while the owner edits.
  const agent = await agentToken(page);
  const newer = `${first}\n\nAsk before merging two entries.`;
  await call(
    page,
    `/skills/${skill}/notes`,
    "PUT",
    { expected_version: current.version, text: newer },
    agent.token,
  );
  await notes(page).fill(`${first} My draft.`);
  await panel.getByRole("button", { name: "Save notes", exact: true }).click();
  const recovery = panel.locator(".conflict-recovery");
  await expect(recovery).toContainText(
    "This record changed in another session",
  );
  await expect(notes(page)).toHaveValue(`${first} My draft.`);
  await recovery
    .getByRole("button", { name: "Review latest values", exact: true })
    .click();
  await expect(recovery).toContainText("Ask before merging two entries.");
  await recovery
    .getByRole("button", { name: "Reload editor and discard draft" })
    .click();
  await expect(notes(page)).toHaveValue(newer);
  // The agent's version names the agent; the owner's earlier one is kept.
  await expect(panel).toContainText(`Version ${current.version + 1}`);
  await panel.getByRole("button", { name: /^Earlier versions/ }).click();
  const versions = panel.getByRole("list", { name: "Earlier versions" });
  const earlier = versions.locator("li", {
    hasText: new RegExp(`Version ${current.version}(?!\\d)`),
  });
  await expect(earlier).toContainText(first);
  await earlier.getByRole("button", { name: "Use this text" }).click();
  await expect(notes(page)).toHaveValue(first);
  await panel.getByRole("button", { name: "Save notes", exact: true }).click();
  await toast(page, "Local notes saved");
  await expect
    .poll(async () => (await call(page, `/skills/${skill}/notes`)).version)
    .toBe(current.version + 2);
  await call(page, `/tokens/${agent.id}`, "DELETE");
});

test("a reference file is read in place and a run's method is offered as a note", async ({
  page,
}) => {
  await go(page, "settings?section=skills&skill=review-inbox");
  const panel = page.locator("section.skill");
  const files = panel.getByRole("list", { name: "Reference files" });
  await files
    .getByRole("button", {
      name: "Read openings-workspace/references/operating-mandate.md",
    })
    .click();
  const dialog = page.locator("dialog[open]");
  await expect(dialog.getByRole("heading", { level: 2 })).toHaveText(
    "openings-workspace/references/operating-mandate.md",
  );
  await expect(dialog.locator("pre")).toContainText("# Operating mandate");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);

  // The prepare-shortlist run of the synthetic workspace reported what its
  // workflow lacked; its report links to the skill's notes.
  const run = (
    await call(page, "/runs?workflow=prepare-shortlist&status=finished")
  ).items.find((item: { method: string }) => item.method);
  await go(page, `activity?section=runs&run=${run.id}`);
  const method = page.getByRole("region", { name: "Method", exact: true });
  await method
    .getByRole("link", { name: "Add to the local notes of prepare-shortlist" })
    .click();
  await expect(page).toHaveURL(
    /section=skills&skill=prepare-shortlist&from_run=/,
  );
  const banner = page.locator("section.skill .banner").first();
  await expect(banner).toContainText("forbids AI-written applications");
  const before = await notes(page).inputValue();
  await banner.getByRole("button", { name: "Add to the notes" }).click();
  await expect(notes(page)).toHaveValue(
    `${before.trimEnd()}\n\n${run.method}`.trim(),
  );
  await expect(page).not.toHaveURL(/from_run=/);
  // The same method is among the suggestions of recent runs.
  await expect(
    page.getByRole("region", { name: "Suggested by recent runs" }),
  ).toContainText(run.method);
});

test("keyboard only: reach Skills, open a skill and save its notes", async ({
  page,
}) => {
  const skill = "prepare-interview";
  const text = unique("Prepare three questions about the team.");
  await go(page, "settings");
  const tab = page.getByRole("tab", { name: "Agent access" });
  await tab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Skills" })).toBeFocused();
  await expect(page).toHaveURL(/#settings\?section=skills$/);
  const open = page
    .getByRole("list", { name: "Skills" })
    .getByRole("button", { name: skill, exact: true });
  await open.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.locator("section.skill").getByRole("heading", { level: 2 }),
  ).toBeFocused();
  await expect(page).toHaveURL(new RegExp(`skill=${skill}`));
  await notes(page).focus();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type(text);
  await page.keyboard.press(tabKey(page));
  await expect(page.getByRole("button", { name: "Save notes" })).toBeFocused();
  await page.keyboard.press("Enter");
  await toast(page, "Local notes saved");
  await expect
    .poll(async () => (await call(page, `/skills/${skill}/notes`)).text)
    .toBe(text);
});
