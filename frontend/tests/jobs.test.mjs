import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of this module; it uses no React.
const model = await import("../src/screens/jobs/model.ts");

const now = new Date(2026, 10, 13, 10, 0);
const signals = (fields = {}) => ({
  computed: true,
  language: "en",
  language_confidence: 0.9,
  required: [],
  duplicate_checked: true,
  duplicate: null,
  no_longer_listed: false,
  unlisted_at: null,
  ...fields,
});
const job = (fields = {}) => ({
  id: "j1",
  version: 1,
  title: "Data Engineer",
  company: "Northstar Labs",
  location: "Zurich",
  url: "",
  triage: "new",
  metadata: {},
  source: "linkedin",
  complete: true,
  application: null,
  application_count: 0,
  created_at: "2026-11-13T08:00:00",
  signals: signals(),
  dismissal: null,
  ...fields,
});
const view = (query = "") => model.readView(new URLSearchParams(query));

test("the address gives the tab, the order and the filters, and only differences are written back", () => {
  const plain = view();
  assert.equal(plain.section, "new");
  assert.equal(plain.sort, "newest");
  assert.deepEqual(model.viewQuery(plain), {
    section: undefined,
    q: undefined,
    sort: undefined,
    job: undefined,
    source: undefined,
    company: undefined,
    location: undefined,
    posting_language: undefined,
    requires: undefined,
    signal: undefined,
    created_since: undefined,
    hide_unspoken: undefined,
  });
  const dismissed = view("section=dismissed&dismissed_by=agent&job=j9");
  assert.equal(dismissed.sort, "dismissed");
  assert.equal(model.viewQuery(dismissed).dismissed_by, "agent");
  assert.equal(model.viewQuery(dismissed).sort, undefined);
  // Who dismissed a job filters only the Dismissed tab.
  const elsewhere = { ...dismissed, section: "all" };
  assert.equal(model.viewQuery(elsewhere).dismissed_by, undefined);
  assert.equal(model.narrowed(elsewhere), false);
  // An unknown tab is New; the old incomplete parameter is a signal.
  assert.equal(view("section=shortlisted").section, "new");
  assert.equal(view("complete=false").filters.signal, "incomplete");
});

test("the list request names the tab, the filters and always the languages switch", () => {
  const fresh = model.listQuery(view("q=rust&source=linkedin"), 200);
  assert.equal(fresh.triage, "new");
  assert.equal(fresh.q, "rust");
  assert.equal(fresh.source, "linkedin");
  assert.equal(fresh.hide_unspoken_required, false);
  assert.equal(fresh.include_counts, true);
  const all = model.listQuery(view("section=all&signal=incomplete"), 50);
  assert.equal(all.triage, undefined);
  assert.equal(all.complete, false);
  assert.equal(all.signal, undefined);
  const dismissed = model.listQuery(
    view("section=dismissed&dismissed_by=agent&hide_unspoken=true"),
    50,
  );
  assert.equal(dismissed.sort, "dismissed");
  assert.equal(dismissed.dismissed_by, "agent");
  assert.equal(dismissed.hide_unspoken_required, true);
});

test("active filters read as chips, in words", () => {
  const chips = model.chipsOf(
    view(
      "section=dismissed&source=linkedin&requires=de&signal=likely_duplicate&dismissed_by=owner&hide_unspoken=true",
    ),
    now,
  );
  assert.deepEqual(
    chips.map((chip) => `${chip.field}: ${chip.value}`),
    [
      "Source: LinkedIn",
      "Requires: German",
      "Signal: Possible duplicate",
      "Dismissed by: You",
      "Languages: Only ones I speak",
    ],
  );
  const since = model.foundChoices(now)[1];
  assert.equal(since.label, "Last 7 days");
  assert.equal(
    model.chipsOf(view(`created_since=${since.value}`), now)[0].value,
    "Last 7 days",
  );
});

test("rows group by day while the list is in time order", () => {
  const rows = [
    job({ id: "a", created_at: "2026-11-13T09:00:00" }),
    job({ id: "b", created_at: "2026-11-12T20:00:00" }),
    job({ id: "c", created_at: "2026-11-02T08:00:00" }),
  ];
  const groups = model.groupRows(rows, { sort: "newest", section: "new" }, now);
  assert.deepEqual(
    groups.map((group) => [group.label, group.rows.map((row) => row.id)]),
    [
      ["Today", ["a"]],
      ["Yesterday", ["b"]],
      ["Earlier", ["c"]],
    ],
  );
  const byName = model.groupRows(rows, { sort: "title", section: "new" }, now);
  assert.deepEqual(
    byName.map((group) => group.label),
    [""],
  );
});

test("after a decision the next job is shown, or the previous one at the end", () => {
  assert.equal(model.neighbour(["a", "b", "c"], "a"), "b");
  assert.equal(model.neighbour(["a", "b", "c"], "c"), "b");
  assert.equal(model.neighbour(["a"], "a"), "");
  assert.equal(model.neighbour(["a", "b"], "x"), "a");
  assert.equal(model.leaves("new", "dismissed"), true);
  assert.equal(model.leaves("new", "new"), false);
  assert.equal(model.leaves("dismissed", "new"), true);
  assert.equal(model.leaves("all", "dismissed"), false);
});

test("a row carries one signal, most telling first", () => {
  assert.equal(model.rowSignal(job()), null);
  assert.equal(model.rowSignal(job({ complete: false })), "incomplete");
  assert.equal(
    model.rowSignal(
      job({
        complete: false,
        signals: signals({ duplicate: { job_id: "x" } }),
      }),
    ),
    "duplicate",
  );
  assert.equal(
    model.rowSignal(job({ signals: signals({ no_longer_listed: true }) })),
    "unlisted",
  );
});

test("the detail says languages, salary, work style and who dismissed in words", () => {
  const german = job({
    signals: signals({ language: "de", required: [["de"], ["fr", "en"]] }),
  });
  assert.equal(
    model.languageLine(german),
    "Posting in German · Requires German · Requires French or English",
  );
  assert.deepEqual(model.signalTags(german), [
    "Requires German",
    "Requires French or English",
  ]);
  assert.equal(
    model.salaryText({
      salary: {
        min_amount: 115000,
        max_amount: 135000,
        currency: "CHF",
        interval: "yearly",
      },
    }),
    "CHF 115k–135k a year",
  );
  assert.equal(model.salaryText({ salary: "Competitive" }), "Competitive");
  assert.equal(model.salaryText({}), "");
  assert.equal(model.workStyle({ is_remote: true }), "Remote");
  assert.equal(model.jobTypeText("fulltime"), "Full time");
  assert.equal(model.actorPhrase("owner"), "by you");
  assert.equal(model.actorPhrase("agent:Claude laptop"), "by Claude laptop");
  assert.equal(model.actorPhrase("system"), "by job sources");
  assert.equal(
    model.sourceLabel({ source: "", metadata: {} }),
    "Added by hand",
  );
  assert.equal(model.deadlineOf({ deadline: "2026-11-18" }), "2026-11-18");
  assert.equal(model.closesSoon("2026-11-18", now), true);
  assert.equal(model.closesSoon("2026-12-18", now), false);
});

test("a duplicate is explained without a score", () => {
  assert.equal(
    model.reasonsLine({
      matched: ["company", "posting_text"],
      conflicts: ["location"],
    }),
    "Both have the same company, identical posting text, but a different place.",
  );
  assert.equal(model.reasonsLine(null), "");
});

test("a posting's plain text keeps its headings, paragraphs and lists", () => {
  const blocks = model.postingBlocks(
    "Build reliable services.\n\nResponsibilities\nDesign practical APIs.\n- Own the pipelines\n- Work with analysts\n\n## What we offer\nA yearly budget.",
  );
  assert.deepEqual(blocks, [
    { kind: "paragraph", text: "Build reliable services." },
    { kind: "heading", text: "Responsibilities" },
    { kind: "paragraph", text: "Design practical APIs." },
    { kind: "list", items: ["Own the pipelines", "Work with analysts"] },
    { kind: "heading", text: "What we offer" },
    { kind: "paragraph", text: "A yearly budget." },
  ]);
  // A single sentence stays a paragraph.
  assert.deepEqual(model.postingBlocks("Short role"), [
    { kind: "paragraph", text: "Short role" },
  ]);
});

test("history entries are named in words", () => {
  assert.equal(
    model.eventTitle({ kind: "triage_changed", payload: { to: "dismissed" } }),
    "Dismissed",
  );
  assert.equal(
    model.eventTitle({
      kind: "triage_changed",
      payload: { from: "dismissed", to: "new" },
    }),
    "Restored",
  );
  assert.equal(model.eventTitle({ kind: "job_added" }), "Found");
  assert.equal(
    model.unspokenLine({ count: 3, hidden: false }, 40),
    "would hide 3 of 40",
  );
  assert.equal(
    model.unspokenLine({ count: 3, hidden: true }, 37),
    "hides 3 of 40",
  );
});
