import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const { isNewWorkspace } = await import("../src/shell/setup.ts");
const model = await import("../src/pages/setup/model.ts");

const blank = {
  profile: { name: "", headline: "", location: "", email: "" },
  sections: [
    { section: "decision", total: 0 },
    { section: "eligibility", total: 0 },
  ],
  noReply: { days: 30, source: "default", item_id: null, confirmed: false },
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
      { section: "decision", total: 1 },
      { section: "eligibility", total: 2 },
    ],
    noReply: { days: 45, source: "policy", item_id: "i", confirmed: true },
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
  assert.equal(items.policy.state, "done");
  assert.equal(
    items.policy.meta,
    "2 facts employers ask about · no reply after 45 days",
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

test("a policy is in progress until it has a fact and the no-reply period", () => {
  const withFact = {
    ...blank,
    sections: [
      { section: "decision", total: 0 },
      { section: "eligibility", total: 1 },
    ],
  };
  const item = (facts) =>
    model.recordItems(facts).find((entry) => entry.id === "policy");
  assert.equal(item(withFact).state, "progress");
  assert.match(item(withFact).meta, /no reply period not set/);
  const withPeriod = {
    ...blank,
    sections: [{ section: "decision", total: 1 }],
    noReply: { days: 30, source: "policy", item_id: "i", confirmed: true },
  };
  assert.equal(item(withPeriod).state, "progress");
});

test("a no-reply period is a whole number of days from 1 to 3650", () => {
  assert.equal(model.replyDays(" 45 "), 45);
  for (const text of ["0", "3651", "4.5", "", "forty"])
    assert.equal(model.replyDays(text), null);
});
