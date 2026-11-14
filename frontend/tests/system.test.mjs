import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the source files; these modules have no React.
const routes = await import("../src/shell/routes.ts");
const collection = await import("../src/pages/collection/model.ts");
const settings = await import("../src/pages/settings/model.ts");

test("links of the old Settings and Collection open where their parts moved", () => {
  const hash = routes.canonicalHash;
  // Provider settings and the task list of Settings are tabs of Collection.
  assert.equal(
    hash("#settings?section=collection"),
    "#collection?section=providers",
  );
  assert.equal(
    hash("#settings?section=activity&source_id=s1"),
    "#collection?section=runs&source_id=s1",
  );
  assert.equal(
    hash("#settings?section=activity&activity_view=tasks&state=failed"),
    "#collection?section=runs&state=failed&view=tasks",
  );
  // The two lists of the old Collection are one list filtered by kind.
  assert.equal(
    hash("#collection?section=searches&q=data"),
    "#collection?q=data&kind=search",
  );
  assert.equal(hash("#collection?section=companies"), "#collection?kind=board");
  // Skills are a tab of Settings.
  assert.equal(hash("#skills"), "#settings?section=skills");
  assert.equal(
    hash("#skills?skill=review-inbox"),
    "#settings?skill=review-inbox&section=skills",
  );
  assert.equal(routes.routeOf("#skills"), "settings");
  // Current addresses stay as they are.
  assert.equal(hash("#settings?section=agents"), null);
  assert.equal(hash("#collection?section=runs"), null);
  // The design's name of the setup guide.
  assert.equal(hash("#onboarding"), "#setup");
  assert.equal(routes.routeOf("#setup?step=record"), "setup");
  assert.equal(hash("#setup"), null);
});

test("a run or task is described by its counts, state and schedule", () => {
  assert.equal(
    collection.countsLine({ received: 40, created: 3, existing: 37 }),
    "40 processed · 3 new · 37 already archived",
  );
  assert.equal(collection.countsLine({}, "running"), "Nothing found yet");
  assert.equal(
    collection.countsLine({ created: 0 }, "failed"),
    "Nothing found",
  );
  assert.equal(
    collection.scheduleLabel({
      kind: "daily",
      times: ["06:00", "17:00"],
      timezone: "Europe/Zurich",
    }),
    "Daily 06:00, 17:00 · Europe/Zurich",
  );
  assert.equal(
    collection.scheduleLabel({ kind: "interval", minutes: 1440 }),
    "Once a day",
  );
  assert.equal(
    collection.scheduleLabel({ kind: "interval", minutes: 120 }),
    "Every 2 h",
  );
  assert.equal(
    collection.scheduleLabel({ kind: "interval", minutes: 45 }),
    "Every 45 min",
  );
  assert.equal(collection.seconds(42), "42s");
  assert.equal(collection.seconds(3725), "1h 2m");
  assert.deepEqual(collection.stateTag({ state: "failed" }), {
    text: "Failed",
    tone: "danger",
  });
  const later = new Date(Date.now() + 3600_000).toISOString();
  assert.equal(
    collection.stateTag({
      state: "queued",
      next_run_at: later,
      task_ids: [],
      tasks: [{ state: "queued", error: "Next collection batch scheduled." }],
    }).text,
    "Continuing collection",
  );
  assert.equal(
    collection.stateTag({ state: "queued", next_run_at: later, error: "429" })
      .text,
    "Waiting",
  );
});

test("sources name their providers and share only common limits", () => {
  assert.deepEqual(
    collection.providersOf({
      kind: "jobspy",
      config: { providers: ["linkedin", "indeed"] },
    }),
    ["LinkedIn", "Indeed"],
  );
  assert.deepEqual(collection.providersOf({ kind: "greenhouse", config: {} }), [
    "Greenhouse",
  ]);
  assert.deepEqual(collection.providersOf({ kind: "rss", config: {} }), [
    "RSS feed",
  ]);
  const schema = (kind, properties) => ({
    kind,
    label: kind,
    config_schema: { properties },
    capabilities: {},
  });
  const shared = collection.sharedProperties(
    [
      schema("a", { max_results: { minimum: 1, maximum: 2000 }, board: {} }),
      schema("b", { max_results: { minimum: 5, maximum: 500 } }),
    ],
    ["a", "b"],
  );
  assert.deepEqual(Object.keys(shared), ["max_results"]);
  assert.equal(shared.max_results.minimum, 5);
  assert.equal(shared.max_results.maximum, 500);
  assert.equal(collection.nextTime(["07:00"]), "08:00");
  assert.equal(collection.nextTime(["23:00", "00:00"]), "01:00");
  assert.deepEqual(collection.terms(" intern, , working student "), [
    "intern",
    "working student",
  ]);
});

test("sizes read in the units of the restore limit", () => {
  assert.equal(settings.megabytes(5 * 1024 ** 2), "5.0 MiB");
  assert.equal(settings.megabytes(3 * 1024 ** 3), "3.0 GiB");
});

test("a search line leaves out an empty query and names the place", () => {
  const search = (config) => ({ kind: "jobspy", config });
  assert.equal(
    collection.sourceLine(search({ query: "", location: "" })),
    "Search · All locations",
  );
  assert.equal(
    collection.sourceLine(
      search({ query: "  data engineer ", country: "switzerland" }),
    ),
    'Search · "data engineer" · switzerland',
  );
  assert.deepEqual(collection.NATIONAL, ["indeed", "glassdoor"]);
});
