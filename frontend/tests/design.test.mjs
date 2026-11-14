import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the source files; these modules have no React.
const { nextTabIndex, trappedIndex } = await import("../src/design/keys.ts");
const { buttonClass, tagClass, cx } = await import("../src/design/classes.ts");
const { actorChip } = await import("../src/design/actor.ts");
const routes = await import("../src/shell/routes.ts");
const preferences = await import("../src/shell/preferences.ts");

test("arrow keys move through tabs and wrap; Home and End jump", () => {
  assert.equal(nextTabIndex("ArrowRight", 0, 3), 1);
  assert.equal(nextTabIndex("ArrowRight", 2, 3), 0);
  assert.equal(nextTabIndex("ArrowLeft", 0, 3), 2);
  assert.equal(nextTabIndex("Home", 2, 3), 0);
  assert.equal(nextTabIndex("End", 0, 3), 2);
  assert.equal(nextTabIndex("Enter", 1, 3), null);
  assert.equal(nextTabIndex("ArrowRight", 0, 0), null);
  // A value that is not among the tabs starts from the first one.
  assert.equal(nextTabIndex("ArrowRight", -1, 3), 1);
});

test("Tab stays inside a container that keeps focus", () => {
  assert.equal(trappedIndex(0, 4, false), 1);
  assert.equal(trappedIndex(3, 4, false), 0);
  assert.equal(trappedIndex(0, 4, true), 3);
  assert.equal(trappedIndex(-1, 4, false), 0);
  assert.equal(trappedIndex(-1, 4, true), 3);
  assert.equal(trappedIndex(0, 0, false), -1);
});

test("buttons and tags get the design system's classes", () => {
  assert.equal(buttonClass(), "btn");
  assert.equal(buttonClass("primary"), "btn primary");
  assert.equal(buttonClass("quiet danger", "sm"), "btn quiet danger sm");
  assert.equal(buttonClass("", "md", "extra"), "btn extra");
  assert.equal(buttonClass("", "", "close", true), "icon-btn close");
  assert.equal(tagClass(), "tag");
  assert.equal(tagClass("ready", "ready-tag"), "tag ready ready-tag");
  assert.equal(tagClass("neutral"), "tag");
  assert.equal(tagClass("agent"), "tag agent");
  assert.equal(cx("a", false, "b a", undefined), "a b");
});

test("an actor chip names the agent's token and keeps the agent colour for agents", () => {
  const token = { kind: "token", name: "career-agent", label: "career-agent" };
  assert.deepEqual(actorChip({ ...token, token_kind: "agent" }), {
    tone: "agent",
    text: "career-agent",
  });
  assert.deepEqual(actorChip({ ...token, token_kind: "owner" }), {
    tone: "owner",
    text: "career-agent (owner token)",
  });
  assert.deepEqual(actorChip({ kind: "owner", name: null, label: "Owner" }), {
    tone: "owner",
    text: "Owner",
  });
  assert.deepEqual(actorChip({ kind: "system", name: null, label: "System" }), {
    tone: "system",
    text: "System",
  });
  assert.deepEqual(actorChip(null), { tone: "unknown", text: "Unknown" });
  assert.equal(
    actorChip({ kind: "unknown", name: null, label: "Unknown" }).tone,
    "unknown",
  );
});

test("every shipped hash route still opens its screen, and design names are aliases", () => {
  for (const route of [
    "today",
    "activity",
    "jobs",
    "applications",
    "collection",
    "career",
    "preferences",
    "templates",
    "settings",
  ])
    assert.equal(routes.routeOf("#" + route), route);
  assert.equal(routes.routeOf(""), "today");
  assert.equal(routes.routeOf("#no-such-page"), "today");
  // Inbox and Shortlist were screens before Jobs; their links open its tabs.
  assert.equal(routes.routeOf("#inbox"), "jobs");
  assert.equal(routes.routeOf("#shortlist"), "jobs");
  assert.equal(routes.routeOf("#inbox?queue=duplicates"), "jobs");
  assert.equal(routes.canonicalHash("#inbox"), "#jobs");
  assert.equal(routes.canonicalHash("#inbox?q=python"), "#jobs?q=python");
  assert.equal(routes.canonicalHash("#shortlist"), "#jobs?section=shortlisted");
  assert.equal(
    routes.canonicalHash("#inbox?queue=dismissed"),
    "#jobs?section=dismissed",
  );
  assert.equal(
    routes.canonicalHash("#inbox?queue=all&complete=false"),
    "#jobs?complete=false&section=all",
  );
  assert.equal(
    routes.canonicalHash("#inbox?queue=duplicates"),
    "#jobs?signal=likely_duplicate",
  );
  assert.equal(
    routes.canonicalHash("#jobs?queue=shortlist"),
    "#jobs?section=shortlisted",
  );
  assert.equal(routes.canonicalHash("#jobs?q=python"), null);
  // Overview was the first screen before Today; its links open Today.
  assert.equal(routes.routeOf("#overview"), "today");
  assert.equal(routes.routeOf("#overview?since=2026-01-01"), "today");
  assert.equal(routes.canonicalHash("#overview"), "#today");
  // Overview's period is the Progress of Applications, Insights.
  assert.equal(
    routes.canonicalHash("#overview?since=2026-01-01"),
    "#applications?since=2026-01-01&section=insights",
  );
  assert.equal(routes.canonicalHash("#career?section=knowledge"), null);
  // The review page belongs to Applications.
  assert.equal(routes.routeOf("#review?application=x1"), "review");
  assert.equal(routes.destinationOf("review").item.label, "Applications");
});

test("navigation has three groups, and the old job queues belong to Jobs", () => {
  assert.deepEqual(
    routes.NAV.map((group) => [
      group.group,
      group.items.map((item) => item.label),
    ]),
    [
      ["Work", ["Today", "Applications", "Jobs", "Activity"]],
      ["Library", ["Career", "Preferences", "Templates"]],
      ["System", ["Collection", "Settings"]],
    ],
  );
  assert.equal(
    routes.destinationOf(routes.routeOf("#shortlist")).item.label,
    "Jobs",
  );
  assert.equal(routes.destinationOf("jobs").group, "Work");
  assert.equal(routes.destinationOf("settings").group, "System");
  assert.equal(routes.TAB_BAR.length, 4);
  // Every screen is reachable from the navigation, except the setup guide:
  // a new workspace opens on it, and Settings, Workspace links to it.
  for (const route of Object.keys(routes.SCREENS))
    if (route !== "setup") assert.ok(routes.destinationOf(route), route);
  assert.equal(routes.destinationOf("setup"), null);
});

test("a job opens in Jobs; an application opens its review page", () => {
  // The old drawer's address, with its tab, from any screen.
  assert.equal(routes.canonicalHash("#today?job=abc"), "#jobs?job=abc");
  assert.equal(
    routes.canonicalHash("#applications?view=list&job=abc"),
    "#jobs?job=abc",
  );
  assert.equal(
    routes.canonicalHash("#inbox?job=abc&detail=notes"),
    "#jobs?job=abc",
  );
  assert.equal(
    routes.canonicalHash("#jobs?job=abc&detail=files"),
    "#jobs?job=abc",
  );
  assert.equal(routes.canonicalHash("#jobs?section=all&job=abc"), null);
  // The old drawer's address, with its tab, from any screen.
  assert.equal(
    routes.canonicalHash("#applications?application=x1&detail=requirements"),
    "#review?application=x1&tab=requirements",
  );
  assert.equal(
    routes.canonicalHash("#today?application=x1&detail=posting"),
    "#review?application=x1&pane=posting",
  );
  assert.equal(
    routes.canonicalHash("#activity?application=x1"),
    "#review?application=x1",
  );
  assert.equal(
    routes.canonicalHash("#review?application=x1&tab=answers"),
    null,
  );
});

test("the stored theme and density win; otherwise the system theme and comfortable rows", () => {
  const store = (values) => ({
    getItem: (key) => values[key] ?? null,
    setItem() {},
  });
  assert.equal(preferences.initialTheme(store({}), true), "dark");
  assert.equal(preferences.initialTheme(store({}), false), "light");
  assert.equal(
    preferences.initialTheme(store({ "openings-theme": "light" }), true),
    "light",
  );
  assert.equal(
    preferences.initialTheme(store({ "openings-theme": "sepia" }), false),
    "light",
  );
  assert.equal(preferences.initialDensity(store({})), "comfortable");
  assert.equal(
    preferences.initialDensity(store({ "openings-density": "compact" })),
    "compact",
  );
  const broken = {
    getItem() {
      throw Error("blocked");
    },
    setItem() {},
  };
  assert.equal(preferences.initialTheme(broken, true), "dark");
  assert.equal(preferences.initialDensity(null), "comfortable");
});

test("free-form values become typed rows and come back unchanged", async () => {
  const kv = await import("../src/design/kv.ts");
  const value = {
    name: "Alex",
    team_size: 6,
    remote: false,
    customers: ["Operator A", "Operator B"],
    references: { manager: { name: "Sam" }, years: [2022, 2023] },
    nothing: null,
    mixed: ["a", 1],
    comma: ["a, b"],
    empty: [],
  };
  const rows = kv.toRows(value);
  assert.deepEqual(
    rows.map((row) => row.type),
    [
      "text",
      "number",
      "boolean",
      "list",
      "structured",
      "structured",
      "structured",
      "structured",
      "structured",
    ],
  );
  // Untouched rows give back exactly what they were given.
  assert.deepEqual(kv.fromRows(rows), value);
  assert.equal(kv.problem(rows), null);
  assert.equal(kv.describe(value.references), "2 fields");
  assert.equal(kv.describe(value.mixed), "2 items");
  assert.equal(kv.describe(null), "Empty");

  // A type change carries the value over where it has a meaning.
  assert.equal(kv.valueOf(kv.retype(rows[1], "text")), "6");
  assert.equal(kv.valueOf(kv.retype(rows[0], "number")), 0);
  assert.equal(
    kv.problem([kv.retype(rows[0], "number")]),
    '"name" needs a number.',
  );
  assert.deepEqual(kv.valueOf(kv.retype(rows[0], "list")), ["Alex"]);
  assert.equal(
    kv.valueOf(kv.retype(rows[3], "text")),
    "Operator A, Operator B",
  );
  assert.equal(kv.valueOf(kv.retype(rows[2], "text")), "");
  assert.equal(kv.valueOf(kv.retype(rows[4], "boolean")), false);

  // An object is edited one level down; deeper values stay as they are.
  assert.equal(kv.editableAsFields(rows[4]), true);
  assert.equal(kv.editableAsFields(rows[6]), false);
  const opened = kv.asFields(rows[4]);
  assert.deepEqual(
    opened.fields.map((row) => [row.key, row.type]),
    [
      ["manager", "structured"],
      ["years", "structured"],
    ],
  );
  opened.fields.push({ ...kv.newRow(), key: "checked", value: "yes" });
  assert.deepEqual(kv.valueOf(opened), {
    ...value.references,
    checked: "yes",
  });
  assert.equal(kv.asFields(rows[6]), rows[6]);

  // What stops a save is said in words.
  assert.equal(kv.problem([kv.newRow()]), "Give every row a key.");
  assert.equal(
    kv.problem([rows[0], { ...rows[1], key: " name " }]),
    'The key "name" is used twice.',
  );
  assert.equal(
    kv.problem([{ ...rows[0], key: "dates" }], ["dates"]),
    '"dates" has its own field above.',
  );
  assert.equal(
    kv.problem([{ ...rows[3], value: " , " }]),
    '"customers" needs at least one list item.',
  );
  assert.equal(
    kv.problem([{ ...opened, fields: [kv.newRow()] }]),
    'In "references": Give every row a key.',
  );
});

test("a comparison keeps two unchanged lines around each change and folds the rest", async () => {
  const { foldDiff } = await import("../src/design/lines.ts");
  const same = (text) => ({ change: "same", text });
  const lines = [
    ...["a", "b", "c", "d", "e", "f"].map(same),
    { change: "removed", text: "g" },
    { change: "added", text: "G" },
    ...["h", "i", "j"].map(same),
  ];
  assert.deepEqual(
    foldDiff(lines).map((row) => row.text ?? `(${row.count})`),
    ["(4)", "e", "f", "g", "G", "h", "i", "(1)"],
  );
  assert.deepEqual(foldDiff([same("a")]), [{ change: "folded", count: 1 }]);
  assert.deepEqual(foldDiff([]), []);
});
