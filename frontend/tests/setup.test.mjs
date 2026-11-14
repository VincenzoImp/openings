import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const checklist = await import("../src/screens/setup/checklist.ts");
const model = await import("../src/screens/setup/model.ts");
const preferences = await import("../src/screens/preferences/model.ts");

const empty = { name: "", preferences: 0, sources: 0, jobs: 0, cv: 0 };

test("the setup checklist reads three server facts, nothing else", () => {
  const start = checklist.progress(empty);
  assert.equal(start.done, 0);
  assert.equal(start.total, 3);
  assert.equal(start.empty, true);
  assert.equal(start.finished, false);
  assert.deepEqual(
    start.items.map((item) => [item.step, item.title]),
    [
      ["about", "Tell us what you're looking for"],
      ["jobs", "Add a job source or a job"],
      ["cv", "Add your CV"],
    ],
  );
  // A name alone is not enough: what you look for is needed too.
  const named = checklist.progress({ ...empty, name: "Alex" });
  assert.equal(named.done, 0);
  assert.equal(named.empty, false);
  assert.equal(
    checklist.progress({ ...empty, name: "Alex", preferences: 1 }).done,
    1,
  );
  // A source or a job; a career entry, a highlight or a template.
  for (const facts of [{ sources: 1 }, { jobs: 3 }])
    assert.equal(checklist.checklist({ ...empty, ...facts })[1].done, true);
  assert.equal(checklist.checklist({ ...empty, cv: 1 })[2].done, true);
  const all = checklist.progress({
    name: "Alex",
    preferences: 2,
    sources: 0,
    jobs: 1,
    cv: 4,
  });
  assert.equal(all.finished, true);
  assert.equal(all.done, 3);
});

const sections = (items) => [
  { section: "looking_for", version: 4, items },
  { section: "ruled_out", version: 1, items: [] },
];
const workspace = (items, spoken = []) => ({
  sections: sections(items),
  settings: { spoken_languages: spoken, version: 7 },
});

test("About you reads what the workspace already says", () => {
  assert.deepEqual(
    model.aboutFrom(
      { name: "Alex Example" },
      workspace(
        [
          { text: "Small teams" },
          { text: "Roles: data engineer" },
          { text: "Where: Zurich or remote" },
        ],
        ["en", "de"],
      ),
    ),
    {
      name: "Alex Example",
      roles: "data engineer",
      where: "Zurich or remote",
      languages: ["en", "de"],
    },
  );
  // The lines it did not write are shown beside its fields.
  assert.deepEqual(
    model.otherLines(
      workspace([{ text: "Small teams" }, { text: "Roles: data engineer" }]),
    ),
    ["Small teams"],
  );
  assert.equal(model.stepOf("cv"), "cv");
  assert.equal(model.stepOf("record"), "about");
  assert.equal(model.stepOf(null), "about");
});

test("About you replaces its own statements and keeps the others", () => {
  const before = workspace(
    [{ text: "Small teams" }, { text: "Roles: analyst" }],
    ["en"],
  );
  const about = {
    name: " Alex ",
    roles: "data engineer",
    where: "Zurich",
    languages: ["en", "it"],
  };
  assert.deepEqual(model.aboutChanges(about, { name: "" }, before), {
    name: "Alex",
    lookingFor: {
      expected_version: 4,
      items: [
        { text: "Small teams" },
        { text: "Roles: data engineer" },
        { text: "Where: Zurich" },
      ],
    },
    languages: ["en", "it"],
  });
  // Nothing changed: nothing is written.
  const same = model.aboutChanges(
    { name: "Alex", roles: "analyst", where: "", languages: ["en"] },
    { name: "Alex" },
    before,
  );
  assert.deepEqual(same, { name: null, lookingFor: null, languages: null });
  // A cleared field removes its statement.
  assert.deepEqual(
    model.aboutChanges(
      { name: "Alex", roles: "", where: "", languages: ["en"] },
      { name: "Alex" },
      before,
    ).lookingFor.items,
    [{ text: "Small teams" }],
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
