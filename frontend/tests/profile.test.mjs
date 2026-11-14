import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of these modules; none of them uses React.
const model = await import("../src/screens/profile/model.ts");
const { parseCv, readDates } = await import("../src/screens/profile/parse.ts");

test("dates read as a CV writes them", () => {
  assert.equal(
    model.formatDates({ kind: "period", start: "2022-02", current: true }),
    "Feb 2022 – Present",
  );
  assert.equal(
    model.formatDates({ kind: "period", start: "2017", end: "2019" }),
    "2017 – 2019",
  );
  assert.equal(
    model.formatDates({ kind: "single", start: "2025-11" }),
    "Nov 2025",
  );
  assert.equal(model.formatDates(null), "");
});

test("the form's dates become stored dates or say how to fix them", () => {
  const draft = (patch) => ({ ...model.dateDraft(null), ...patch });
  assert.deepEqual(model.datesOf(draft({})), { dates: null });
  assert.deepEqual(model.datesOf(draft({ startYear: "2021" })), {
    dates: { kind: "single", start: "2021" },
  });
  assert.deepEqual(
    model.datesOf(
      draft({ startYear: "2021", startMonth: "03", current: true }),
    ),
    { dates: { kind: "period", start: "2021-03", current: true } },
  );
  assert.deepEqual(
    model.datesOf(
      draft({ startYear: "2019", endYear: "2021", endMonth: "06" }),
    ),
    {
      dates: { kind: "period", start: "2019", end: "2021-06", current: false },
    },
  );
  assert.match(model.datesOf(draft({ endYear: "2020" })).error, /start year/);
  assert.match(model.datesOf(draft({ startYear: "21" })).error, /four digits/);
  assert.match(
    model.datesOf(draft({ startYear: "2022", endYear: "2020" })).error,
    /before the start/,
  );
  assert.deepEqual(
    model.dateDraft({ kind: "period", start: "2022-02", current: true }),
    {
      startYear: "2022",
      startMonth: "02",
      endYear: "",
      endMonth: "",
      current: true,
    },
  );
});

test("a new entry goes before the first older one; a full list is spread out", () => {
  const entries = [
    {
      id: "a",
      position: 10,
      dates: { kind: "period", start: "2022", current: true },
    },
    {
      id: "b",
      position: 20,
      dates: { kind: "period", start: "2019", end: "2021" },
    },
    { id: "c", position: 30, dates: null },
  ];
  // Between the current job and the one that ended in 2021.
  assert.deepEqual(
    model.placeNew(entries, { kind: "period", start: "2021", end: "2023" }),
    { position: 15, moves: [] },
  );
  // Newest of all: before the first.
  assert.equal(
    model.placeNew(entries, { kind: "single", start: "9999" }).position,
    9,
  );
  // Without dates: last.
  assert.deepEqual(model.placeNew(entries, null), { position: 31, moves: [] });
  // No room between 1 and 2: the list is spread ten apart.
  const tight = [
    { id: "a", position: 1, dates: { kind: "single", start: "2024" } },
    { id: "b", position: 2, dates: { kind: "single", start: "2020" } },
  ];
  const placed = model.placeNew(tight, { kind: "single", start: "2022" });
  assert.deepEqual(placed, {
    position: 11,
    moves: [{ id: "b", position: 21, dates: tight[1].dates }],
  });
});

test("skills of the record: once each, the most used first", () => {
  assert.deepEqual(
    model.allSkills([
      { skills: ["SQL", "Python"] },
      { skills: ["python", "Go"] },
    ]),
    ["Python", "SQL", "Go"],
  );
  assert.deepEqual(model.addSkills(["Python"], "sql, python ,  Go"), [
    "Python",
    "sql",
    "Go",
  ]);
  assert.equal(model.linkHref("example.dev"), "https://example.dev");
  assert.equal(model.linkText({ url: "https://example.dev/" }), "example.dev");
});

test("dates in a line of a CV", () => {
  assert.deepEqual(readDates("Mar 2020 - Present"), {
    dates: { kind: "period", start: "2020-03", current: true },
    rest: "",
  });
  assert.deepEqual(readDates("2014 – 2017 · Porto").dates, {
    kind: "period",
    start: "2014",
    end: "2017",
    current: false,
  });
  assert.deepEqual(readDates("Since 03/2021").dates, {
    kind: "single",
    start: "2021-03",
  });
  assert.equal(readDates("No dates here").dates, null);
});

test("a Markdown CV becomes a header, entries and their highlights", () => {
  const { header, entries } = parseCv(`# Jordan Example
Platform engineer
Lisbon · jordan@example.test · +351 000 000 000 · example.dev

## Summary
Ten years of platform work.

## Experience
### Platform engineer — Example Grid
2021 – Present · Lisbon
Owned the build system.
- Cut deploy time from 40 to 6 minutes.
- Skills: Go, Bazel

## Education
### BSc Computer Science, Example University
2014 – 2017

## Skills
Python, SQL; Terraform`);
  assert.deepEqual(header, {
    name: "Jordan Example",
    headline: "Platform engineer",
    location: "Lisbon",
    email: "jordan@example.test",
    phone: "+351 000 000 000",
    links: [{ label: "example.dev", url: "https://example.dev" }],
    summary: "Ten years of platform work.",
  });
  assert.equal(entries.length, 3);
  assert.deepEqual(entries[0], {
    kind: "experience",
    title: "Platform engineer",
    organization: "Example Grid",
    dates: { kind: "period", start: "2021", current: true },
    location: "Lisbon",
    narrative: "Owned the build system.",
    skills: ["Go", "Bazel"],
    highlights: ["Cut deploy time from 40 to 6 minutes."],
  });
  assert.equal(entries[1].organization, "Example University");
  assert.deepEqual(entries[2].skills, ["Python", "SQL", "Terraform"]);
});

test("plain text with capitalised headings reads the same way", () => {
  const { entries } = parseCv(`Sam Example
EXPERIENCE
Analyst at Example Retail
Jan 2016 - Dec 2019
• Built the weekly sales dashboard.
LANGUAGES
- English (native)
- German (B2)`);
  assert.deepEqual(
    entries.map((entry) => [entry.kind, entry.title, entry.organization]),
    [
      ["experience", "Analyst", "Example Retail"],
      ["language", "English (native)", ""],
      ["language", "German (B2)", ""],
    ],
  );
  assert.deepEqual(entries[0].dates, {
    kind: "period",
    start: "2016-01",
    end: "2019-12",
    current: false,
  });
  assert.deepEqual(entries[0].highlights, [
    "Built the weekly sales dashboard.",
  ]);
});
