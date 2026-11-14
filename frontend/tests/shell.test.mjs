import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
// Node strips the types of the source files; these modules have no React.
const routes = await import("../src/shell/routes.ts");
const shortcuts = await import("../src/shell/shortcuts.ts");
const gestures = await import("../src/ui/gestures.ts");
const links = await import("../src/pages/applications/links.ts");

test("every screen has one hash route; an unknown or old route opens Today", () => {
  const cases = {
    today: "today",
    jobs: "jobs",
    "jobs?job=J-1&section=new": "jobs",
    applications: "applications",
    "applications?stage=applied": "applications",
    "applications/AP-1": "application",
    "applications/AP-1?tab=documents": "application",
    profile: "profile",
    preferences: "preferences",
    templates: "templates",
    sources: "sources",
    "sources?section=runs": "sources",
    settings: "settings",
    setup: "setup",
  };
  for (const [hash, id] of Object.entries(cases)) {
    assert.equal(routes.match("#" + hash)?.id, id, hash);
    assert.equal(routes.resolve("#" + hash).id, id, hash);
  }
  // No aliases: the names of earlier versions and removed screens open Today.
  for (const old of [
    "",
    "#",
    "#no-such-page",
    "#review?application=AP-1",
    "#career",
    "#collection",
    "#activity",
    "#overview",
    "#inbox",
    "#applications/AP-1/extra",
  ]) {
    assert.equal(routes.match(old), null, old);
    assert.equal(routes.resolve(old).id, "today", old);
  }
});

test("a route reads its parameters and query; href writes them back", () => {
  const route = routes.match("#applications/AP%201?tab=documents&pane=cv");
  assert.equal(route.id, "application");
  assert.deepEqual(route.params, { id: "AP 1" });
  assert.equal(route.query.get("tab"), "documents");
  assert.equal(route.def.parent, "applications");
  assert.equal(
    routes.href("application", { id: "AP 1" }, { tab: "documents" }),
    "#applications/AP%201?tab=documents",
  );
  assert.equal(routes.href("jobs", {}, { job: "J-1", q: "" }), "#jobs?job=J-1");
  assert.equal(routes.href("today"), "#today");
  // The breadcrumb of a second-level page; none on a top-level one.
  assert.deepEqual(routes.breadcrumb(route, "Data Engineer · Orbit"), [
    { label: "Applications", href: "#applications" },
    { label: "Data Engineer · Orbit" },
  ]);
  assert.deepEqual(routes.breadcrumb(routes.resolve("#jobs")), []);
  // The application page the old screens link to is this route.
  assert.equal(
    routes.match(links.reviewHref("AP-1", "details")).id,
    "application",
  );
});

test("g then a letter goes to a screen; n, / and ? act alone", () => {
  const read = (keys) => {
    let pending = null;
    let action = null;
    for (const key of keys)
      ({ action, pending } = shortcuts.readKey(key, pending));
    return action;
  };
  assert.deepEqual(read(["g", "t"]), { kind: "go", route: "today" });
  assert.deepEqual(read(["g", "j"]), { kind: "go", route: "jobs" });
  assert.deepEqual(read(["g", "a"]), { kind: "go", route: "applications" });
  assert.deepEqual(read(["g", "p"]), { kind: "go", route: "profile" });
  assert.equal(read(["g", "z"]), null);
  assert.equal(read(["t"]), null);
  assert.deepEqual(read(["n"]), { kind: "add-job" });
  assert.deepEqual(read(["/"]), { kind: "search" });
  assert.deepEqual(read(["?"]), { kind: "help" });
  // A chord waits for one key only.
  assert.equal(shortcuts.readKey("g", null).pending, "g");
  assert.equal(shortcuts.readKey("x", "g").pending, null);
  // Every `g` shortcut names a route, and the sheet lists it.
  const sheet = shortcuts.SHEET.flatMap((section) => section.items);
  for (const [letter, route] of Object.entries(shortcuts.GO)) {
    assert.ok(routes.ROUTES[route], route);
    assert.ok(
      sheet.some(([keys]) => keys.join(" ") === `g ${letter}`),
      `g ${letter}`,
    );
  }
});

test("x toggles a row; shift-click selects the range from the last one", () => {
  const ids = ["a", "b", "c", "d", "e"];
  let picked = gestures.toggleSelected(new Set(), "b");
  assert.deepEqual([...picked], ["b"]);
  picked = gestures.selectRange(picked, ids, "b", "d");
  assert.deepEqual([...picked].sort(), ["b", "c", "d"]);
  // Upwards, and without an anchor only the row itself.
  assert.deepEqual([...gestures.selectRange(new Set(), ids, "e", "c")].sort(), [
    "c",
    "d",
    "e",
  ]);
  assert.deepEqual([...gestures.selectRange(new Set(), ids, null, "c")], ["c"]);
  assert.deepEqual([...gestures.toggleSelected(picked, "c")].sort(), [
    "b",
    "d",
  ]);
  // A row no longer in the list changes nothing.
  assert.deepEqual([...gestures.selectRange(new Set(), ids, "a", "z")], []);
});

test("a swipe needs a mostly horizontal drag past the threshold", () => {
  const width = 390;
  assert.equal(gestures.swipeOutcome(140, 10, width), "right");
  assert.equal(gestures.swipeOutcome(-140, 10, width), "left");
  // Too short: under 30% of the row and under the minimum.
  assert.equal(gestures.swipeOutcome(60, 0, width), null);
  assert.equal(gestures.swipeOutcome(100, 0, width), null);
  // Mostly vertical: a scroll.
  assert.equal(gestures.swipeOutcome(140, 90, width), null);
  // On a narrow row the minimum distance still applies.
  assert.equal(gestures.swipeOutcome(70, 0, 200), null);
  assert.equal(gestures.swipeOutcome(80, 0, 200), "right");
});

test("the page declares the cascade layers before any stylesheet", () => {
  for (const page of ["index.html", "ui.html"]) {
    const html = readFileSync(new URL(`../${page}`, import.meta.url), "utf8");
    const layers = html.indexOf("@layer reset, tokens, legacy, ui, screens;");
    assert.ok(layers > 0, `${page} declares the layer order`);
    assert.ok(layers < html.indexOf("<script"), page);
  }
});
