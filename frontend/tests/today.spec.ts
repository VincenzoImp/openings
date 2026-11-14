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

// Today, the first screen, on the synthetic workspace of
// backend/tests/today_fixtures.py: ready applications with deadlines, a
// blocked one and sent applications of different ages. Each test starts from
// the seeded workspace (fixtures.ts).
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

const plural = (count: number, one: string) =>
  `${count} ${count === 1 ? one : one + "s"}`;
/** The day before which a sent application has waited long (as Today computes it). */
const dayBefore = (days: number) =>
  new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
/** Shortlisted applications held by a blocking requirement, closest deadline first. */
async function blockedOf(page: Page) {
  const items = (
    await call(page, "/applications?stage=shortlisted&sort=deadline&limit=200")
  ).items.filter((item: any) => item.blocking_requirements > 0);
  return { items, total: items.length };
}
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".loading")).toHaveCount(0);
}
test("Today says what is ready, where applications stand and what waits for a reply", async ({
  page,
}) => {
  await go(page, "today");
  await expect(page).toHaveTitle("Today · Openings");
  await settled(page);
  const ready = await call(
    page,
    "/applications?stage=ready&sort=deadline&limit=5",
  );
  const blocked = await blockedOf(page);
  // The synthetic settings say 45 days of no reply; the server reads them.
  const waiting = await call(page, "/applications?needs=reply_overdue&limit=1");
  expect(waiting.no_reply.days).toBe(45);
  expect(waiting.total).toBe(
    (
      await call(
        page,
        `/applications?stage=applied&applied_until=${dayBefore(45)}&limit=1`,
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
  expect(blocked.total).toBeGreaterThan(0);
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

  // The pipeline strip: each stage counted, each a link to its list.
  const counts = await call(page, "/applications?limit=1");
  const pipeline = page.getByRole("navigation", { name: "Pipeline" });
  const stages = [
    [
      "Shortlisted",
      counts.stage_counts.shortlisted - counts.stage_counts.ready,
    ],
    ["Ready", counts.stage_counts.ready],
    ["Applied", counts.stage_counts.applied],
    ["Interview", counts.stage_counts.interview],
    ["Offer", counts.stage_counts.offer],
  ];
  await expect(pipeline.getByRole("link")).toHaveText(
    stages.map(([label, value]) => `${value}${label}`),
  );
  // Each step opens its own stage.
  expect(
    await pipeline
      .getByRole("link")
      .evaluateAll((links) => links.map((link) => link.getAttribute("href"))),
  ).toEqual([
    "#applications?stage=shortlisted",
    "#applications?stage=ready&sort=deadline",
    "#applications?stage=applied",
    "#applications?stage=interview",
    "#applications?stage=offer",
  ]);

  // Waiting for a reply: how many waited longer than the no-reply period.
  const wait = card(page, "Waiting for a reply");
  await expect(wait.locator("header .count")).toHaveText(
    String(counts.stage_counts.applied),
  );
  await expect(wait).toContainText(
    `${waiting.total} applications were sent more than 45 days ago without an answer.`,
  );
  // Each is listed with its own Close as no reply.
  await expect(
    wait
      .getByRole("list", { name: "Applications without a reply" })
      .getByRole("button", { name: /^Close as no reply/ }),
  ).toHaveCount(Math.min(waiting.total, 5));
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

test("every card of Today has its empty, loading and error state", async ({
  page,
}) => {
  const empty = { items: [], total: 0, stage_counts: {} };
  // An empty workspace: every list answers with nothing.
  await page.route(/\/api\/v1\/applications(\?|$)/, (route) =>
    route.fulfill({ json: empty }),
  );
  await go(page, "today");
  await settled(page);
  await expect(page.locator(".page-head")).toContainText(
    "Nothing is waiting for you.",
  );
  for (const [title, state] of [
    ["Ready to apply", "Nothing is ready to apply"],
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
  await page.route(/\/api\/v1\/applications\?stage=ready/, async (route) => {
    await held;
    await route.continue();
  });
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
  await page.route(
    /\/api\/v1\/applications\?(stage=ready|needs=reply_overdue)/,
    (route) =>
      fail
        ? route.fulfill({
            status: 500,
            json: {
              error: { code: "internal", message: "The server failed." },
            },
          })
        : route.continue(),
  );
  await page.reload();
  await expect(page.locator(".page-head")).toContainText(
    "Some of today's numbers could not be loaded.",
  );
  for (const title of ["Ready to apply", "Waiting for a reply"])
    await expect(card(page, title).getByRole("alert")).toContainText(
      "The server failed.",
    );
  fail = false;
  for (const title of ["Ready to apply", "Waiting for a reply"])
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
