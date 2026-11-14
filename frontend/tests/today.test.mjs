import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const { todaySummary } = await import("../src/pages/today/summary.ts");
const time = await import("../src/library/time.ts");
const changes = await import("../src/library/changes.ts");

test("the summary leads with ready applications and counts in words", () => {
  const counts = { ready: 6, blocked: 0, waiting: 3, days: 30 };
  assert.deepEqual(todaySummary(counts), {
    lead: "6 applications are ready for you.",
    rest: "3 applications have waited more than 30 days for a reply.",
    quiet: false,
  });
  assert.deepEqual(
    todaySummary({ ready: 1, blocked: 1, waiting: 1, days: 45 }),
    {
      lead: "1 application is ready for you.",
      rest: "1 application is blocked by a requirement, and 1 application has waited more than 45 days for a reply.",
      quiet: false,
    },
  );
  // Nothing ready: the first thing that waits leads.
  assert.deepEqual(todaySummary({ ready: 0, blocked: 2, waiting: 0, days: 30 }), {
    lead: "2 applications are blocked by a requirement.",
    rest: "",
    quiet: false,
  });
  // Nothing waits: say so.
  assert.deepEqual(todaySummary({ ready: 0, blocked: 0, waiting: 0, days: 30 }), {
    lead: "Nothing is waiting for you.",
    rest: "",
    quiet: true,
  });
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

test("a change says where it moved a record", () => {
  const change = (kind, payload) => ({ kind, payload });
  assert.equal(
    changes.changeDetail(
      change("application_updated", { from: "draft", to: "applied" }),
    ),
    "Preparing → Applied",
  );
  assert.equal(
    changes.changeDetail(
      change("triage_changed", { from: "inbox", to: "saved" }),
    ),
    "Inbox → Shortlist",
  );
  // A change that kept the stage names the fields it touched instead.
  assert.equal(
    changes.changeDetail(
      change("application_updated", {
        from: "draft",
        to: "draft",
        fields: ["answers", "priority"],
      }),
    ),
    "Fields: answers, priority",
  );
  assert.equal(
    changes.changeDetail(
      change("application_ready_cleared", { reason: "document_created" }),
    ),
    "A new document revision was saved",
  );
  assert.equal(
    changes.changeDetail(
      change("preferences_updated", { section: "working_with_me" }),
    ),
    "Working with me",
  );
  assert.equal(
    changes.changeLabel("application_marked_ready"),
    "Application marked ready",
  );
});
