import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
// Node strips the types of these modules; they import no React.
const {
  formatDate,
  formatDay,
  formatFull,
  formatNumber,
  formatTime,
  plural,
  EMPTY,
} = await import("../src/ui/format.ts");
const { listIndex, cycleIndex, typeahead, isTyping, plainKey } =
  await import("../src/ui/keys.ts");

const NOW = new Date(2026, 10, 14, 15, 0);
const ago = (ms) => new Date(NOW.getTime() - ms);
const MIN = 60_000,
  HOUR = 60 * MIN;

test("past moments are relative within a week, then a day", () => {
  assert.equal(formatDate(ago(20_000), NOW), "Just now");
  assert.equal(formatDate(ago(25 * MIN), NOW), "25m");
  assert.equal(formatDate(ago(3 * HOUR), NOW), "3h");
  assert.equal(formatDate(new Date(2026, 10, 13, 22), NOW), "Yesterday");
  assert.equal(formatDate(new Date(2026, 10, 10, 9), NOW), "4d");
  assert.equal(formatDate(new Date(2026, 10, 7, 9), NOW), "7 Nov");
  assert.equal(formatDate(new Date(2025, 11, 30), NOW), "30 Dec 2025");
});

test("future moments read Today, Tomorrow, then the day", () => {
  assert.equal(formatDate(new Date(2026, 10, 14, 18), NOW), "Today");
  assert.equal(formatDate(new Date(2026, 10, 15, 9), NOW), "Tomorrow");
  assert.equal(formatDate(new Date(2026, 10, 18, 9), NOW), "18 Nov");
  assert.equal(formatDate(new Date(2027, 0, 3), NOW), "3 Jan 2027");
});

test("dates accept ISO strings, never show them, and mark invalid ones", () => {
  assert.equal(formatDay("2026-11-13T10:00:00", NOW), "13 Nov");
  // A date-only value is that local day, in every time zone.
  assert.equal(formatDay("2026-12-14", NOW), "14 Dec");
  assert.equal(formatDate("not a date", NOW), EMPTY);
  assert.equal(
    formatFull(new Date(2026, 10, 13, 14, 5)),
    "Fri 13 Nov 2026, 14:05",
  );
  assert.equal(formatTime(new Date(2026, 10, 13, 9, 5)), "09:05");
});

test("a count reads with its noun, in the one number format", () => {
  assert.equal(plural(1, "job"), "1 job");
  assert.equal(plural(0, "job"), "0 jobs");
  assert.equal(plural(2, "entry", "entries"), "2 entries");
  assert.equal(plural(12500, "job"), "12,500 jobs");
});

test("numbers group thousands; compact counts shorten", () => {
  assert.equal(formatNumber(25000), "25,000");
  assert.equal(formatNumber(25400, { compact: true }), "25.4k");
  assert.equal(formatNumber(950, { compact: true }), "950");
  assert.equal(formatNumber(null), EMPTY);
});

test("lists move with j/k and the arrows, stop at the ends, and jump", () => {
  assert.equal(listIndex("j", 0, 3), 1);
  assert.equal(listIndex("ArrowDown", 2, 3), 2);
  assert.equal(listIndex("k", 0, 3), 0);
  assert.equal(listIndex("ArrowUp", 2, 3), 1);
  assert.equal(listIndex("Home", 2, 3), 0);
  assert.equal(listIndex("End", 0, 3), 2);
  assert.equal(listIndex("j", -1, 3), 0);
  assert.equal(listIndex("x", 0, 3), null);
  assert.equal(listIndex("j", 0, 0), null);
});

test("menus and tabs wrap around; typeahead finds the next match", () => {
  assert.equal(cycleIndex("ArrowDown", 2, 3), 0);
  assert.equal(cycleIndex("ArrowUp", 0, 3), 2);
  assert.equal(cycleIndex("ArrowRight", 1, 3, "horizontal"), 2);
  assert.equal(cycleIndex("ArrowDown", 1, 3, "horizontal"), null);
  assert.equal(cycleIndex("ArrowUp", -1, 3), 2);
  const labels = ["Open posting", "Add note", "Copy link", "Archive"];
  assert.equal(typeahead(labels, "a", 0), 1);
  assert.equal(typeahead(labels, "a", 1), 3);
  assert.equal(typeahead(labels, "A", 3), 1);
  assert.equal(typeahead(labels, "z", 0), -1);
});

test("shortcuts stay out of text fields and modifier chords", () => {
  const input = (type) => ({ tagName: "INPUT", type });
  assert.equal(isTyping(input("text")), true);
  assert.equal(isTyping(input("checkbox")), false);
  assert.equal(isTyping({ tagName: "TEXTAREA" }), true);
  assert.equal(isTyping({ tagName: "DIV", isContentEditable: true }), true);
  assert.equal(isTyping({ tagName: "BUTTON" }), false);
  const press = (key, extra = {}) => ({
    key,
    metaKey: false,
    ctrlKey: false,
    altKey: false,
    target: { tagName: "BUTTON" },
    ...extra,
  });
  assert.equal(plainKey(press("s")), "s");
  assert.equal(plainKey(press("s", { metaKey: true })), null);
  assert.equal(plainKey(press("s", { target: input("search") })), null);
});

// Colour means something (P7): no colour literal outside the tokens.
function files(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? files(join(dir, entry.name))
      : [join(dir, entry.name)],
  );
}
const SRC = new URL("../src/", import.meta.url).pathname;

// P7: colours come from the tokens only, in every screen and component.
test("src has no hex colour outside tokens.css", () => {
  const found = [];
  for (const file of files(SRC)) {
    if (file.endsWith("schema.d.ts")) continue;
    if (!/\.(css|tsx?)$/.test(file) || file.endsWith("tokens.css")) continue;
    const text = readFileSync(file, "utf8");
    for (const match of text.matchAll(/(?<![\w&])#[0-9a-fA-F]{3,8}\b/g))
      found.push(`${file.slice(SRC.length)}: ${match[0]}`);
  }
  assert.deepEqual(found, []);
});

test("every stylesheet sits in a cascade layer, and no weight is 700", () => {
  for (const file of files(SRC)) {
    if (!file.endsWith(".css")) continue;
    const text = readFileSync(file, "utf8");
    if (!file.endsWith("base.css"))
      assert.match(text, /^@layer (reset|tokens|ui|screens) \{/m, file);
    assert.doesNotMatch(text, /font-weight:\s*(700|bold)|\b700 \d/, file);
  }
});
