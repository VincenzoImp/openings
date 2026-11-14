import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the source files; these modules have no React.
const { nextTabIndex, trappedIndex } = await import("../src/design/keys.ts");
const { buttonClass, tagClass, cx } = await import("../src/design/classes.ts");
const { actorPhrase } = await import("../src/design/actor.ts");

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

test("who made a change reads as one plain phrase; an unknown actor says nothing", () => {
  assert.equal(actorPhrase("owner"), "by you");
  assert.equal(actorPhrase("agent:career-agent"), "by career-agent");
  assert.equal(actorPhrase("system"), "by job sources");
  assert.equal(actorPhrase(null), "");
  assert.equal(actorPhrase(undefined), "");
  assert.equal(actorPhrase(""), "");
  assert.equal(actorPhrase("agent:"), "by an agent");
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
