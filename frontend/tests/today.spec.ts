import { test, expect, type Page } from "@playwright/test";
import {
  call,
  card,
  fitsViewport,
  go,
  isNarrow,
  ownerSession,
  type Cookies,
} from "./session";

// Today, the first screen, on the synthetic workspace of
// backend/tests/today_fixtures.py: ready applications with deadlines, a
// blocked one, sent applications of different ages, the agent's runs and
// questions, and collection runs. The four projects share one server, so a
// test that changes something makes its own records.
const cookies: Cookies = ownerSession();
const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  errors.set(page, []);
  page.on("pageerror", (error) => errors.get(page)!.push(error.message));
  await page.context().addCookies(cookies);
});
test.afterEach(async ({ page }) => {
  expect(errors.get(page)).toEqual([]);
});

const unique = (name: string) =>
  `${name} ${test.info().project.name} ${Date.now()}`;
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const plural = (count: number, one: string) =>
  `${count} ${count === 1 ? one : one + "s"}`;
/** The day before which a sent application has waited long (as Today computes it). */
const dayBefore = (days: number) =>
  new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".loading")).toHaveCount(0);
}
async function agent(page: Page, name: string) {
  return call(page, "/tokens", "POST", { name, kind: "agent" });
}

test("Today answers the owner's three questions with the workspace's own numbers", async ({
  page,
}) => {
  await go(page, "today");
  await expect(page).toHaveTitle("Today · Openings");
  await settled(page);
  const ready = await call(
    page,
    "/applications?readiness=ready&sort=deadline&limit=5",
  );
  const questions = await call(page, "/questions?state=open&limit=1");
  const blocked = await call(
    page,
    "/applications?readiness=blocked&status=draft&limit=1",
  );
  // The synthetic policy's "No reply" decision says 45 days; the server reads it.
  const waiting = await call(page, "/applications?no_reply_due=true&limit=1");
  expect(waiting.no_reply.days).toBe(45);
  expect(waiting.total).toBe(
    (
      await call(
        page,
        `/applications?status=applied&applied_until=${dayBefore(45)}&limit=1`,
      )
    ).total,
  );
  expect(ready.total).toBeGreaterThan(5);
  expect(waiting.total).toBeGreaterThanOrEqual(3);

  // The sentence under the title counts each of them.
  const head = page.locator(".page-head");
  await expect(head.locator("strong")).toHaveText(
    `${plural(ready.total, "application")} ${ready.total === 1 ? "is" : "are"} ready for you.`,
  );
  await expect(head).toContainText(
    `Your agent has ${plural(questions.total, "question")}`,
  );
  await expect(head).toContainText(
    `${plural(blocked.total, "application")} ${blocked.total === 1 ? "is" : "are"} blocked by a requirement`,
  );
  await expect(head).toContainText(
    `${plural(waiting.total, "application")} have waited more than 45 days for a reply.`,
  );

  // Ready to apply: closest deadline first, one primary action, the rest behind a link.
  const readyCard = card(page, "Ready to apply");
  await expect(readyCard.locator("header .count")).toHaveText(
    String(ready.total),
  );
  const rows = readyCard.locator("li").filter({
    has: page.getByRole("link", { name: /^Review/ }),
  });
  await expect(rows).toHaveCount(5);
  for (const [index, application] of ready.items.entries())
    await expect(rows.nth(index).locator(".title")).toHaveText(
      application.job.title,
    );
  await expect(readyCard.locator(".btn.primary")).toHaveCount(1);
  await expect(rows.first().locator(".btn.primary")).toHaveAttribute(
    "href",
    `#review?application=${ready.items[0].id}`,
  );
  await expect(
    rows.filter({ hasText: "Python Engineer" }).locator(".tag").first(),
  ).toHaveText("Closes tomorrow");
  await expect(
    rows.filter({ hasText: "Senior Machine Learning" }).locator(".tag").first(),
  ).toHaveText(/^Overdue since/);
  await expect(rows.filter({ hasText: "Python Engineer" })).toContainText("P1");
  // A long title and company wrap inside the row.
  await fitsViewport(page);
  const more = readyCard.getByRole("link", {
    name: `${plural(ready.total - 5, "more ready application")}`,
  });
  await expect(more).toHaveAttribute(
    "href",
    "#applications?stage=ready&sort=deadline",
  );

  // Needs your decision: the newest open questions, answered in place, and
  // the blocked applications, closest deadline first. Other tests add their
  // own, so the rows are compared with the API.
  const decide = card(page, "Needs your decision");
  await expect(decide.locator("header .count")).toHaveText(
    String(questions.total + blocked.total),
  );
  const asked = (await call(page, "/questions?state=open&limit=3")).items;
  const stopped = (
    await call(
      page,
      "/applications?readiness=blocked&status=draft&sort=deadline&limit=3",
    )
  ).items;
  await expect(decide.getByRole("article")).toHaveText([
    ...asked.map((item: any) => new RegExp(escape(item.question))),
    ...stopped.map(
      (item: any) =>
        new RegExp(`^Blocking requirement${escape(item.job.title)}`),
    ),
  ]);
  // The agent's question about a start date (synthetic seed).
  const start = decide.getByRole("article", {
    name: "Can you start before 1 February?",
  });
  await expect(start).toContainText("career-agent · prepare-shortlist");
  await expect(
    start.getByRole("group", { name: "Choices" }).getByRole("button"),
  ).toHaveText(["Yes, from 15 January", "No, February only"]);
  await expect(
    start.getByRole("link", { name: /^Application: Site Reliability/ }),
  ).toBeVisible();
  await expect(
    start.getByRole("link", { name: "Asked in this run" }),
  ).toHaveAttribute("href", /#activity\?section=runs&run=/);
  // A question without choices has its text box open.
  await expect(
    decide
      .getByRole("article", { name: /on-call work at night/ })
      .getByRole("textbox", { name: "Your answer" }),
  ).toBeVisible();
  const first = decide.getByRole("article", {
    name: new RegExp(`^${escape(stopped[0].job.title)}.* is blocked`),
  });
  await expect(first.locator(".tag")).toHaveText("Blocking requirement");
  await expect(
    first.getByRole("link", { name: "Open the requirements" }),
  ).toHaveAttribute(
    "href",
    `#review?application=${stopped[0].id}&tab=requirements`,
  );

  // The pipeline strip: each stage counted, each a link to its list.
  const counts = await call(page, "/applications?limit=1");
  const pipeline = page.getByRole("navigation", { name: "Pipeline" });
  const stages = [
    ["Preparing", counts.stage_counts.draft - counts.ready_count],
    ["Ready", counts.ready_count],
    ["Applied", counts.stage_counts.applied],
    ["Interview", counts.stage_counts.interview],
    ["Offer", counts.stage_counts.offer],
  ];
  await expect(pipeline.getByRole("link")).toHaveText(
    stages.map(([label, value]) => `${value}${label}`),
  );
  // Preparing no longer includes the Ready ones: each step opens its own stage.
  expect(
    await pipeline
      .getByRole("link")
      .evaluateAll((links) => links.map((link) => link.getAttribute("href"))),
  ).toEqual([
    "#applications?stage=preparing",
    "#applications?stage=ready&sort=deadline",
    "#applications?stage=applied",
    "#applications?stage=interview",
    "#applications?stage=offer",
  ]);

  // Since your last visit: the first visit covers the last 7 days.
  const since = card(page, "Since your last visit");
  await expect(since.locator("header .caption")).toHaveText("Last 7 days");
  await expect(
    since.getByRole("listitem").filter({ hasText: "In progress" }).first(),
  ).toContainText("so far");
  const collection = since
    .getByRole("listitem")
    .filter({ has: page.getByRole("link", { name: "Collection" }) });
  await expect(collection).toContainText("new jobs from 2 sources");
  await expect(collection).toContainText(
    "1 source failed: Fjord Analytics board",
  );
  await expect(collection.locator(".tag")).toHaveText("Needs attention");

  // Waiting for a reply: how many waited longer than the policy's period.
  const wait = card(page, "Waiting for a reply");
  await expect(wait.locator("header .count")).toHaveText(
    String(counts.stage_counts.applied),
  );
  await expect(wait).toContainText(
    `${waiting.total} applications were sent more than 45 days ago without an answer.`,
  );
  // Closing them as no reply lists them first; keeping them open changes nothing.
  await wait
    .getByRole("button", { name: `Close ${waiting.total} as no reply` })
    .click();
  const dialog = page.locator("dialog[open]");
  await expect(dialog.getByRole("listitem")).toHaveCount(waiting.total);
  await dialog.getByRole("button", { name: "Keep them open" }).click();
  await expect(dialog).toHaveCount(0);
  // The progress of sent applications moved to Applications, Insights.
  await expect(card(page, "Progress")).toHaveCount(0);
  await expect(wait.getByRole("link", { name: "Insights" })).toHaveAttribute(
    "href",
    "#applications?section=insights",
  );
  await fitsViewport(page);

  // Record replies opens Applied past the period.
  await wait.getByRole("link", { name: "Record replies" }).click();
  await expect(page).toHaveURL(/#applications\?stage=applied&waiting=1/);
  await expect(
    page.getByRole("button", {
      name: /^No reply for more than 45 days ?: remove this filter$/,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Applications" }).getByRole("row"),
  ).toHaveCount(waiting.total + 1);

  // A stage of the pipeline opens Applications with that stage.
  await go(page, "today");
  await page
    .getByRole("navigation", { name: "Pipeline" })
    .getByRole("link", { name: /Interview$/ })
    .click();
  await expect(page).toHaveURL(/#applications\?stage=interview/);
  await expect(page.locator(".main h1")).toHaveText("Applications");
  await expect(
    page.getByRole("group", { name: "Stage" }).getByRole("button", {
      name: /^Interview/,
    }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("keyboard only: the owner answers the agent's questions on Today", async ({
  page,
}) => {
  await go(page, "today");
  const token = await agent(page, unique("Synthetic agent"));
  const written = unique("Which notice period applies?");
  const chosen = unique("Is a hybrid schedule acceptable?");
  const job = await call(page, "/jobs", "POST", {
    title: unique("Hybrid role"),
    company: "Example Labs",
    posting: "Build reliable services.",
  });
  const first = await call(
    page,
    "/questions",
    "POST",
    { question: written, why: "The posting does not say." },
    token.token,
  );
  await call(
    page,
    "/questions",
    "POST",
    {
      question: chosen,
      subject_type: "job",
      subject_id: job.id,
      choices: ["Yes", "No"],
    },
    token.token,
  );
  await page.reload();
  await settled(page);
  const decide = card(page, "Needs your decision");
  const choice = decide.getByRole("article", { name: chosen });
  const text = decide.getByRole("article", { name: written });
  await expect(choice).toContainText(token.name);
  await expect(
    choice.getByRole("link", { name: /^Job: Hybrid role/ }),
  ).toBeVisible();

  // A choice answers at once.
  await choice.getByRole("button", { name: "Yes", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(page.locator(".toast").last()).toContainText("Answer saved.");
  await expect(choice).toHaveCount(0);

  // A written answer: the box takes focus, Escape ("Not now") only closes it.
  const box = text.getByRole("textbox", { name: "Your answer" });
  await box.focus();
  await page.keyboard.type("Three months.");
  await page.keyboard.press("Escape");
  const write = text.getByRole("button", { name: "Write an answer" });
  await expect(write).toBeFocused();
  expect((await call(page, `/questions/${first.id}`)).state).toBe("open");
  await page.keyboard.press("Enter");
  await expect(box).toBeFocused();
  await expect(box).toHaveValue("Three months.");
  await page.keyboard.press("ControlOrMeta+Enter");
  await expect(page.locator(".toast").last()).toContainText("Answer saved.");
  await expect(text).toHaveCount(0);

  const answers = await call(
    page,
    "/questions?state=answered&limit=50",
    "GET",
    undefined,
    token.token,
  );
  const mine = answers.items.filter((item: any) =>
    [written, chosen].includes(item.question),
  );
  const answer = (question: string) =>
    mine.find((item: any) => item.question === question);
  expect(answer(written).answer).toBe("Three months.");
  expect(answer(chosen).answer_choice).toBe("Yes");
  await call(page, "/tokens/" + token.id, "DELETE");
});

test("since your last visit counts from the end of the previous visit", async ({
  page,
}) => {
  // The last visit ended five and a half hours ago: only what moved since
  // then is listed.
  const seen = new Date(Date.now() - 5.5 * 3_600_000).toISOString();
  await page.addInitScript((seen) => {
    if (!sessionStorage.getItem("seeded")) {
      localStorage.setItem(
        "openings-today-visit",
        JSON.stringify({ since: null, seen }),
      );
      sessionStorage.setItem("seeded", "1");
    }
  }, seen);
  await go(page, "today");
  await settled(page);
  const since = card(page, "Since your last visit");
  const caption = since.locator("header .caption");
  await expect(caption).not.toHaveText("Last 7 days");
  await expect(caption).toHaveText(/^(Today|Yesterday) \d\d:\d\d$/);
  const shown = await caption.textContent();
  await expect(
    since.getByRole("link", { name: "review-inbox", exact: true }),
  ).toHaveCount(0);
  await expect(
    since.getByRole("link", { name: "maintain-career", exact: true }),
  ).toHaveCount(0);
  // Collection since then: the newest run of the fixtures, which failed, and
  // the runs the Collection tests started and stopped (read from the API).
  const runs = (await call(page, "/collection/runs?limit=100")).items.filter(
    (run: { created_at: string; finished_at?: string }) =>
      Date.parse(run.finished_at || run.created_at) >= Date.parse(seen),
  ).length;
  await expect(since).toContainText(
    `No new jobs in ${runs} collection run${runs === 1 ? "" : "s"}; 1 source failed: Fjord Analytics board`,
  );
  const stored = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("openings-today-visit") || "null"),
  );
  expect(stored.since).toBe(seen);

  // Looking elsewhere and coming back is the same visit.
  await go(page, "activity");
  await go(page, "today");
  await expect(
    card(page, "Since your last visit").locator("header .caption"),
  ).toHaveText(shown!);
});

test("every card of Today has its empty, loading and error state", async ({
  page,
}) => {
  const empty = { items: [], total: 0, stage_counts: {}, ready_count: 0 };
  const overview = {
    sent: 0,
    interviews: 0,
    offers: 0,
    active: 0,
    drafts: 0,
    inbox: 0,
    incomplete: 0,
    funnel: [],
    activity: [],
  };
  // An empty workspace: every list answers with nothing.
  await page.route(
    /\/api\/v1\/(applications|questions|runs|collection\/runs|overview)(\?|$)/,
    (route) =>
      route.fulfill({
        json: route.request().url().includes("/overview") ? overview : empty,
      }),
  );
  await go(page, "today");
  await settled(page);
  await expect(page.locator(".page-head")).toContainText(
    "Nothing is waiting for you. No agent has worked in this workspace yet.",
  );
  for (const [title, state] of [
    ["Ready to apply", "Nothing is ready to apply"],
    ["Needs your decision", "No decision is waiting"],
    ["Since your last visit", "Nothing new"],
    ["Waiting for a reply", "No long wait"],
  ])
    await expect(
      card(page, title).getByRole("heading", { name: state }),
    ).toBeVisible();
  await fitsViewport(page);

  // Loading: each card says what it is reading.
  await page.unrouteAll();
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route(
    /\/api\/v1\/applications\?readiness=ready/,
    async (route) => {
      await held;
      await route.continue();
    },
  );
  await page.reload();
  await expect(card(page, "Ready to apply").getByRole("status")).toHaveText(
    "Loading ready applications…",
  );
  await expect(page.locator(".page-head")).toContainText(
    "Reading your workspace…",
  );
  release();
  await expect(card(page, "Ready to apply").getByRole("status")).toHaveCount(0);

  // Errors: the card says so and offers a retry; the summary does not guess.
  await page.unrouteAll();
  let fail = true;
  await page.route(/\/api\/v1\/(questions|runs)\?/, (route) =>
    fail
      ? route.fulfill({
          status: 500,
          json: { error: { code: "internal", message: "The server failed." } },
        })
      : route.continue(),
  );
  await page.reload();
  await expect(page.locator(".page-head")).toContainText(
    "Some of today's numbers could not be loaded.",
  );
  for (const title of ["Needs your decision", "Since your last visit"])
    await expect(card(page, title).getByRole("alert")).toContainText(
      "The server failed.",
    );
  fail = false;
  for (const title of ["Needs your decision", "Since your last visit"])
    await card(page, title)
      .getByRole("button", { name: "Try again" })
      .first()
      .click();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("on a phone the bottom bar never covers the end of Today", async ({
  page,
}) => {
  test.skip(!isNarrow(page), "The bottom bar exists on narrow screens.");
  await go(page, "today");
  await settled(page);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const bar = await page
    .getByRole("navigation", { name: "Main" })
    .boundingBox();
  const last = await card(page, "Waiting for a reply").boundingBox();
  expect(last!.y + last!.height).toBeLessThanOrEqual(bar!.y);
  await fitsViewport(page);
});
