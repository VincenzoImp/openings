import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const model = await import("../src/screens/applications/model.ts");
const filters = await import("../src/screens/applications/filters.ts");

// Friday 13 November 2026, 10:00 local time.
const now = new Date(2026, 10, 13, 10, 0);
const app = (fields) => ({
  id: "a1",
  stage: "shortlisted",
  ready: false,
  missing: [],
  updated_at: "2026-11-01T10:00:00Z",
  required_documents: ["cv", "letter"],
  requirements: [],
  ...fields,
});

test("Ready is a computed stage inside Shortlisted", () => {
  assert.equal(model.stageOf(app({})), "shortlisted");
  assert.equal(model.stageOf(app({ ready: true })), "ready");
  assert.equal(model.stageOf(app({ stage: "offer" })), "offer");
  assert.equal(model.stageOf(app({ stage: "closed", ready: true })), "closed");
});

test("each row has one status phrase that follows its stage", () => {
  const phrase = (fields) => model.statusPhrase(app(fields), 45, now);
  assert.deepEqual(phrase({ missing: ["letter"] }), {
    text: "Missing: letter",
  });
  assert.deepEqual(phrase({ missing: ["cv", "letter", "requirement:r1"] }), {
    text: "Missing: CV, letter, 1 requirement",
  });
  assert.deepEqual(phrase({ ready: true, deadline: "2026-11-16" }), {
    text: "Ready · due Mon",
    tone: "warning",
  });
  assert.deepEqual(phrase({ ready: true, deadline: "2026-12-01" }), {
    text: "Ready · due 1 Dec",
  });
  assert.deepEqual(phrase({ ready: true, deadline: "2026-11-10" }), {
    text: "Ready · overdue 3 days",
    tone: "danger",
  });
  assert.deepEqual(
    phrase({ stage: "applied", applied_at: "2026-10-12T09:00:00" }),
    { text: "Applied 12 Oct · no reply 32 days" },
  );
  assert.deepEqual(
    phrase({ stage: "applied", applied_at: "2026-09-12T09:00:00" }),
    { text: "Applied 12 Sep · no reply 62 days", tone: "warning" },
  );
  assert.deepEqual(
    phrase({
      stage: "interview",
      applied_at: "2026-10-01T09:00:00",
      last_reply: { kind: "interview", date: "2026-11-04" },
    }),
    { text: "Interview 4 Nov" },
  );
  assert.deepEqual(phrase({ stage: "closed", outcome: "rejected" }), {
    text: "Closed · rejected",
  });
  assert.deepEqual(phrase({ stage: "closed", outcome: "no_response" }), {
    text: "Closed · no reply",
  });
});

test("Needs action: Ready by deadline, dated Shortlisted, overdue, then the rest", () => {
  const rows = [
    app({ id: "rest", stage: "interview", updated_at: "2026-11-12T00:00Z" }),
    app({ id: "late", stage: "applied", applied_at: "2026-08-01T00:00Z" }),
    app({ id: "dated", deadline: "2026-11-20" }),
    app({ id: "ready-late", ready: true, deadline: "2026-12-01" }),
    app({ id: "ready-soon", ready: true, deadline: "2026-11-15" }),
    app({ id: "plain", updated_at: "2026-11-02T00:00Z" }),
  ];
  assert.deepEqual(
    model.sortApplications(rows, "needs", 45, now).map((row) => row.id),
    ["ready-soon", "ready-late", "dated", "late", "rest", "plain"],
  );
  assert.deepEqual(
    rows.map((row) => model.needsRank(row, 45, now)),
    [3, 2, 1, 0, 0, 3],
  );
  assert.deepEqual(
    model.sortApplications(rows, "updated", 45, now)[0].id,
    "rest",
  );
});

test("the bulk bar offers only the actions valid for the whole selection", () => {
  const sent = app({ stage: "applied", applied_at: "2026-10-01T00:00Z" });
  const draft = app({});
  const closed = app({ stage: "closed", outcome: "rejected" });
  assert.deepEqual(model.bulkActions([sent]), [
    "no_reply",
    "close",
    "priority",
  ]);
  assert.deepEqual(model.bulkActions([sent, draft]), ["close", "priority"]);
  assert.deepEqual(model.bulkActions([closed]), ["reopen"]);
  assert.deepEqual(model.bulkActions([closed, sent]), []);
  assert.equal(model.reopenStage(sent), "applied");
  assert.equal(model.reopenStage(draft), "shortlisted");
});

test("what is missing before Ready, and the first thing to do", () => {
  const items = model.checklist(
    app({
      required_documents: ["cv"],
      missing: ["cv", "requirement:r2"],
      requirements: [
        { id: "r1", text: "Send it in English", resolved: true },
        { id: "r2", text: "Two references", resolved: false },
      ],
    }),
  );
  assert.deepEqual(
    items.map((item) => [item.key, item.state, item.detail]),
    [
      ["cv", "missing", undefined],
      ["letter", "not_needed", undefined],
      ["requirements", "missing", "1/2 done"],
    ],
  );
  assert.equal(model.firstMissing(app({ missing: ["letter"] })), "letter");
  assert.equal(
    model.firstMissing(app({ missing: ["requirement:x"] })),
    "requirement",
  );
  assert.equal(model.firstMissing(app({})), null);
});

test("a reply says what it does to the stage", () => {
  assert.equal(
    model.replyEffect("applied", "interview"),
    "The application moves to Interview.",
  );
  assert.equal(
    model.replyEffect("interview", "offer"),
    "The application moves to Offer.",
  );
  assert.equal(
    model.replyEffect("offer", "rejection"),
    "A rejection closes the application.",
  );
  assert.equal(
    model.replyEffect("interview", "interview"),
    "The stage does not change.",
  );
  assert.equal(
    model.replyEffect("closed", "interview", "no_response"),
    "The application moves to Interview.",
  );
  assert.equal(model.likelyReply("applied"), "interview");
  assert.equal(model.likelyReply("interview"), "offer");
});

test("the send queue: place, next after Mark applied, the last one", () => {
  const queue = [{ id: "a" }, { id: "b" }, { id: "c" }];
  assert.deepEqual(model.queuePlace(queue, "b"), {
    position: 2,
    total: 3,
    previous: { id: "a" },
    next: { id: "c" },
  });
  assert.equal(model.queuePlace(queue, "x"), null);
  assert.equal(model.nextReady(queue, "b").id, "c");
  assert.equal(model.nextReady(queue, "c").id, "a");
  assert.equal(model.nextReady(queue, "x").id, "a");
  assert.equal(model.nextReady([{ id: "a" }], "a"), null);
});

test("sent and closed applications lead with a status line", () => {
  assert.deepEqual(
    model.followUpLine(
      app({ stage: "applied", applied_at: "2026-10-12T09:00:00" }),
      45,
      now,
    ),
    { text: "Applied 12 Oct · no reply for 32 days" },
  );
  assert.equal(
    model.closedSummary(
      app({
        stage: "closed",
        outcome: "rejected",
        last_reply: { kind: "rejection", date: "2026-11-02" },
        replies: [
          { kind: "interview", date: "2026-10-20" },
          { kind: "rejection", date: "2026-11-02" },
        ],
      }),
      now,
    ),
    "Rejected on 2 Nov after interview",
  );
  assert.equal(
    model.closedSummary(app({ stage: "closed", outcome: "not_pursued" }), now),
    "Not pursued · never sent",
  );
});

test("history entries in words; field changes only with all changes", () => {
  const event = (kind, payload = {}) => ({
    type: "event",
    kind: "event",
    event: { kind, payload },
  });
  assert.deepEqual(
    model.historyLine(
      event("application_updated", { from: "shortlisted", to: "applied" }),
    ),
    { text: "Marked applied", main: true },
  );
  assert.deepEqual(
    model.historyLine(
      event("application_updated", { from: "closed", to: "applied" }),
    ),
    { text: "Reopened as Applied", main: true },
  );
  assert.deepEqual(
    model.historyLine(
      event("application_updated", { fields: ["deadline", "priority"] }),
    ),
    { text: "Changed deadline, priority", main: false },
  );
  assert.deepEqual(
    model.historyLine(
      {
        type: "event",
        kind: "reply",
        event: {
          kind: "reply_added",
          payload: { from: "applied", to: "interview" },
        },
      },
      { kind: "interview", date: "2026-11-04", note: "Call on Monday" },
      now,
    ),
    {
      text: "Interview invitation · 4 Nov · moved to Interview",
      detail: "Call on Monday",
      main: true,
    },
  );
  assert.equal(model.actorPhrase("owner"), "by you");
  assert.equal(model.actorPhrase("agent:career-agent"), "by career-agent");
  assert.equal(model.actorPhrase(null), "");
});

test("the list's filters live in its address, defaults left out", () => {
  const read = (query) => filters.readFilters(new URLSearchParams(query));
  const value = read("stage=applied&waiting=1&priority=2&sort=bogus");
  assert.equal(value.stage, "applied");
  assert.equal(value.waiting, true);
  assert.equal(value.sort, "needs");
  assert.deepEqual(filters.writeFilters(value), {
    stage: "applied",
    priority: "2",
    waiting: "1",
  });
  assert.equal(read("section=stats").stats, true);
  assert.equal(read("stage=draft").stage, "all");
  assert.deepEqual(filters.writeFilters(filters.cleared(value)), {
    stage: "applied",
  });
  const row = (fields) => ({ ...app(fields), job: { source: "LinkedIn" } });
  assert.equal(
    filters.passes(row({ deadline: "2026-11-18" }), read("deadline=week"), now),
    true,
  );
  assert.equal(
    filters.passes(row({ deadline: "2026-11-10" }), read("deadline=week"), now),
    false,
  );
  assert.equal(filters.passes(row({}), read("source=Indeed"), now), false);
  assert.deepEqual(
    filters
      .filterChips(read("waiting=1&outcome=rejected"), 45)
      .map((chip) => [chip.field, chip.value]),
    [
      ["Waiting", "no reply for over 45 days"],
      ["Outcome", "Rejected"],
    ],
  );
});

test("the current revision of a kind is the one nothing replaces", () => {
  const revisions = [
    { id: "1", kind: "cv", created_at: "2026-11-01" },
    { id: "2", kind: "cv", created_at: "2026-11-02", previous_id: "1" },
    { id: "3", kind: "letter", created_at: "2026-11-03" },
  ];
  assert.equal(model.currentOf(revisions, "cv").id, "2");
  assert.equal(model.currentOf(revisions, "letter").id, "3");
  assert.equal(model.currentOf(revisions, "other"), null);
});

test("where the stage is already said, a Ready row reads only its deadline", () => {
  const shown = (fields) =>
    model.statusPhrase(app(fields), 45, now, { stageShown: true });
  assert.deepEqual(shown({ ready: true, deadline: "2026-11-16" }), {
    text: "Due Mon",
    tone: "warning",
  });
  assert.deepEqual(shown({ ready: true }), { text: "" });
  assert.deepEqual(shown({ missing: ["letter"] }), { text: "Missing: letter" });
  assert.equal(model.NEEDS_GROUPS[2], "Waiting for a reply");
});
