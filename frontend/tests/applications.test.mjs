import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const model = await import("../src/pages/applications/model.ts");
const { replyPlan, likelyChoice } =
  await import("../src/pages/applications/recording.ts");
const review = await import("../src/pages/review/model.ts");
const routes = await import("../src/shell/routes.ts");

const now = new Date(2026, 10, 13, 10, 0);
const app = (fields) => ({
  id: "a1",
  job_id: "j1",
  status: "shortlisted",
  outcome: null,
  ready: false,
  version: 1,
  note: "",
  questions: [],
  answers: {},
  ...fields,
});

test("Ready is a computed stage inside Shortlisted, with what is missing", () => {
  assert.equal(model.stageOf(app({})), "shortlisted");
  assert.equal(model.stageOf(app({ ready: true })), "ready");
  assert.equal(model.stageOf(app({ status: "offer" })), "offer");
  assert.deepEqual(
    model.stageCounts({
      total: 20,
      stage_counts: {
        shortlisted: 9,
        ready: 4,
        applied: 5,
        interview: 2,
        offer: 1,
        closed: 3,
      },
    }),
    {
      all: 20,
      shortlisted: 9,
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
    query("shortlisted"),
    "stage=shortlisted&sort=updated&limit=200",
  );
  assert.equal(query("ready"), "stage=ready&sort=updated&limit=200");
  assert.equal(query("all"), "sort=updated&limit=200");
  assert.equal(
    model
      .listQuery({ ...model.DEFAULTS, waiting: "1", q: "Data" }, 50, 100)
      .toString(),
    "q=Data&needs=reply_overdue&sort=updated&limit=50&offset=100",
  );
  assert.equal(
    model.missingText(app({ status: "shortlisted", missing: ["letter"] })),
    "Missing: letter",
  );
  assert.equal(
    model.missingText(
      app({
        status: "shortlisted",
        missing: ["cv", "requirement:r1"],
        requirements: [{ id: "r1", text: "Work permit" }],
      }),
    ),
    "Missing: CV, requirement “Work permit”",
  );
  assert.equal(
    model.missingText(app({ status: "applied", missing: ["cv"] })),
    "",
  );
  assert.equal(model.missingText(app({ missing: [] })), "");
});

test("addresses of the old Applications page open the stage they meant", () => {
  const hash = routes.canonicalHash;
  assert.equal(
    hash("#applications?status=draft&view=list"),
    "#applications?view=list&stage=shortlisted",
  );
  assert.equal(
    hash("#applications?status=applied&applied_until=2026-10-01"),
    "#applications?applied_until=2026-10-01&stage=applied",
  );
  assert.equal(
    hash("#applications?readiness=ready&sort=ready"),
    "#applications?sort=deadline&stage=ready",
  );
  assert.equal(
    hash("#applications?stage=preparing"),
    "#applications?stage=shortlisted",
  );
  // The removed Readiness filter is dropped.
  assert.equal(
    hash("#applications?stage=all&readiness=blocked"),
    "#applications?stage=all",
  );
  assert.equal(hash("#applications?stage=applied"), null);
  assert.equal(routes.routeOf("#applications?application=a1"), "review");
});

test("the employer's reply, or the wait, in words", () => {
  const sent = { applied_at: "2026-10-01T09:00:00+00:00" };
  assert.deepEqual(
    model.replyLine(app({ status: "applied", ...sent }), 30, now),
    {
      text: "No reply for 43 days",
      tone: "attention",
      badge: true,
    },
  );
  assert.equal(
    model.replyLine(app({ status: "applied", ...sent }), 45, now).tone,
    undefined,
  );
  assert.equal(
    model.replyLine(
      app({
        status: "interview",
        ...sent,
        last_reply: { kind: "interview", date: "2026-11-06" },
      }),
      30,
      now,
    ).text,
    "Interview · 6 Nov",
  );
  assert.equal(
    model.replyLine(
      app({
        status: "closed",
        outcome: "rejected",
        ...sent,
        last_reply: { kind: "rejection", date: "2026-10-13" },
      }),
      30,
      now,
    ).text,
    "Rejection · 13 Oct, after 12 days",
  );
  assert.equal(
    model.replyLine(
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
    model.replyLine(app({ status: "closed", outcome: "not_pursued" }), 30, now),
    { text: "Not pursued · not counted in Insights", quiet: true },
  );
  assert.equal(model.replyLine(app({}), 30, now).text, "");
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
      { kind: "cv", revisions: 1, complete: 1 },
      { kind: "letter", revisions: 1, complete: 1 },
    ]),
    "CV and letter uploaded",
  );
  assert.equal(
    kinds([
      { kind: "cv", revisions: 1, complete: 1 },
      { kind: "letter", revisions: 1, complete: 0 },
    ]),
    "CV uploaded, letter without PDF",
  );
  assert.equal(
    kinds([{ kind: "cv", revisions: 1, complete: 0 }]),
    "Waiting for the PDF",
  );
  assert.deepEqual(
    model.documentState(app({ preparation: [], missing: ["letter"] }))[1],
    { text: "Missing: letter", tone: "attention" },
  );
});

test("recording a reply: one update that moves the stage when the reply implies it", () => {
  const day = "2026-11-10";
  assert.deepEqual(replyPlan("applied", "interview", day, "Call"), {
    body: { reply: { kind: "interview", date: day, note: "Call" } },
    submit: "Save the interview",
    caption:
      "The application moves to Interview. The date stays correctable in its timeline.",
    note: true,
  });
  assert.match(
    replyPlan("interview", "interview", day, "").caption,
    /stage does not change/,
  );
  assert.deepEqual(replyPlan("interview", "interview", day, "").body, {
    reply: { kind: "interview", date: day },
  });
  assert.match(replyPlan("offer", "rejection", day, "").caption, /closes/);
  assert.match(
    replyPlan("closed", "offer", day, "", "no_response").caption,
    /moves to Offer/,
  );
  const silence = replyPlan("applied", "no_reply", day, "ignored");
  assert.deepEqual(silence.body, {
    status: "closed",
    outcome: "no_response",
    concluded_on: day,
  });
  assert.equal(silence.note, false);
  assert.match(
    replyPlan("applied", "other", day, "").caption,
    /does not change/,
  );
  assert.equal(likelyChoice("applied"), "interview");
  assert.equal(likelyChoice("interview"), "offer");
});

test("a CV or letter is complete with its PDF; a source pairs with it", () => {
  const tex = { name: "cv.tex", media_type: "application/x-tex", sha256: "s1" };
  const pdf = (built) => ({
    name: "cv.pdf",
    media_type: "application/pdf",
    sha256: "p1",
    source_sha256: built,
  });
  const cv = (files) => ({ kind: "cv", files });
  assert.match(review.incompleteReason(cv([])), /PDF/);
  assert.match(review.incompleteReason(cv([tex])), /PDF/);
  assert.equal(review.incompleteReason(cv([pdf(null)])), null);
  assert.equal(review.incompleteReason(cv([tex, pdf("s1")])), null);
  assert.equal(review.incompleteReason({ kind: "answers", files: [] }), null);
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
    { id: "a", kind: "cv", created_at: "1", previous_id: null },
    { id: "b", kind: "cv", created_at: "2", previous_id: "a" },
    { id: "c", kind: "letter", created_at: "3", previous_id: null },
  ];
  assert.equal(review.currentOf(revisions, "cv").id, "b");
  assert.equal(review.currentOf(revisions, "letter").id, "c");
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
  assert.equal(review.tabOf("inputs"), "documents");
  assert.equal(review.tabOf("nonsense"), "answers");
});

test("bulk actions are offered only when valid for every selected application", () => {
  const shortlisted = { status: "shortlisted", applied_at: null };
  const applied = { status: "applied", applied_at: "2026-11-01T10:00:00Z" };
  const interview = { ...applied, status: "interview" };
  const closed = { ...applied, status: "closed" };
  assert.deepEqual(model.bulkActions([]), []);
  assert.deepEqual(model.bulkActions([applied, interview, shortlisted]), [
    "close",
    "delete",
  ]);
  assert.deepEqual(model.bulkActions([applied, interview]), [
    "no_reply",
    "close",
    "delete",
  ]);
  assert.deepEqual(model.bulkActions([shortlisted]), ["close", "delete"]);
  assert.deepEqual(model.bulkActions([closed]), ["reopen", "delete"]);
  assert.deepEqual(model.bulkActions([closed, applied]), ["delete"]);
});

test("after Mark applied the next Ready application follows in Today's order", () => {
  const queue = [{ id: "a" }, { id: "b" }, { id: "c" }];
  assert.equal(review.nextReady(queue, "a").id, "b");
  assert.equal(review.nextReady(queue, "c").id, "a");
  assert.equal(review.nextReady(queue, "x").id, "a");
  assert.equal(review.nextReady([{ id: "a" }], "a"), null);
  assert.equal(review.nextReady([], "a"), null);
});
