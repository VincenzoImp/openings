import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
// Node strips the types of these modules; none of them uses React.
const model = await import("../src/screens/templates/model.ts");
const starters = await import("../src/screens/templates/starters.ts");
const preferences = await import("../src/screens/preferences/model.ts");

const example = (name) =>
  readFileSync(new URL(`../../examples/${name}`, import.meta.url), "utf8");

test("the example templates are the repository's examples", () => {
  assert.equal(starters.EXAMPLE_CV.tex, example("cv.tex"));
  assert.equal(starters.EXAMPLE_CV.kind, "cv");
  assert.equal(starters.EXAMPLE_LETTER.tex, example("letter.tex"));
  assert.equal(starters.EXAMPLE_LETTER.kind, "letter");
});

test("limits are typed; other rules are kept as they are", () => {
  const rules = { engine: "lualatex", max_pages: 1, max_bullets: 4 };
  assert.equal(model.limitOf(rules, "max_pages"), 1);
  assert.equal(model.limitOf({ max_pages: "2" }, "max_pages"), null);
  assert.deepEqual(
    model.withLimits(rules, {
      max_pages: "2",
      max_bullets: "",
      max_bullet_chars: "180",
    }),
    { engine: "lualatex", max_pages: 2, max_bullet_chars: 180 },
  );
  assert.equal(model.limitError("", 20), null);
  assert.equal(model.limitError("3", 20), null);
  for (const text of ["0", "21", "1.5", "two"])
    assert.match(model.limitError(text, 20), /whole number/);
  assert.equal(model.limitText(1, "pages"), "1 page");
  assert.equal(model.limitText(180, "characters"), "180 characters");
  assert.deepEqual(model.otherRules(rules), [
    { label: "Engine", value: "lualatex" },
  ]);
});

test("a template's kind, name and copy name come from plain words", () => {
  assert.equal(model.kindOfFile("my-cover-letter.tex"), "letter");
  assert.equal(model.kindOfFile("resume.tex"), "cv");
  assert.equal(model.nameOfFile("my-cv_2026.tex"), "My cv 2026");
  assert.equal(model.copyName("CV", ["CV"]), "CV copy");
  assert.equal(model.copyName("CV", ["CV", "CV copy"]), "CV copy 2");
  assert.equal(model.tabOf("files"), "files");
  assert.equal(model.tabOf("rules"), "preview");
  assert.equal(model.changedText("3h"), "Changed 3h ago");
  assert.equal(model.changedText("Just now"), "Changed just now");
  assert.equal(model.changedText("13 Nov"), "Changed 13 Nov");
  assert.equal(model.shownSource("a\nb\n"), "a\nb");
});

test("a dragged line lands where the pointer passed the middles", () => {
  const middles = [10, 30, 50, 70];
  assert.equal(preferences.dropIndex(middles, 0, 5), 0);
  assert.equal(preferences.dropIndex(middles, 0, 40), 1);
  assert.equal(preferences.dropIndex(middles, 0, 90), 3);
  assert.equal(preferences.dropIndex(middles, 3, 20), 1);
  assert.deepEqual(preferences.reordered(["a", "b", "c"], 0, 2), [
    "b",
    "c",
    "a",
  ]);
  assert.deepEqual(
    preferences.removed([{ text: "a" }, { text: "b" }], 5, "b"),
    [{ text: "a" }],
  );
  assert.equal(
    preferences.hiddenLine(4, 31),
    "would hide 4 of the 31 new jobs",
  );
  // Every section shows two examples while it is empty.
  for (const section of preferences.SECTIONS)
    assert.equal(section.examples.length, 2);
});
