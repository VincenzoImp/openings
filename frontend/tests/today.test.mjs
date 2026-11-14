import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const today = await import("../src/screens/today/model.ts");
const time = await import("../src/library/time.ts");
const changes = await import("../src/library/changes.ts");

const row = (id, fields = {}) => ({
  id,
  status: "shortlisted",
  ready: false,
  deadline: null,
  missing: [],
  open_requirements: 0,
  blocking_requirements: 0,
  job: { title: `Role ${id}`, company: "Example Labs" },
  ...fields,
});

test("the summary line names only what is not zero", () => {
  assert.deepEqual(
    today.summaryParts({ ready: 3, deadlines: 1, newJobs: 12 }),
    ["3 ready to apply", "1 deadline this week", "12 new jobs"],
  );
  assert.deepEqual(today.summaryParts({ ready: 0, deadlines: 2, newJobs: 1 }), [
    "2 deadlines this week",
    "1 new job",
  ]);
  assert.deepEqual(
    today.summaryParts({ ready: 0, deadlines: 0, newJobs: 0 }),
    [],
  );
  const morning = new Date(2026, 10, 13, 9, 0);
  const evening = new Date(2026, 10, 13, 21, 0);
  assert.equal(today.greeting("Alex Example", morning), "Good morning, Alex");
  assert.equal(today.greeting("", evening), "Good evening");
});

test("a deadline is danger when past, warning within a week, plain later", () => {
  const now = new Date(2026, 10, 13, 10, 0); // Friday
  assert.deepEqual(today.deadlineText("2026-11-11", now), {
    text: "Closed 11 Nov",
    tone: "danger",
  });
  assert.deepEqual(today.deadlineText("2026-11-13", now), {
    text: "Closes today",
    tone: "warning",
  });
  assert.deepEqual(today.deadlineText("2026-11-14", now), {
    text: "Closes tomorrow",
    tone: "warning",
  });
  assert.deepEqual(today.deadlineText("2026-11-17", now), {
    text: "Closes Tue",
    tone: "warning",
  });
  assert.deepEqual(today.deadlineText("2026-11-20", now), {
    text: "Closes 20 Nov",
    tone: "warning",
  });
  assert.deepEqual(today.deadlineText("2026-12-02", now), {
    text: "Closes 2 Dec",
  });
  assert.deepEqual(today.deadlineText("2027-01-05", now), {
    text: "Closes 5 Jan 2027",
  });
  assert.equal(today.deadlineText(null, now), null);
  assert.equal(today.dueThisWeek("2026-11-20", now), true);
  assert.equal(today.dueThisWeek("2026-11-21", now), false);
  assert.equal(today.dueThisWeek("2026-11-12", now), false);
  assert.equal(today.daysSince("2026-10-01T10:00:00Z", now), 43);
});

test("needs attention: due within a week and not Ready, then Ready with an open requirement", () => {
  const now = new Date(2026, 10, 13, 10, 0);
  const rows = [
    row("A", { deadline: "2026-11-15", missing: ["letter"] }),
    row("B", { deadline: "2026-12-15", missing: ["cv"] }),
    row("C", { ready: true, deadline: "2026-11-14" }),
    row("D", { ready: true, open_requirements: 1, missing: [] }),
    row("E", { deadline: "2026-11-10", missing: ["cv", "letter"] }),
  ];
  assert.deepEqual(
    today.needsAttention(rows, now).map((item) => item.id),
    ["A", "E", "D"],
  );
  // Each row names the one thing missing.
  assert.equal(today.missingText(rows[0]), "Missing: letter");
  assert.equal(today.missingText(rows[4]), "Missing: CV and letter");
  const held = row("F", {
    missing: ["requirement:r1"],
    open_requirements: 2,
  });
  assert.equal(
    today.missingText(held, { r1: "Reference letter" }),
    "Reference letter not done",
  );
  assert.equal(today.missingText(held), "2 requirements open");
  assert.equal(
    today.missingText(row("G", { open_requirements: 1 })),
    "1 requirement open",
  );
  assert.deepEqual(today.roleOf(row("H", { job: {} })), {
    title: "Untitled role",
    company: "",
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
      change("application_updated", { from: "shortlisted", to: "applied" }),
    ),
    "Shortlisted → Applied",
  );
  assert.equal(
    changes.changeDetail(
      change("triage_changed", { from: "new", to: "shortlisted" }),
    ),
    "New → Shortlisted",
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
