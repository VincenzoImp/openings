import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const visit = await import("../src/pages/today/visit.ts");
const { todaySummary, replyDays, DEFAULT_REPLY_DAYS } =
  await import("../src/pages/today/summary.ts");
const { collectedSince, collectedLine } =
  await import("../src/pages/today/collected.ts");
const time = await import("../src/library/time.ts");
const wording = await import("../src/pages/activity/wording.ts");

const at = (text) => new Date(text);
const MIN = 60_000;

/** A storage double: what Today would keep in localStorage. */
function store(initial = {}) {
  const items = { ...initial };
  return {
    items,
    getItem: (key) => (key in items ? items[key] : null),
    setItem: (key, value) => {
      items[key] = String(value);
    },
  };
}

test("the first visit counts the last 7 days and remembers the visit", () => {
  const kept = store();
  const now = at("2026-11-13T09:00:00Z");
  const first = visit.beginVisit(now, kept);
  assert.equal(first.since, null);
  assert.equal(
    visit.sinceOf(first, now),
    new Date(now.valueOf() - 7 * 86_400_000).toISOString(),
  );
  assert.deepEqual(JSON.parse(kept.items[visit.VISIT_KEY]), {
    since: null,
    seen: now.toISOString(),
  });
});

test("a reload or a look elsewhere keeps the visit; an absence starts the next one", () => {
  const kept = store();
  const start = at("2026-11-13T09:00:00Z");
  visit.beginVisit(start, kept);
  // Today stays open until 09:40 (the page touches the visit while visible).
  visit.touchVisit({ since: null }, at("2026-11-13T09:40:00Z"), kept);
  // Back after 20 minutes: the same visit, still counted from the start.
  const same = visit.beginVisit(at("2026-11-13T10:00:00Z"), kept);
  assert.equal(same.since, null);
  // Back the next morning: "since your last visit" starts where the last one ended.
  const next = visit.beginVisit(at("2026-11-14T08:00:00Z"), kept);
  assert.equal(next.since, "2026-11-13T10:00:00.000Z");
  // And it holds through that whole visit, however often Today is reopened.
  visit.touchVisit(next, at("2026-11-14T08:20:00Z"), kept);
  const again = visit.beginVisit(at("2026-11-14T08:45:00Z"), kept);
  assert.equal(again.since, "2026-11-13T10:00:00.000Z");
});

test("the gap that ends a visit is 30 minutes", () => {
  const seen = "2026-11-13T09:00:00.000Z";
  const stored = { since: "2026-11-12T18:00:00.000Z", seen };
  const after = (minutes) =>
    visit.openVisit(stored, new Date(Date.parse(seen) + minutes * MIN));
  assert.equal(after(30).since, stored.since);
  assert.equal(after(31).since, seen);
});

test("unusable or unavailable storage counts as a first visit and never throws", () => {
  for (const raw of [null, "", "not json", "{}", '{"seen":"yesterday"}'])
    assert.equal(visit.parseVisit(raw), null);
  assert.deepEqual(
    visit.parseVisit('{"since":"nonsense","seen":"2026-11-13T09:00:00Z"}'),
    { since: null, seen: "2026-11-13T09:00:00Z" },
  );
  const broken = {
    getItem() {
      throw new Error("SecurityError");
    },
    setItem() {
      throw new Error("QuotaExceededError");
    },
  };
  const now = at("2026-11-13T09:00:00Z");
  assert.equal(visit.beginVisit(now, broken).since, null);
  assert.doesNotThrow(() => visit.touchVisit({ since: null }, now, broken));
  assert.equal(visit.beginVisit(now, null).since, null);
});

test("the summary leads with ready applications and counts in words", () => {
  const counts = { ready: 6, questions: 2, blocked: 0, waiting: 3, days: 30 };
  assert.deepEqual(todaySummary(counts), {
    lead: "6 applications are ready for you.",
    rest: "Your agent has 2 questions, and 3 applications have waited more than 30 days for a reply.",
    quiet: false,
  });
  assert.deepEqual(
    todaySummary({ ready: 1, questions: 1, blocked: 1, waiting: 1, days: 45 }),
    {
      lead: "1 application is ready for you.",
      rest: "Your agent has 1 question, 1 application is blocked by a requirement, and 1 application has waited more than 45 days for a reply.",
      quiet: false,
    },
  );
  // Nothing ready: the first thing that waits leads.
  assert.deepEqual(
    todaySummary({ ready: 0, questions: 0, blocked: 2, waiting: 0, days: 30 }),
    {
      lead: "2 applications are blocked by a requirement.",
      rest: "",
      quiet: false,
    },
  );
  // Nothing waits: say so, and what the agent last did.
  assert.deepEqual(
    todaySummary(
      { ready: 0, questions: 0, blocked: 0, waiting: 0, days: 30 },
      "Your agent last finished review-inbox, yesterday 18:00.",
    ),
    {
      lead: "Nothing is waiting for you.",
      rest: "Your agent last finished review-inbox, yesterday 18:00.",
      quiet: true,
    },
  );
});

test("the no-reply period comes from the policy's No reply decision", () => {
  const item = (label, value) => ({ label, value });
  assert.equal(replyDays([item("No reply", "45 days")]), 45);
  assert.equal(replyDays([item("No response after", 21)]), 21);
  assert.equal(replyDays([item("no-reply period", "60")]), 60);
  // Anything else falls back to the default.
  assert.equal(replyDays([]), DEFAULT_REPLY_DAYS);
  assert.equal(replyDays([item("No reply", "six weeks")]), 30);
  assert.equal(replyDays([item("No reply", 0)]), 30);
  assert.equal(replyDays([item("Salary", "45 days")]), 30);
});

test("collection since the last visit: new jobs, their sources and failing sources", () => {
  const run = (source, state, created, when) => ({
    id: source + when,
    source_id: source,
    source_name: source + " board",
    state,
    created_at: when,
    finished_at: when,
    counts: { created },
  });
  const runs = [
    run("fjord", "failed", 0, "2026-11-13T08:00:00Z"),
    run("alpine", "succeeded", 7, "2026-11-13T07:00:00Z"),
    run("fjord", "succeeded", 5, "2026-11-12T22:00:00Z"),
    run("kestrel", "failed", 0, "2026-11-12T21:00:00Z"),
    run("kestrel", "succeeded", 2, "2026-11-12T23:00:00Z"),
    run("orbit", "succeeded", 9, "2026-11-10T08:00:00Z"),
  ];
  // Newest first, as the API lists them; the last run of a source decides.
  runs.sort((a, b) => b.created_at.localeCompare(a.created_at));
  const collected = collectedSince(runs, "2026-11-12T20:00:00Z");
  assert.deepEqual(collected, {
    runs: 5,
    created: 14,
    sources: ["alpine board", "kestrel board", "fjord board"],
    failed: ["fjord board"],
  });
  assert.equal(
    collectedLine(collected),
    "14 new jobs from 3 sources; 1 source failed: fjord board",
  );
  assert.equal(
    collectedLine({ runs: 1, created: 0, sources: [], failed: [] }),
    "No new jobs in 1 collection run",
  );
});

test("times read as a person says them", () => {
  const now = new Date(2026, 10, 13, 10, 0);
  const local = (day, hour, minute = 0) =>
    new Date(2026, 10, day, hour, minute).toISOString();
  assert.equal(time.dayTime(local(13, 9, 12), now), "Today 09:12");
  assert.equal(time.dayTime(local(12, 18, 12), now), "Yesterday 18:12");
  assert.equal(time.dayTime(local(9, 19, 5), now), "Monday 19:05");
  assert.equal(time.dayTime(local(6, 10), now), "6 Nov");
  assert.equal(time.dayLabel(local(9, 19), now), "Monday 9 November");
  assert.equal(time.duration(local(13, 9), local(13, 9, 41)), "41 min");
  assert.equal(time.duration(local(13, 9), local(13, 11, 5)), "2 h 5 min");
  assert.equal(time.duration(local(13, 9), local(13, 9)), "under a minute");
});

test("deadline tags: overdue, today, tomorrow, this week and later", () => {
  const now = new Date(2026, 10, 13, 10, 0);
  assert.deepEqual(time.deadlineTag("2026-11-11", now), {
    text: "Overdue since 11 Nov",
    tone: "danger",
  });
  assert.equal(time.deadlineTag("2026-11-13", now).text, "Closes today");
  assert.deepEqual(time.deadlineTag("2026-11-14", now), {
    text: "Closes tomorrow",
    tone: "danger",
  });
  assert.deepEqual(time.deadlineTag("2026-11-18", now), {
    text: "Closes 18 Nov",
    tone: "attention",
  });
  assert.deepEqual(time.deadlineTag("2027-01-10", now), {
    text: "Closes 10 Jan 2027",
    tone: "neutral",
  });
  assert.equal(time.deadlineTag(null, now), null);
  assert.equal(time.deadlineTag("not a date", now), null);
});

test("a run is put into words by its status, summary and counts", () => {
  const run = (fields) => ({
    status: "finished",
    summary: "",
    note: "",
    changes_total: 0,
    change_counts: {},
    started_at: "2026-11-13T09:00:00Z",
    last_activity_at: "2026-11-13T09:12:00Z",
    ended_at: "2026-11-13T09:41:00Z",
    workflow: "prepare-shortlist",
    ...fields,
  });
  assert.equal(
    wording.runLine(run({ summary: "Five applications are ready." })),
    "Five applications are ready.",
  );
  assert.equal(
    wording.runLine(
      run({
        changes_total: 13,
        change_counts: {
          document_created: 10,
          application_marked_ready: 1,
          note_added: 1,
          triage_changed: 1,
        },
      }),
    ),
    "10 document revisions, 1 application marked ready, 1 note, 1 more change",
  );
  assert.equal(
    wording.runLine(run({ status: "interrupted", changes_total: 2 })),
    "Stopped without a report after 2 changes",
  );
  assert.equal(
    wording.runLine(run({ status: "open", ended_at: null })),
    "No change yet",
  );
  assert.equal(wording.runDuration(run({})), "41 min");
  assert.equal(
    wording.runDuration(run({ status: "interrupted", ended_at: null })),
    "last activity after 12 min",
  );
  assert.equal(
    wording.runDuration(
      run({ status: "open", ended_at: null }),
      new Date("2026-11-13T09:26:00Z"),
    ),
    "26 min so far",
  );
  assert.equal(
    wording.lastRunLine(undefined),
    "No agent has worked in this workspace yet.",
  );
  assert.equal(
    wording.lastRunLine(run({ status: "open" })),
    "Your agent is working on prepare-shortlist now.",
  );
});

test("a change says where it moved a record", () => {
  const change = (kind, payload) => ({ id: "1", kind, payload });
  assert.equal(
    wording.changeDetail(
      change("application_updated", { from: "draft", to: "applied" }),
    ),
    "Preparing → Applied",
  );
  assert.equal(
    wording.changeDetail(
      change("triage_changed", { from: "inbox", to: "saved" }),
    ),
    "Inbox → Shortlist",
  );
  // A change that kept the stage names the fields it touched instead.
  assert.equal(
    wording.changeDetail(
      change("application_updated", {
        from: "draft",
        to: "draft",
        fields: ["answers", "priority"],
      }),
    ),
    "Fields: answers, priority",
  );
  assert.equal(
    wording.changeDetail(
      change("application_ready_cleared", { reason: "document_created" }),
    ),
    "A new document revision was saved",
  );
  assert.equal(
    wording.changeLabel("application_marked_ready"),
    "Application marked ready",
  );
  assert.equal(wording.countedAs("document_created", 1), "document revision");
  assert.equal(wording.countedAs("job_added", 7), "jobs added");
  assert.equal(wording.countedAs("something_new", 2), "something new");
});
