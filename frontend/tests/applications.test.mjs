import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const model = await import("../src/pages/applications/model.ts");
const { respondPlan, likelyChoice } =
  await import("../src/pages/applications/recording.ts");
const review = await import("../src/pages/review/model.ts");
const staleness = await import("../src/library/staleness.ts");
const routes = await import("../src/shell/routes.ts");

const now = new Date(2026, 10, 13, 10, 0);
const app = (fields) => ({
  id: "a1",
  job_id: "j1",
  status: "draft",
  outcome: null,
  ready_at: null,
  version: 1,
  note: "",
  questions: [],
  answers: {},
  ...fields,
});

test("Ready is a stage of its own: Preparing counts only the others", () => {
  assert.equal(model.stageOf(app({})), "preparing");
  assert.equal(model.stageOf(app({ ready_at: "2026-11-01" })), "ready");
  assert.equal(model.stageOf(app({ status: "offer" })), "offer");
  assert.deepEqual(
    model.stageCounts({
      total: 20,
      stage_counts: { draft: 9, applied: 5, interview: 2, offer: 1, closed: 3 },
      ready_count: 4,
    }),
    {
      all: 20,
      preparing: 5,
      ready: 4,
      applied: 5,
      interview: 2,
      offer: 1,
      closed: 3,
    },
  );
  const query = (stage) =>
    model.listQuery({ ...model.DEFAULTS, stage }, 200).toString();
  assert.equal(
    query("preparing"),
    "status=draft&ready=false&sort=updated&limit=200",
  );
  assert.equal(
    query("ready"),
    "status=draft&ready=true&sort=updated&limit=200",
  );
  assert.equal(query("closed"), "status=closed&sort=updated&limit=200");
  assert.equal(
    model
      .listQuery({ ...model.DEFAULTS, waiting: "1", q: "Data" }, 50, 100)
      .toString(),
    "q=Data&no_reply_due=true&sort=updated&limit=50&offset=100",
  );
});

test("addresses of the old Applications page open the stage they meant", () => {
  const hash = routes.canonicalHash;
  assert.equal(
    hash("#applications?status=draft&view=list"),
    "#applications?view=list&stage=preparing",
  );
  assert.equal(
    hash("#applications?status=applied&applied_until=2026-10-01"),
    "#applications?applied_until=2026-10-01&stage=applied",
  );
  assert.equal(
    hash("#applications?readiness=ready&sort=ready"),
    "#applications?sort=ready&stage=ready",
  );
  // A readiness filter inside another stage stays a filter.
  assert.equal(hash("#applications?stage=all&readiness=blocked"), null);
  assert.equal(hash("#applications?stage=applied"), null);
  assert.equal(routes.routeOf("#applications?application=a1"), "review");
});

test("the employer's answer, or the wait, in words", () => {
  const sent = { applied_at: "2026-10-01T09:00:00+00:00" };
  assert.deepEqual(
    model.responseLine(app({ status: "applied", ...sent }), 30, now),
    {
      text: "No reply for 43 days",
      tone: "attention",
      badge: true,
    },
  );
  assert.equal(
    model.responseLine(app({ status: "applied", ...sent }), 45, now).tone,
    undefined,
  );
  assert.equal(
    model.responseLine(
      app({
        status: "interview",
        ...sent,
        last_response: { kind: "interview", date: "2026-11-06" },
      }),
      30,
      now,
    ).text,
    "Interview · 6 Nov",
  );
  assert.equal(
    model.responseLine(
      app({
        status: "closed",
        outcome: "rejected",
        ...sent,
        last_response: { kind: "rejection", date: "2026-10-13" },
      }),
      30,
      now,
    ).text,
    "Rejection · 13 Oct, after 12 days",
  );
  assert.equal(
    model.responseLine(
      app({
        status: "closed",
        outcome: "no_response",
        concluded_on: "2026-11-10",
        ...sent,
      }),
      30,
      now,
    ).text,
    "No reply · closed 10 Nov after 40 days",
  );
  assert.deepEqual(
    model.responseLine(
      app({ status: "closed", outcome: "not_pursued" }),
      30,
      now,
    ),
    { text: "Not pursued · not counted in Insights", quiet: true },
  );
  assert.equal(model.responseLine(app({}), 30, now).text, "");
});

test("plan tags and the state of the documents", () => {
  assert.deepEqual(
    model.planTags(
      app({ priority: 1, deadline: "2026-11-14", blocking_requirements: 2 }),
      now,
    ),
    [
      { text: "P1", tone: "attention" },
      { text: "Closes tomorrow", tone: "danger" },
      { text: "2 blocking requirements", tone: "danger" },
    ],
  );
  const kinds = (items) =>
    model.documentState(app({ preparation: items }))[0].text;
  assert.equal(kinds([]), "None");
  assert.equal(
    kinds([
      { kind: "resume", revisions: 1, pdf: 1, approved: 1 },
      { kind: "cover_letter", revisions: 1, pdf: 1, approved: 1 },
    ]),
    "CV and letter approved",
  );
  assert.equal(
    kinds([
      { kind: "resume", revisions: 1, pdf: 1, approved: 1 },
      { kind: "cover_letter", revisions: 1, pdf: 0, approved: 0 },
    ]),
    "CV approved, letter not yet",
  );
  assert.equal(
    kinds([{ kind: "resume", revisions: 1, pdf: 0, approved: 0 }]),
    "Written, without PDF",
  );
  assert.equal(
    model.documentState(app({ preparation: [], stale_inputs: ["profile"] }))[1]
      .tone,
    "attention",
  );
});

test("what changed since the documents were written, in words", () => {
  const change = (fields) => ({
    id: null,
    label: "",
    state: "changed",
    frozen_version: 1,
    current_version: 2,
    ...fields,
  });
  const summary = change({ input: "profile", id: "summary", label: "Summary" });
  const authorization = change({
    input: "policy",
    id: "p1",
    label: "Work authorization",
    section: "eligibility",
  });
  const page = change({
    input: "policy",
    id: "p2",
    label: "One page",
    section: "writing",
    state: "added",
  });
  const template = change({ input: "template", id: "t1", label: "MASTER CV" });
  assert.deepEqual(
    [summary, authorization, template].map((item) =>
      staleness.changeName(item),
    ),
    ["Profile summary", "Policy “Work authorization”", "Template “MASTER CV”"],
  );
  assert.deepEqual(
    [summary, authorization, page, template].map(staleness.changeState),
    [
      "changed",
      "changed · Facts employers ask about",
      "added · Rules for your documents",
      "changed · version 1 → 2",
    ],
  );
  const whole = change({ input: "profile", label: "Profile" });
  assert.equal(staleness.changeName(whole), "Profile");
  assert.equal(staleness.changeState(whole), "changed · compared as a whole");
  assert.equal(
    staleness.changeName(
      change({ input: "claim", id: "c1", label: "x".repeat(60) }),
      32,
    ),
    `Claim “${"x".repeat(31)}…”`,
  );

  // The list names the first change and counts the rest.
  const detail = (fields) =>
    staleness.staleDetail(app({ stale_inputs: ["profile"], ...fields }));
  assert.equal(
    detail({ stale_changes: [summary], stale_changes_total: 1 }),
    "Profile summary",
  );
  assert.equal(
    detail({ stale_changes: [summary, authorization], stale_changes_total: 4 }),
    "Profile summary and 3 more",
  );
  assert.equal(detail({}), "");
  assert.equal(
    model.documentState(
      app({
        preparation: [],
        stale_inputs: ["profile"],
        stale_changes: [summary],
      }),
    )[1].text,
    "Inputs changed",
  );

  // A rule for the CV concerns the CV only; notes say what was not compared.
  const report = {
    documents: [
      {
        kind: "resume",
        context_id: "c",
        changes: [summary, page],
        comparison: { profile: "parts", policy: "items" },
      },
      {
        kind: "cover_letter",
        context_id: "c",
        changes: [summary],
        comparison: { profile: "parts", policy: "not_frozen" },
      },
    ],
  };
  const kinds = { resume: "CV", cover_letter: "Letter" };
  assert.equal(staleness.concerned(page, report, kinds), "CV");
  assert.equal(staleness.concerned(summary, report, kinds), "");
  assert.equal(staleness.comparisonNotes(report).length, 1);
  assert.match(
    staleness.comparisonNotes(report)[0],
    /before the policy existed/,
  );
});

test("recording an answer: a stage change with its response, or a response alone", () => {
  const day = "2026-11-10";
  assert.deepEqual(respondPlan("applied", "interview", day, "Call"), {
    call: "update",
    body: { status: "interview", response_date: day, response_note: "Call" },
    submit: "Save and move to Interview",
    caption:
      "The application moves to Interview. The date stays correctable in its timeline.",
    note: true,
  });
  assert.equal(respondPlan("interview", "interview", day, "").call, "add");
  assert.deepEqual(respondPlan("interview", "interview", day, "").body, {
    kind: "interview",
    date: day,
    note: "",
  });
  assert.deepEqual(respondPlan("offer", "rejection", day, "").body, {
    status: "closed",
    outcome: "rejected",
    response_date: day,
  });
  const silence = respondPlan("applied", "no_reply", day, "ignored");
  assert.deepEqual(silence.body, {
    status: "closed",
    outcome: "no_response",
    concluded_on: day,
  });
  assert.equal(silence.note, false);
  assert.equal(respondPlan("applied", "other", day, "").call, "add");
  assert.equal(likelyChoice("applied"), "interview");
  assert.equal(likelyChoice("interview"), "offer");
});

test("a CV or letter is approved with its source and the PDF built from it", () => {
  const tex = { name: "cv.tex", media_type: "application/x-tex", sha256: "s1" };
  const pdf = (built) => ({
    name: "cv.pdf",
    media_type: "application/pdf",
    sha256: "p1",
    source_sha256: built,
  });
  const cv = (files) => ({ kind: "resume", files });
  assert.match(review.approvalBlock(cv([])), /source/);
  assert.match(review.approvalBlock(cv([tex])), /PDF/);
  assert.equal(review.approvalBlock(cv([tex, pdf("s1")])), null);
  assert.equal(review.approvalBlock({ kind: "answers", files: [] }), null);
  assert.equal(review.sourceAndPdf(cv([tex, pdf("s1")])).pairing, "matches");
  assert.equal(review.sourceAndPdf(cv([tex, pdf(null)])).pairing, "unnamed");
  assert.equal(review.sourceAndPdf(cv([tex, pdf("s2")])).pairing, "other");
  assert.equal(review.sourceAndPdf(cv([tex])).pairing, null);
  // Only TeX is a source, as the server reads it.
  assert.equal(
    review.isSource({ name: "notes.md", media_type: "text/markdown" }),
    false,
  );
  assert.equal(
    review.isSource({ name: "cv", media_type: "text/x-tex; charset=utf-8" }),
    true,
  );
});

test("the review page: current revisions, before you send, the queue and old tabs", () => {
  const revisions = [
    { id: "a", kind: "resume", created_at: "1", previous_id: null },
    { id: "b", kind: "resume", created_at: "2", previous_id: "a" },
    { id: "c", kind: "cover_letter", created_at: "3", previous_id: null },
  ];
  assert.equal(review.currentOf(revisions, "resume").id, "b");
  assert.equal(review.currentOf(revisions, "cover_letter").id, "c");
  assert.equal(review.currentOf(revisions, "answers"), null);
  const notices = review.beforeYouSend(
    app({
      questions: [
        { id: "q1", label: "Salary", required: true },
        { id: "q2", label: "Why?", required: false },
      ],
      answers: {},
      requirements: [
        {
          id: "r",
          kind: "deadline",
          text: "Before Friday",
          blocking: false,
          resolved: false,
        },
      ],
    }),
  );
  assert.deepEqual(
    notices.map((notice) => notice.tab),
    ["answers", "requirements"],
  );
  assert.match(notices[0].text, /"Salary"/);
  assert.deepEqual(review.beforeYouSend(app({ status: "applied" })), []);
  const queue = [{ id: "x" }, { id: "y" }, { id: "z" }];
  assert.deepEqual(review.queuePlace(queue, "y"), {
    position: 2,
    total: 3,
    next: { id: "z" },
  });
  assert.equal(review.queuePlace(queue, "w"), null);
  assert.equal(review.tabOf("history"), "timeline");
  assert.equal(review.tabOf("details"), "details");
  assert.equal(review.tabOf("nonsense"), "answers");
});
