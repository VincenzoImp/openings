import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const today = await import("../src/screens/today/model.ts");
const applications = await import("../src/screens/applications/model.ts");

const row = (id, fields = {}) => ({
  id,
  stage: "shortlisted",
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

test("Today and Applications say a deadline in the same words", () => {
  const now = new Date(2026, 10, 13, 10, 0); // Friday
  const label = (day) => applications.deadlineLabel(day, now);
  assert.deepEqual(label("2026-11-11"), {
    text: "Overdue 2 days",
    tone: "danger",
  });
  assert.deepEqual(label("2026-11-13"), { text: "Due today", tone: "warning" });
  assert.deepEqual(label("2026-11-14"), {
    text: "Due tomorrow",
    tone: "warning",
  });
  assert.deepEqual(label("2026-11-17"), { text: "Due Tue" });
  assert.deepEqual(label("2026-11-20"), { text: "Due 20 Nov" });
  assert.deepEqual(label("2027-01-05"), { text: "Due 5 Jan 2027" });
  assert.equal(label(null), null);
  // Never "Closed": that is a stage, not a deadline.
  for (const day of ["2026-11-01", "2026-11-12", "2026-11-13"])
    assert.doesNotMatch(label(day).text, /Clos/);
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
