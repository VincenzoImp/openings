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

test("older button and tag names map to the design system's classes", () => {
  assert.equal(buttonClass(), "btn");
  assert.equal(buttonClass("primary"), "btn primary");
  assert.equal(buttonClass("danger small"), "btn danger sm");
  assert.equal(buttonClass("danger-fill"), "btn danger");
  assert.equal(buttonClass("", "sm", "small extra"), "btn sm extra");
  assert.equal(buttonClass("subtle"), "btn quiet");
  assert.equal(buttonClass("", "", "close", true), "icon-btn close");
  assert.equal(tagClass(), "tag");
  assert.equal(tagClass("green", "ready-tag"), "tag ready ready-tag");
  assert.equal(tagClass("amber"), "tag attention");
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
    "overview",
    "activity",
    "inbox",
    "shortlist",
    "applications",
    "collection",
    "career",
    "templates",
    "settings",
  ])
    assert.equal(routes.routeOf("#" + route), route);
  assert.equal(routes.routeOf(""), "overview");
  assert.equal(routes.routeOf("#no-such-page"), "overview");
  assert.equal(routes.routeOf("#inbox?queue=duplicates"), "inbox");
  assert.equal(routes.routeOf("#today"), "overview");
  assert.equal(routes.routeOf("#jobs?q=python"), "inbox");
  assert.equal(routes.canonicalHash("#jobs?q=python"), "#inbox?q=python");
  assert.equal(routes.canonicalHash("#today"), "#overview");
  assert.equal(routes.canonicalHash("#career?section=knowledge"), null);
});

test("navigation has three groups, and both job queues belong to Jobs", () => {
  assert.deepEqual(
    routes.NAV.map((group) => [
      group.group,
      group.items.map((item) => item.label),
    ]),
    [
      ["Work", ["Overview", "Applications", "Jobs", "Activity"]],
      ["Library", ["Career", "Templates"]],
      ["System", ["Collection", "Settings"]],
    ],
  );
  assert.equal(routes.destinationOf("shortlist").item.label, "Jobs");
  assert.equal(routes.destinationOf("inbox").group, "Work");
  assert.equal(routes.destinationOf("settings").group, "System");
  assert.equal(routes.TAB_BAR.length, 4);
  // Every screen is reachable from the navigation.
  for (const route of Object.keys(routes.SCREENS))
    assert.ok(routes.destinationOf(route), route);
});

test("deep links to a job or an application are read from the hash", () => {
  assert.deepEqual(routes.overlayOf("#inbox?job=abc"), {
    kind: "job",
    id: "abc",
  });
  assert.deepEqual(
    routes.overlayOf("#applications?application=x1&detail=requirements"),
    { kind: "application", id: "x1" },
  );
  assert.equal(routes.overlayOf("#applications?view=list"), null);
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
