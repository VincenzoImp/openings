import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of this module; it uses no React.
const model = await import("../src/pages/jobs/model.ts");

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
  posting: "",
  triage: "new",
  metadata: {},
  source: "linkedin",
  complete: true,
  application: null,
  application_count: 0,
  created_at: "2026-11-13T08:00:00Z",
  signals: signals(),
  dismissal: null,
  ...fields,
});
const filters = (fields = {}) => ({ ...model.DEFAULTS, ...fields });

test("each tab reads its queue, and only Dismissed filters by who dismissed", () => {
  const review = model.listQuery(filters(), 200);
  assert.equal(review.get("triage"), "new");
  assert.equal(review.get("sort"), "newest");
  assert.equal(review.get("limit"), "200");
  const dismissed = model.listQuery(
    filters({ section: "dismissed", dismissed_by: "agent" }),
    200,
  );
  assert.equal(dismissed.get("triage"), "dismissed");
  assert.equal(dismissed.get("sort"), "dismissed");
  assert.equal(dismissed.get("dismissed_by"), "agent");
  const all = model.listQuery(
    filters({
      section: "all",
      dismissed_by: "agent",
      sort: "dismissed",
      q: "rust",
    }),
    50,
  );
  assert.equal(all.get("triage"), null);
  assert.equal(all.get("dismissed_by"), null);
  assert.equal(all.get("sort"), "newest");
  assert.equal(all.get("q"), "rust");
  assert.equal(model.sectionOf("nonsense"), "new");
  // The tab names of earlier versions.
  assert.equal(model.sectionOf("review"), "new");
  assert.equal(model.sectionOf("shortlist"), "shortlisted");
  const counts = {
    all: 9,
    new: 4,
    shortlisted: 2,
    dismissed: 3,
    dismissed_by: { agent: 1, owner: 2, other: 0 },
  };
  assert.equal(model.sectionCount("new", counts), 4);
  assert.equal(model.sectionCount("shortlisted", counts), 2);
  assert.equal(model.sectionCount("all", counts), undefined);
});

test("signals read as tags; the owner's languages decide what needs attention", () => {
  const german = job({
    signals: signals({
      language: "de",
      required: [["de"], ["en", "fr"]],
      duplicate: { job_id: "j0", confidence: 0.93, tier: "high" },
      no_longer_listed: true,
    }),
    complete: false,
  });
  assert.deepEqual(model.signalTags(german), [
    { text: "No longer listed", tone: "danger" },
    { text: "Possible duplicate", tone: "info" },
    { text: "Requires German", tone: undefined },
    { text: "Requires English or French", tone: undefined },
    { text: "In German" },
    { text: "Text incomplete", tone: "attention" },
  ]);
  const own = new Set(["en", "it"]);
  assert.deepEqual(
    model.signalTags(german, { own }).map((tag) => [tag.text, tag.tone]),
    [
      ["No longer listed", "danger"],
      ["Possible duplicate", "info"],
      ["Requires German", "attention"],
      ["In German", undefined],
      ["Text incomplete", "attention"],
    ],
  );
  // A job in a language the owner works in shows nothing about it in a list.
  assert.deepEqual(model.signalTags(job(), { own }), []);
  assert.deepEqual(
    model.signalTags(job(), { own, full: true }).map((tag) => tag.text),
    ["In English"],
  );
});

test("the owner's languages come from the settings", () => {
  assert.deepEqual([...model.ownLanguages(["en", "it"])], ["en", "it"]);
  assert.equal(model.ownLanguages([]), null);
  assert.equal(model.ownLanguages(undefined), null);
});

test("the languages toggle is always asked for and says how many it hides", () => {
  assert.equal(
    model.listQuery(filters(), 200).get("hide_unspoken_required"),
    "false",
  );
  assert.equal(
    model
      .listQuery(filters({ hide_unspoken: "true" }), 200)
      .get("hide_unspoken_required"),
    "true",
  );
  // Off: the list holds them all; on: the list holds the rest.
  assert.equal(
    model.unspokenLine({ count: 3, hidden: false }, 40),
    "would hide 3 of 40",
  );
  assert.equal(
    model.unspokenLine({ count: 3, hidden: true }, 37),
    "hides 3 of 40",
  );
  assert.equal(model.unspokenLine(undefined, 40), "");
});

test("a dismissal says who made it, when and why", () => {
  const at = "2026-11-13T09:12:00";
  const by = (kind, extra = {}) => ({
    kind,
    id: null,
    name: null,
    token_kind: null,
    label: "",
    ...extra,
  });
  const dismissed = (dismissal) =>
    job({
      triage: "dismissed",
      dismissal: { at, reason: "", ...dismissal },
    });
  assert.equal(
    model.dismissalLine(
      dismissed({ by: by("system"), category: "other" }),
      now,
    ),
    "Dismissed by System · Today 09:12",
  );
  assert.equal(
    model.dismissedBy(
      dismissed({
        by: by("token", { name: "career-agent", token_kind: "agent" }),
        category: "agent",
      }),
    ),
    "career-agent",
  );
  assert.equal(
    model.dismissalLine(dismissed({ by: by("owner"), category: "owner" }), now),
    "Dismissed by you · Today 09:12",
  );
  assert.equal(
    model.dismissedBy(dismissed({ by: by("unknown"), category: "other" })),
    "Not recorded",
  );
});

test("where a job came from and where it is now", () => {
  assert.equal(model.sourceLabel(job()), "LinkedIn");
  assert.equal(
    model.sourceLabel(
      job({
        source: undefined,
        metadata: { ats: "greenhouse", source: "greenhouse" },
      }),
    ),
    "Greenhouse board",
  );
  assert.equal(
    model.sourceLabel(job({ source: undefined, metadata: {} })),
    "Added by hand",
  );
  // Found on LinkedIn today, at the local time of the machine.
  assert.match(
    model.foundLine(job({ created_at: "2026-11-13T09:30:00" }), now),
    /^LinkedIn · Today \d\d:\d\d$/,
  );
  assert.deepEqual(model.placeTag(job()), { text: "New" });
  assert.deepEqual(model.placeTag(job({ triage: "shortlisted" })), {
    text: "Shortlisted",
  });
  assert.deepEqual(
    model.placeTag(
      job({
        application: { id: "a1", status: "applied", outcome: null, version: 1 },
      }),
    ),
    { text: "Applied", tone: "info" },
  );
});

test("a job that leaves its list gives way to the next row, or the previous one", () => {
  const ids = ["a", "b", "c"];
  assert.equal(model.neighbour(ids, "a"), "b");
  assert.equal(model.neighbour(ids, "b"), "c");
  assert.equal(model.neighbour(ids, "c"), "b");
  assert.equal(model.neighbour(["a"], "a"), "");
  assert.equal(model.neighbour(ids, "gone"), "a");
  assert.deepEqual(model.QUEUE_SECTIONS, ["new", "shortlisted"]);
});
