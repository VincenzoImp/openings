import { test, expect, type Page } from "./fixtures";
import {
  call,
  card,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  type Cookies,
} from "./session";

// Activity: the agent's questions, the owner's requests, runs with their
// reports, and the timeline of every change. Each dashboard path of the
// questions.*, requests.*, runs.* and events.* operations is exercised here.
// The four projects share one server, so each test makes its own records.
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
  await go(page, "activity");
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const dialog = (page: Page) => page.locator("dialog[open]").last();
const toast = (page: Page, text: string) =>
  expect(page.locator(".toast").last()).toContainText(text);
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".loading")).toHaveCount(0);
}
/** An agent token and a job for one test. */
async function setup(page: Page) {
  const agent = await call(page, "/tokens", "POST", {
    name: unique("Synthetic agent"),
    kind: "agent",
  });
  const job = await call(page, "/jobs", "POST", {
    title: unique("Hybrid role"),
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  const as = (path: string, method = "GET", body?: unknown) =>
    call(page, path, method, body, agent.token);
  return { agent, job, as };
}
/** On a narrow screen a run list and its report are shown one at a time. */
async function showPane(page: Page, pane: "Runs" | "Report") {
  if (isNarrow(page))
    await page
      .getByRole("group", { name: "Shown pane" })
      .getByRole("button", { name: pane, exact: true })
      .click();
}

test("questions are answered with a choice and a comment, corrected and withdrawn", async ({
  page,
}) => {
  const { agent, job, as } = await setup(page);
  const run = await as("/runs", "POST", { workflow: unique("review-inbox") });
  const hybrid = unique("Is a hybrid schedule acceptable?");
  const notice = unique("Which notice period applies?");
  const asked = await as("/questions", "POST", {
    question: hybrid,
    why: "The posting requires two office days each week.",
    subject_type: "job",
    subject_id: job.id,
    choices: ["Yes", "No"],
  });
  await as("/questions", "POST", { question: notice });
  const open = (await call(page, "/questions?state=open&limit=1")).total;
  await page.reload();
  await settled(page);
  await expect(
    page.getByRole("tab", { name: /^Questions/ }).locator(".count"),
  ).toHaveText(String(open));
  await expect(
    page
      .getByRole("navigation", { name: "Main" })
      .getByRole("link", { name: /^Activity/ }),
  ).toHaveAccessibleName(new RegExp(`${open} open questions`));

  const opened = card(page, "Open");
  const question = opened.getByRole("article", { name: hybrid });
  await expect(question).toContainText("two office days");
  await expect(question.locator(".actor")).toHaveText(
    `${agent.name} · ${run.workflow}`,
  );
  await expect(
    question.getByRole("link", { name: "Asked in this run" }),
  ).toHaveAttribute("href", `#activity?section=runs&run=${run.id}`);
  await fitsViewport(page);
  // The subject opens the job in Jobs; Back returns to the question.
  await question.getByRole("link", { name: /^Job: Hybrid role/ }).click();
  await expect(page).toHaveURL(new RegExp(`#jobs\\?job=${job.id}$`));
  await expect(page.locator("#job-title")).toHaveText(job.title);
  await page.goBack();
  await expect(page.locator(".main h1")).toHaveText("Activity");

  // A comment and a choice are sent together.
  await question.getByRole("button", { name: "Write an answer" }).click();
  await question
    .getByRole("textbox", { name: "Your answer" })
    .fill("Two days are fine.");
  await question.getByRole("button", { name: "Yes", exact: true }).click();
  await toast(page, "Answer saved.");
  await expect(question).toHaveCount(0);

  const answered = card(page, "Answered").getByRole("article", {
    name: hybrid,
  });
  await expect(answered.locator(".answered")).toHaveText(
    "Yes · Two days are fine.",
  );
  await expect(answered).toContainText("Owner (dashboard) answered");
  await expect(answered).toContainText(`asked by ${agent.name} in its run`);
  // The owner corrects the answer.
  await answered.getByRole("button", { name: "Change answer" }).click();
  const box = answered.getByRole("textbox", { name: "Your answer" });
  await expect(box).toHaveValue("Two days are fine.");
  await box.fill("Two days, never Mondays.");
  await answered.getByRole("button", { name: "Save answer" }).click();
  await toast(page, "Answer saved.");
  await expect(answered.locator(".answered")).toContainText(
    "Two days, never Mondays.",
  );
  const read = await as(
    "/questions?answered_since=" + encodeURIComponent(asked.created_at),
  );
  expect(read.items).toContainEqual(
    expect.objectContaining({
      id: asked.id,
      state: "answered",
      answer: "Two days, never Mondays.",
    }),
  );

  // Withdraw the other one: it moves to Withdrawn with who withdrew it.
  await opened
    .getByRole("article", { name: notice })
    .getByRole("button", { name: "Withdraw" })
    .click();
  await toast(page, "Question withdrawn.");
  await expect(
    card(page, "Withdrawn").getByRole("article", { name: notice }),
  ).toContainText("Owner (dashboard) withdrew it");
  await fitsViewport(page);

  // A link of an earlier version opens the answered list.
  await go(page, "activity?state=answered");
  await expect(
    card(page, "Answered").getByRole("article", { name: hybrid }),
  ).toBeInViewport();
  await call(page, "/tokens/" + agent.id, "DELETE");
});

test("keyboard only: move through the Activity tabs and open a run's report", async ({
  page,
}) => {
  const { agent, job, as } = await setup(page);
  const workflow = unique("review-inbox");
  const run = await as("/runs", "POST", {
    workflow,
    scope: "One synthetic Inbox job.",
  });
  await as(`/jobs/${job.id}/notes`, "POST", { body: "Synthetic agent note." });
  const asked = unique("Which notice period applies?");
  await as("/questions", "POST", {
    question: asked,
    subject_type: "job",
    subject_id: job.id,
  });
  await as(`/runs/${run.id}/finish`, "POST", {
    expected_version: run.version,
    summary: "Reviewed one synthetic job.",
    changes: "Added one note and asked one question.",
    not_done: [
      {
        item: "Shortlist decision",
        reason: "Waiting for the notice period.",
        subject_type: "job",
        subject_id: job.id,
      },
    ],
    checks: [
      { check: "Inbox query re-read" },
      { check: "PDF render", verified: false },
    ],
    limits: "No application was submitted.",
    method: "A salary filter is missing.",
  });
  await page.reload();
  await settled(page);

  // Arrow keys move through the tabs; each tab has its address.
  await page.getByRole("tab", { name: /^Questions/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Requests" })).toBeFocused();
  await expect(page).toHaveURL(/#activity\?section=requests$/);
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Timeline" })).toBeFocused();
  await expect(page).toHaveURL(/#activity\?section=timeline$/);
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "Runs" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page).toHaveURL(/#activity\?section=runs$/);

  // Open the run from the list with Enter: the report takes focus.
  const row = page.getByRole("listitem").filter({
    has: page.getByRole("button", { name: workflow, exact: true }),
  });
  await expect(row.locator(".tag")).toHaveText("Finished");
  await expect(row).toContainText("1 note, 1 question asked");
  await expect(row.locator(".actor")).toHaveText(agent.name);
  await row.getByRole("button", { name: workflow }).focus();
  await page.keyboard.press("Enter");
  const report = page.locator("article.report");
  const heading = report.getByRole("heading", { name: workflow, exact: true });
  await expect(heading).toBeFocused();
  await expect(page).toHaveURL(
    new RegExp(`#activity\\?section=runs&run=${run.id}$`),
  );
  // On a phone the report replaces the list; the list marks the open run.
  if (!isNarrow(page))
    await expect(row).toHaveAttribute("aria-current", "true");
  for (const [title, content] of [
    ["Scope", "One synthetic Inbox job."],
    ["Summary", "Reviewed one synthetic job."],
    ["Changes", "Added one note and asked one question."],
    ["Not done", "Waiting for the notice period."],
    ["Checks", "Not verified"],
    ["Limits", "No application was submitted."],
    ["Method", "A salary filter is missing."],
    ["Questions for you", asked],
    ["Requests handled", "This run handled no requests."],
  ])
    await expect(
      report.getByRole("region", { name: title, exact: true }),
    ).toContainText(content);
  const changes = report.getByRole("region", { name: "Changes", exact: true });
  await expect(changes.locator("dt")).toHaveText(["1", "1"]);
  await expect(changes.locator("dd").first()).toHaveText(
    `note: ${job.title} · Example Labs`,
  );
  await fitsViewport(page);

  // The changes of the run in the timeline, with who made them.
  await changes
    .getByRole("link", { name: "All 2 changes in the timeline" })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(
    new RegExp(`#activity\\?section=timeline&run=${run.id}$`),
  );
  await expect(
    page.getByRole("button", { name: `Run: ${workflow}, remove this filter` }),
  ).toBeVisible();
  const entries = page
    .locator("main li")
    .filter({ has: page.locator(".actor") });
  await expect(entries).toHaveCount(2);
  await expect(entries.first()).toContainText("Question asked");
  await expect(entries.last()).toContainText("Note added");
  await expect(entries.last().locator(".actor")).toHaveText(
    `${agent.name} · ${workflow}`,
  );
  // A change links to the record it touched.
  await entries
    .last()
    .getByRole("link", { name: /^Note: Hybrid role/ })
    .click();
  await expect(page.locator("#job-title")).toHaveText(job.title);
  await expect(
    page.getByRole("list", { name: "Timeline of this job" }),
  ).toContainText("Note");

  // An interrupted run says why it has no report and keeps its changes.
  await go(page, "activity?section=runs");
  await page
    .getByRole("group", { name: "Status" })
    .getByRole("button", { name: "Interrupted" })
    .click();
  const interrupted = page.getByRole("listitem").filter({
    has: page.getByRole("button", { name: "maintain-career", exact: true }),
  });
  await expect(interrupted.locator(".tag")).toHaveText("Interrupted");
  await expect(interrupted).toContainText("8 min · The Career record");
  await interrupted.getByRole("button", { name: "maintain-career" }).click();
  await expect(report.locator(".banner")).toContainText(
    "started another run before closing this one",
  );
  await expect(report).toContainText("This run ended without a report.");
  await expect(report.locator(".counts dt")).toHaveText(["2"]);
  await showPane(page, "Runs");
  await fitsViewport(page);
  // Leave no open question behind: Today lists the newest ones.
  const [left] = (await call(page, `/questions?state=open&run_id=${run.id}`))
    .items;
  await call(page, `/questions/${left.id}/withdraw`, "POST", {
    expected_version: left.version,
  });
  await call(page, "/tokens/" + agent.id, "DELETE");
});

test("the timeline filters by who, kind, period and run, page by page", async ({
  page,
}) => {
  // The name the timeline had before it was rebuilt still opens it.
  await go(page, "activity?section=changes");
  await expect(page.getByRole("tab", { name: "Timeline" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await settled(page);
  const total = (await call(page, "/events?limit=1")).total;
  const pages = page.getByRole("navigation", { name: "Change pages" });
  await expect(pages).toContainText(`1–30 of ${total}`);
  await pages.getByRole("button", { name: "Next" }).click();
  await expect(pages).toContainText(`31–60 of ${total}`);
  await expect(page).toHaveURL(/offset=30/);

  // A kind of change starts again at the first page.
  await page.getByLabel("Kind of change").selectOption("notes");
  await expect(page).not.toHaveURL(/offset=30/);
  await settled(page);
  const notes = page.locator("main li").filter({ has: page.locator(".actor") });
  await expect(notes.first()).toBeVisible();
  for (const tag of await notes.locator(".tag").allTextContents())
    expect(tag).toBe("Notes");

  // Who: the agent's token.
  await page
    .getByRole("group", { name: "Made by" })
    .getByRole("button", { name: "API tokens" })
    .click();
  const tokens = await call(page, "/tokens");
  const careerAgent = tokens.items.find(
    (item: any) => item.name === "career-agent",
  );
  await page.getByLabel("API token").selectOption(careerAgent.id);
  await settled(page);
  const expected = await call(
    page,
    `/events?subject_types=note&actor=token&token_id=${careerAgent.id}&limit=30`,
  );
  await expect(notes).toHaveCount(expected.items.length);
  for (const actor of await notes.locator(".actor").allTextContents())
    expect(actor).toMatch(/^career-agent/);

  // A period without changes, and the way back.
  const tomorrow = new Date(Date.now() + 2 * 86_400_000)
    .toISOString()
    .slice(0, 10);
  await page.getByLabel("From").fill(tomorrow);
  await expect(
    page.getByRole("heading", { name: "No changes match these filters" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page).toHaveURL(/#activity\?section=changes$/);
  await expect(pages).toContainText(`of ${total}`);
  await fitsViewport(page);
});

test("the owner writes requests, follows the agent's result and withdraws one", async ({
  page,
}) => {
  const { agent, job, as } = await setup(page);
  await page.getByRole("tab", { name: "Requests" }).click();
  await expect(page).toHaveURL(/#activity\?section=requests$/);

  // A general request, written and sent with the keyboard.
  const general = unique("Stop preparing consultancy roles");
  const field = page.getByRole("textbox", {
    name: "What should your agent do?",
  });
  await field.focus();
  await page.keyboard.type(general);
  await page.getByRole("button", { name: "Send request" }).focus();
  await page.keyboard.press("Enter");
  await toast(page, "Request saved.");
  const waiting = page.getByRole("article", { name: general });
  await expect(waiting.locator(".tag")).toHaveText("Waiting for your agent");
  await expect(waiting).toContainText("Owner (dashboard) wrote it");
  await expect(field).toHaveValue("");

  // A request about one job, found by its title.
  const about = unique("Prepare this one too");
  await field.fill(about);
  await page.getByLabel("About").selectOption("job");
  await expect(
    page.getByRole("button", { name: "Send request" }),
  ).toBeDisabled();
  await page.getByLabel("Find the job").fill(job.title);
  await page
    .getByRole("list", { name: "Matching records" })
    .getByRole("button", { name: `${job.title} · Example Labs` })
    .click();
  await page.getByRole("button", { name: "Send request" }).click();
  await toast(page, "Request saved.");
  const pending = page.getByRole("article", { name: about });
  await expect(
    pending.getByRole("link", { name: `Job: ${job.title} · Example Labs` }),
  ).toBeVisible();
  await fitsViewport(page);

  // The job's own "Ask your agent" lists the request about it and writes
  // another one about the job.
  await go(page, `jobs?section=all&job=${job.id}`);
  const detail = page.locator(".job-detail");
  await detail.locator("summary", { hasText: "Ask your agent" }).click();
  await expect(detail.getByRole("article", { name: about })).toBeVisible();
  const later = unique("Check the salary range");
  await detail.getByLabel("A request about this job").fill(later);
  await detail
    .getByRole("button", { name: "Send the request", exact: true })
    .click();
  await expect(
    detail.getByRole("article", { name: later }).locator(".tag"),
  ).toHaveText("Waiting for your agent");

  // The agent takes it in a run and reports the result.
  const run = await as("/runs", "POST", {
    workflow: unique("prepare-shortlist"),
  });
  const open = (
    await as(`/requests?state=open&subject_type=job&subject_id=${job.id}`)
  ).items.find((item: any) => item.text === about);
  const taken = await as(`/requests/${open.id}/take`, "POST", {
    expected_version: open.version,
  });
  await as(`/requests/${taken.id}/complete`, "POST", {
    expected_version: taken.version,
    result: "Draft prepared and marked ready.",
  });
  await go(page, "activity?section=requests");
  await page
    .getByRole("group", { name: "State" })
    .getByRole("button", { name: "Done" })
    .click();
  await expect(page).toHaveURL(/state=done/);
  const done = page.getByRole("article", { name: about });
  await expect(done.locator(".tag")).toHaveText("Done");
  await expect(done.locator(".answered")).toHaveText(
    "Draft prepared and marked ready.",
  );
  await expect(done).toContainText(`completed by ${agent.name}`);
  await done.getByRole("link", { name: `${run.workflow} run` }).click();
  await showPane(page, "Report");
  await expect(
    page
      .locator("article.report")
      .getByRole("region", { name: "Requests handled" }),
  ).toContainText(about);

  // The owner withdraws the request nobody took.
  await go(page, "activity?section=requests&state=open");
  await page
    .getByRole("article", { name: general })
    .getByRole("button", { name: "Withdraw" })
    .click();
  await toast(page, "Request withdrawn.");
  await expect(page.getByRole("article", { name: general })).toHaveCount(0);
  await page
    .getByRole("group", { name: "State" })
    .getByRole("button", { name: "Withdrawn" })
    .click();
  await expect(page.getByRole("article", { name: general })).toContainText(
    "withdrawn by Owner (dashboard)",
  );
  await call(page, "/tokens/" + agent.id, "DELETE");
});
