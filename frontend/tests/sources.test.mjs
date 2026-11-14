import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the source files; these modules have no React.
const sources = await import("../src/pages/sources/model.ts");
const settings = await import("../src/pages/settings/model.ts");

const NOW = new Date(2026, 10, 14, 12, 0);
const hoursAgo = (hours) => new Date(NOW.getTime() - hours * 3600_000);
const source = (overrides = {}) => ({
  id: "S-1",
  name: "Data engineer Zurich",
  kind: "jobspy",
  url: "",
  enabled: true,
  automatic_collection: true,
  version: 1,
  config: {},
  filters: {},
  schedule: {},
  ...overrides,
});

test("a source row counts what its jobs became, without zeros", () => {
  const line = sources.countsLine;
  assert.equal(
    line({ found: 31, shortlisted: 9, applied: 3, replied: 1 }),
    "31 found · 9 shortlisted · 3 applied",
  );
  assert.equal(
    line({ found: 12, shortlisted: 0, applied: 2 }),
    "12 found · 2 applied",
  );
  assert.equal(line({ found: 0, shortlisted: 0, applied: 0 }), "");
  assert.equal(line(undefined), "");
});

test("what a source searches leaves out empty parts and never shows quotes", () => {
  const describe = sources.describeSource;
  assert.equal(
    describe(
      source({
        config: {
          query: "Data engineer",
          location: "Zurich",
          providers: ["linkedin", "indeed"],
        },
      }),
    ),
    "Data engineer · Zurich · LinkedIn, Indeed",
  );
  assert.equal(
    describe(source({ config: { query: " ", providers: ["linkedin"] } })),
    "LinkedIn",
  );
  assert.equal(
    describe(source({ config: { query: "SRE", country: "switzerland" } })),
    "SRE · Switzerland",
  );
  assert.equal(
    describe(source({ kind: "greenhouse", config: { board: "northstar" } }), {
      greenhouse: "Greenhouse",
    }),
    "Greenhouse · northstar",
  );
  assert.equal(
    describe(source({ kind: "rss", url: "https://example.test/jobs.rss" })),
    "RSS feed · example.test/jobs.rss",
  );
});

test("a source's status: checking, failed, checked with what was new, paused", () => {
  const status = (overrides) => sources.sourceStatus(source(overrides), NOW);
  assert.deepEqual(status({ last_run: { state: "running" } }), {
    text: "Checking now…",
    running: true,
  });
  assert.deepEqual(
    status({
      last_outcome: "failed",
      last_error: "Blocked by the site. Try later.",
    }),
    { text: "Last check failed: blocked by the site", failed: true },
  );
  assert.equal(
    status({
      last_run: {
        state: "succeeded",
        finished_at: hoursAgo(2).toISOString(),
        counts: { created: 4 },
      },
    }).text,
    "Checked 2h ago · 4 new",
  );
  assert.equal(
    status({
      enabled: false,
      last_run: {
        state: "succeeded",
        finished_at: hoursAgo(30).toISOString(),
      },
    }).text,
    "Checked yesterday · nothing new",
  );
  assert.equal(status({}).text, "Not checked yet");
  assert.equal(status({ automatic_collection: false }).failed, true);
});

test("failing sources come first, then active ones, then paused", () => {
  const sorted = sources.sortSources([
    source({ id: "a", name: "B paused", enabled: false }),
    source({ id: "b", name: "A active" }),
    source({ id: "c", name: "C failing", last_outcome: "failed" }),
  ]);
  assert.deepEqual(
    sorted.map((item) => item.id),
    ["c", "b", "a"],
  );
});

test("one interval for every source, or none when they differ", () => {
  assert.equal(sources.commonInterval([source(), source()]), 1440);
  assert.equal(
    sources.commonInterval([
      source({ schedule: { kind: "interval", minutes: 360 } }),
      source({ schedule: { kind: "interval", minutes: 360 } }),
    ]),
    360,
  );
  assert.equal(
    sources.commonInterval([
      source(),
      source({ schedule: { kind: "daily", times: ["07:00"] } }),
    ]),
    null,
  );
  assert.deepEqual([60, 360, 1440, 45, 2880].map(sources.intervalLabel), [
    "1 h",
    "6 h",
    "24 h",
    "45 min",
    "2 days",
  ]);
});

test("moments read as people say them", () => {
  assert.equal(sources.ago(hoursAgo(3), NOW), "3h ago");
  assert.equal(sources.ago(new Date(2026, 10, 1), NOW), "on 1 Nov");
  assert.equal(sources.clock(new Date(2026, 10, 14, 14, 0), NOW), "14:00");
  assert.equal(
    sources.clock(new Date(2026, 10, 15, 3, 30), NOW),
    "tomorrow 03:30",
  );
});

test("a careers page names its job board before the server is asked", () => {
  const detect = sources.detectBoard;
  assert.deepEqual(detect("https://boards.greenhouse.io/northstar"), {
    kind: "greenhouse",
    board: "northstar",
  });
  assert.deepEqual(detect("https://jobs.lever.co/fjord/abc"), {
    kind: "lever",
    board: "fjord",
  });
  assert.deepEqual(detect("https://example.recruitee.com/"), {
    kind: "recruitee",
    board: "example",
  });
  assert.equal(detect("https://example.test/careers"), null);
  assert.equal(detect("not an address"), null);
  assert.equal(
    sources.suggestedName("company", { url: "https://jobs.ashbyhq.com/orbit" }),
    "Orbit",
  );
  assert.equal(
    sources.suggestedName("search", { query: "SRE ", location: "Bern" }),
    "SRE · Bern",
  );
});

test("the sites in use, the usual country and the checks", () => {
  const list = [
    source({
      config: { providers: ["linkedin", "indeed"], country: "switzerland" },
    }),
    source({ kind: "greenhouse", config: { board: "x" } }),
    source({ config: { country: "switzerland" } }),
  ];
  assert.deepEqual([...sources.sitesInUse(list)].sort(), [
    "greenhouse",
    "indeed",
    "linkedin",
  ]);
  assert.equal(sources.usualCountry(list), "switzerland");
  const check = (overrides) => ({
    id: "R-1",
    state: "succeeded",
    created_at: NOW.toISOString(),
    ...overrides,
  });
  assert.equal(
    sources.checkLine(check({ counts: { received: 36, created: 12 } })),
    "36 found · 12 new",
  );
  assert.equal(sources.checkLine(check({ counts: {} })), "Nothing found");
  assert.equal(
    sources.checkLine(
      check({
        state: "failed",
        tasks: [
          { id: "T-1", state: "failed", error: "The board did not answer." },
        ],
      }),
    ),
    "Failed: the board did not answer",
  );
  assert.deepEqual(
    sources.failedTasks(
      check({
        tasks: [
          { id: "T-1", state: "failed" },
          { id: "T-2", state: "succeeded" },
        ],
      }),
    ),
    ["T-1"],
  );
  assert.deepEqual(sources.terms(" a, ,b ,"), ["a", "b"]);
});

test("Settings: sections, sizes, access, snippets and request limits", () => {
  assert.equal(settings.sectionOf("data"), "data");
  assert.equal(settings.sectionOf("skills"), null);
  assert.equal(settings.sectionOf(null), null);
  assert.deepEqual(
    [512, 934_000, 1_400_000, 146_520_264_704].map(settings.bytes),
    ["512 bytes", "934 KB", "1.4 MB", "147 GB"],
  );
  assert.equal(settings.accessOf("owner"), "owner");
  assert.equal(settings.accessOf("anything"), "agent");
  assert.equal(settings.ACCESS.agent.label, "Agent");
  assert.match(
    settings.connectSnippet("claude", "https://openings.example.test/"),
    /^claude mcp add --transport http openings https:\/\/openings\.example\.test\/mcp\/ /,
  );
  assert.match(
    settings.connectSnippet("codex", "https://openings.example.test"),
    /bearer_token_env_var = "OPENINGS_TOKEN"/,
  );
  const provider = (policy, runtime = {}) => ({
    capability: { supported: true },
    policy,
    runtime,
  });
  assert.equal(settings.gateOf(provider({ enabled: true })).text, "Ready");
  assert.equal(settings.gateOf(provider({ enabled: false })).text, "Off");
  assert.equal(
    settings.gateOf(
      provider(
        { enabled: true },
        { cooldown_until: new Date(Date.now() + 60_000).toISOString() },
      ),
    ).tone,
    "warning",
  );
  assert.deepEqual(
    ["5", "0", "2,5", "", "-1", "4000", "x"].map(settings.spacing),
    [5, 0, 2.5, null, null, null, null],
  );
});
