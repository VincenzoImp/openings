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
  welcome: [],
  duplicate_checked: true,
  duplicate: null,
  no_longer_listed: false,
  unlisted_at: null,
  rules: [],
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
  triage: "inbox",
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
  assert.equal(review.get("queue"), "inbox");
  assert.equal(review.get("sort"), "newest");
  assert.equal(review.get("limit"), "200");
  const dismissed = model.listQuery(
    filters({ section: "dismissed", dismissed_by: "rule", rule_id: "r1" }),
    200,
  );
  assert.equal(dismissed.get("queue"), "dismissed");
  assert.equal(dismissed.get("sort"), "dismissed");
  assert.equal(dismissed.get("dismissed_by"), "rule");
  assert.equal(dismissed.get("rule_id"), "r1");
  const all = model.listQuery(
    filters({
      section: "all",
      dismissed_by: "rule",
      sort: "dismissed",
      q: "rust",
    }),
    50,
  );
  assert.equal(all.get("queue"), null);
  assert.equal(all.get("dismissed_by"), null);
  assert.equal(all.get("sort"), "newest");
  assert.equal(all.get("q"), "rust");
  assert.equal(model.sectionOf("nonsense"), "review");
  const counts = {
    all: 9,
    inbox: 4,
    shortlist: 2,
    applications: 1,
    dismissed: 3,
    dismissed_by: { rule: 1, agent: 1, owner: 1, other: 0 },
  };
  assert.equal(model.sectionCount("review", counts), 4);
  assert.equal(model.sectionCount("all", counts), undefined);
});

test("signals read as tags; the owner's languages decide what needs attention", () => {
  const german = job({
    signals: signals({
      language: "de",
      required: [["de"], ["en", "fr"]],
      welcome: ["it"],
      duplicate: { job_id: "j0", confidence: 0.93, tier: "high" },
      no_longer_listed: true,
      rules: [{ item_id: "r1", label: "Mention duplicates", action: "flag" }],
    }),
    complete: false,
  });
  assert.deepEqual(model.signalTags(german), [
    { text: "No longer listed", tone: "danger" },
    { text: "Likely duplicate 0.93", tone: "info" },
    { text: "Requires German", tone: undefined },
    { text: "Requires English or French", tone: undefined },
    { text: "In German" },
    { text: "Italian welcome" },
    { text: "Flagged: Mention duplicates", tone: "info" },
    { text: "Text incomplete", tone: "attention" },
  ]);
  const own = new Set(["en", "it"]);
  assert.deepEqual(
    model.signalTags(german, { own }).map((tag) => [tag.text, tag.tone]),
    [
      ["No longer listed", "danger"],
      ["Likely duplicate 0.93", "info"],
      ["Requires German", "attention"],
      ["In German", undefined],
      ["Italian welcome", undefined],
      ["Flagged: Mention duplicates", "info"],
      ["Text incomplete", "attention"],
    ],
  );
  // A job in a language the owner works in shows nothing about it in a list.
  assert.deepEqual(model.signalTags(job(), { own }), []);
  assert.deepEqual(
    model.signalTags(job(), { own, full: true }).map((tag) => tag.text),
    ["Posting in English"],
  );
});

test("the owner's languages come from a confirmed rule of the policy", () => {
  const item = (fields) => ({
    confirmed: true,
    rule: {
      signal: "language_required",
      condition: { operator: "not_in", value: ["English", "it"] },
      action: "dismiss",
    },
    ...fields,
  });
  assert.deepEqual([...model.ownLanguages([item({})])], ["en", "it"]);
  assert.equal(model.ownLanguages([item({ confirmed: false })]), null);
  assert.equal(model.ownLanguages([]), null);
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
      dismissal: { at, reason: "", rule: null, ...dismissal },
    });
  assert.equal(
    model.dismissalLine(
      dismissed({
        by: by("system"),
        category: "rule",
        rule: { item_id: "r1", label: "Languages outside my list" },
      }),
      now,
    ),
    "Dismissed by the rule “Languages outside my list” · Today 09:12",
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
  assert.deepEqual(model.placeTag(job()), { text: "To review" });
  assert.deepEqual(model.placeTag(job({ triage: "saved" })), {
    text: "Shortlist",
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
