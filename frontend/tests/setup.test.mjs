import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const { isNewWorkspace } = await import("../src/shell/setup.ts");
const model = await import("../src/pages/setup/model.ts");
const preferences = await import("../src/pages/preferences/model.ts");

const blank = {
  profile: { name: "", headline: "", location: "", email: "" },
  sections: [
    { section: "looking_for", items: [] },
    { section: "ruled_out", items: [] },
  ],
  noReply: { days: 30, source: "default" },
  sources: 0,
  tokens: [],
  entries: 0,
  claims: 0,
  templates: 0,
  applications: 0,
};
const token = (name, created_at, last_used_at = null) => ({
  name,
  kind: "agent",
  created_at,
  last_used_at,
});

test("a workspace is new only while it has no name, entry, source, token or job", () => {
  const empty = { name: " ", entries: 0, sources: 0, tokens: 0, jobs: 0 };
  assert.equal(isNewWorkspace(empty), true);
  for (const change of [
    { name: "Alex" },
    { entries: 1 },
    { sources: 1 },
    { tokens: 1 },
    { jobs: 1 },
  ])
    assert.equal(isNewWorkspace({ ...empty, ...change }), false);
});

test("the agent is connected once one of its tokens made a call", () => {
  assert.deepEqual(model.connection([]), { state: "todo", token: null });
  const waiting = model.connection([
    token("old", "2026-11-01T00:00:00Z"),
    token("new", "2026-11-02T00:00:00Z"),
  ]);
  assert.equal(waiting.state, "waiting");
  assert.equal(waiting.token.name, "new");
  const done = model.connection([
    token("first", "2026-11-01T00:00:00Z", "2026-11-03T00:00:00Z"),
    token("second", "2026-11-02T00:00:00Z", "2026-11-04T00:00:00Z"),
    token("unused", "2026-11-05T00:00:00Z"),
  ]);
  assert.equal(done.state, "done");
  assert.equal(done.token.name, "second");
});

test("a new workspace starts by connecting the agent, with nothing done", () => {
  const steps = model.steps(blank);
  assert.equal(steps.agent.line, "Not started");
  assert.equal(steps.record.line, "Not started");
  assert.equal(steps.next.line, "After the record");
  assert.equal(model.firstStep(blank), "agent");
  assert.equal(model.setupComplete(blank), false);
  assert.ok(model.recordItems(blank).every((item) => item.state === "todo"));
});

test("the record counts each part from the workspace", () => {
  const facts = {
    ...blank,
    profile: { ...blank.profile, name: "Alex Morgan", headline: "Engineer" },
    sections: [
      { section: "looking_for", items: [{ text: "a" }, { text: "b" }] },
      { section: "ruled_out", items: [{ text: "c" }] },
    ],
    noReply: { days: 45, source: "settings" },
    sources: 1,
    entries: 9,
    claims: 1,
    templates: 0,
  };
  const items = Object.fromEntries(
    model.recordItems(facts).map((item) => [item.id, item]),
  );
  assert.equal(items.profile.state, "done");
  assert.equal(items.profile.meta, "Alex Morgan · Engineer");
  assert.equal(items.preferences.state, "done");
  assert.equal(
    items.preferences.meta,
    "2 statements on what you look for · 1 you rule out · no reply after 45 days",
  );
  assert.equal(items.searches.meta, "1 saved search or company board");
  assert.equal(items.entries.meta.startsWith("9 entries"), true);
  assert.equal(items.claims.meta.startsWith("1 statement "), true);
  assert.equal(items.templates.state, "todo");
  assert.equal(model.steps(facts).record.line, "In progress · 5 of 6");
  // The record is not done and the agent is not connected: the agent first.
  assert.equal(model.firstStep(facts), "agent");
  const connected = {
    ...facts,
    tokens: [
      token("career-agent", "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"),
    ],
  };
  assert.equal(model.firstStep(connected), "record");
  const complete = { ...connected, templates: 2, applications: 3 };
  assert.equal(model.firstStep(complete), "next");
  assert.equal(model.setupComplete(complete), true);
  assert.equal(model.steps(complete).next.line, "3 applications");
});

test("preferences are in progress until they say what you look for and the no-reply period", () => {
  const withStatement = {
    ...blank,
    sections: [
      { section: "looking_for", items: [{ text: "Backend roles" }] },
      { section: "ruled_out", items: [] },
    ],
  };
  const item = (facts) =>
    model.recordItems(facts).find((entry) => entry.id === "preferences");
  assert.equal(item(withStatement).state, "progress");
  assert.match(item(withStatement).meta, /no reply period not set/);
  const withPeriod = {
    ...blank,
    sections: [{ section: "ruled_out", items: [{ text: "Agencies" }] }],
    noReply: { days: 30, source: "settings" },
  };
  assert.equal(item(withPeriod).state, "progress");
  assert.equal(
    item({ ...withStatement, noReply: withPeriod.noReply }).state,
    "done",
  );
});

test("a no-reply period is a whole number of days from 1 to 365", () => {
  assert.equal(preferences.replyDays(" 45 "), 45);
  assert.equal(preferences.replyDays("365"), 365);
  for (const text of ["0", "366", "4.5", "", "forty"])
    assert.equal(preferences.replyDays(text), null);
});

test("a Preferences section is saved whole: in place, moved or added", () => {
  const items = [{ text: "a" }, { text: "b" }, { text: "c" }];
  assert.deepEqual(
    preferences.moved(items, 0, 1).map((item) => item.text),
    ["b", "a", "c"],
  );
  assert.deepEqual(preferences.moved(items, 0, -1), items);
  // An edit replaces the statement where it now is, found by its text.
  assert.deepEqual(
    preferences
      .saved([{ text: "z" }, ...items], { text: "B" }, 1, "b")
      .map((item) => item.text),
    ["z", "a", "B", "c"],
  );
  // A statement removed elsewhere, or a new one, is added at the end.
  assert.deepEqual(
    preferences.saved(items, { text: "x" }, 1, "gone").map((item) => item.text),
    ["a", "b", "c", "x"],
  );
  assert.deepEqual(
    preferences.saved(items, { text: "d" }, -1, null).map((item) => item.text),
    ["a", "b", "c", "d"],
  );
  // Only a writing rule carries a scope; it defaults to every document.
  assert.deepEqual(preferences.itemsBody("writing", [{ text: "a" }]), [
    { text: "a", scope: "all" },
  ]);
  assert.deepEqual(
    preferences.itemsBody("facts", [{ text: "a", scope: "cv" }]),
    [{ text: "a" }],
  );
  assert.equal(preferences.itemName("x".repeat(50), 10), "xxxxxxxxx…");
});
