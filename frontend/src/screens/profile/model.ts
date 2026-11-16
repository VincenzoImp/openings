// The Profile as a CV: which section an entry belongs to, how its dates read,
// where a new entry goes, and the skills of the whole record. Pure (no React,
// no client), so it is tested directly (tests/profile.test.mjs).

export type Kind =
  | "experience"
  | "project"
  | "course"
  | "education"
  | "award"
  | "publication"
  | "fact"
  | "skill"
  | "language"
  | "other";

export const KINDS: Record<Kind, string> = {
  experience: "Experience",
  education: "Education",
  course: "Course",
  project: "Project",
  award: "Award",
  publication: "Publication",
  language: "Language",
  skill: "Skill",
  fact: "Fact",
  other: "Other",
};

export type SectionId = "experience" | "education" | "projects" | "other";

export const SECTIONS: {
  id: SectionId;
  title: string;
  /** The kind a new entry of this section starts with. */
  kind: Kind;
  add: string;
}[] = [
  {
    id: "experience",
    title: "Experience",
    kind: "experience",
    add: "Add experience",
  },
  {
    id: "education",
    title: "Education",
    kind: "education",
    add: "Add education",
  },
  { id: "projects", title: "Projects", kind: "project", add: "Add project" },
  { id: "other", title: "Other", kind: "other", add: "Add other" },
];

export function sectionOf(kind: string): SectionId {
  if (kind === "experience") return "experience";
  if (kind === "education" || kind === "course") return "education";
  if (kind === "project") return "projects";
  return "other";
}

export interface Dates {
  kind: "single" | "period";
  start: string;
  end?: string | null;
  current?: boolean;
}

export const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** "2022-02" → "Feb 2022"; "2017" → "2017". */
export function formatMonth(value: string) {
  const [year, month] = value.split("-");
  return month ? `${MONTH_NAMES[Number(month) - 1].slice(0, 3)} ${year}` : year;
}

/** "Feb 2022 – Present", "2017 – 2019", "2025"; nothing without dates. */
export function formatDates(dates?: Partial<Dates> | null) {
  if (!dates?.start) return "";
  const start = formatMonth(dates.start);
  if (dates.kind !== "period") return start;
  const end = dates.current
    ? "Present"
    : dates.end
      ? formatMonth(dates.end)
      : "";
  return end ? `${start} – ${end}` : start;
}

/** A key that sorts newer entries first: current, then the latest end. */
export function recency(dates?: Partial<Dates> | null) {
  if (!dates?.start) return "";
  const last = dates.current ? "9999-99" : dates.end || dates.start;
  return `${last.padEnd(7, "-99")}|${dates.start.padEnd(7, "-99")}`;
}

// --- The dates of the form: a start and an end, each a month and a year ---

export interface DateDraft {
  startMonth: string;
  startYear: string;
  endMonth: string;
  endYear: string;
  current: boolean;
}

export function dateDraft(dates?: Partial<Dates> | null): DateDraft {
  const [startYear = "", startMonth = ""] = (dates?.start || "").split("-");
  const [endYear = "", endMonth = ""] = (dates?.end || "").split("-");
  return {
    startYear,
    startMonth,
    endYear,
    endMonth,
    current: Boolean(dates?.current),
  };
}

const YEAR = /^[0-9]{4}$/;

/**
 * The stored dates of a draft, or an error that says how to fix it. No start
 * means no dates; a start alone is one date; an end or Present makes a period.
 */
export function datesOf(
  draft: DateDraft,
): { dates: Dates | null; error?: undefined } | { error: string } {
  const startYear = draft.startYear.trim(),
    endYear = draft.endYear.trim();
  if (!startYear) {
    if (endYear || draft.current)
      return { error: "Add the start year, for example 2021." };
    return { dates: null };
  }
  if (!YEAR.test(startYear) || startYear === "0000")
    return { error: "Write the start year with four digits, like 2021." };
  const start = startYear + (draft.startMonth ? `-${draft.startMonth}` : "");
  if (draft.current) return { dates: { kind: "period", start, current: true } };
  if (!endYear) return { dates: { kind: "single", start } };
  if (!YEAR.test(endYear) || endYear === "0000")
    return { error: "Write the end year with four digits, like 2024." };
  const end = endYear + (draft.endMonth ? `-${draft.endMonth}` : "");
  const from = start.length === 7 ? start : `${start}-01`;
  const to = end.length === 7 ? end : `${end}-12`;
  if (from > to) return { error: "The end comes before the start." };
  return { dates: { kind: "period", start, end, current: false } };
}

// --- Order: the stored position, chosen from the dates for a new entry ---

export interface Placed {
  id: string;
  position: number;
  dates?: Partial<Dates> | null;
}

/**
 * The position of a new entry among the entries of its section (in their
 * shown order): before the first one it is newer than, otherwise last. When
 * there is no gap, the section is spread out first (`moves`).
 */
export function placeNew(section: Placed[], dates: Partial<Dates> | null) {
  const key = recency(dates);
  let index = section.length;
  if (key) index = section.findIndex((entry) => recency(entry.dates) < key);
  if (index < 0) index = section.length;
  return placeAt(section, index);
}

/** The position that puts an item at `index` of `list`, and any moves. */
export function placeAt(list: Placed[], index: number) {
  const before = list[index - 1]?.position;
  const after = list[index]?.position;
  if (after === undefined)
    return { position: (before ?? -1) + 1, moves: [] as Placed[] };
  if (before === undefined && after > 0)
    return { position: after - 1, moves: [] as Placed[] };
  if (before !== undefined && after - before > 1)
    return {
      position: before + Math.floor((after - before) / 2),
      moves: [] as Placed[],
    };
  // No room: spread the list ten apart, leaving a gap at `index`.
  const base = list[0]?.position ?? 0;
  const moves: Placed[] = [];
  list.forEach((entry, at) => {
    const position = base + (at < index ? at : at + 1) * 10;
    if (position !== entry.position) moves.push({ ...entry, position });
  });
  return { position: base + index * 10, moves };
}

// --- Skills of the whole record ---

/** Every skill once (first spelling), the most used first. */
export function allSkills(entries: { skills?: string[] }[]) {
  const counts = new Map<string, { name: string; count: number; at: number }>();
  let at = 0;
  for (const entry of entries)
    for (const skill of entry.skills ?? []) {
      const key = skill.trim().toLowerCase();
      if (!key) continue;
      const found = counts.get(key);
      if (found) found.count++;
      else counts.set(key, { name: skill.trim(), count: 1, at: at++ });
    }
  return [...counts.values()]
    .sort((a, b) => b.count - a.count || a.at - b.at)
    .map((item) => item.name);
}

/** Add skills typed with commas, without case-insensitive duplicates. */
export function addSkills(current: string[], typed: string) {
  const next = [...current];
  for (const raw of typed.split(",")) {
    const skill = raw.trim();
    if (
      skill &&
      !next.some((item) => item.toLowerCase() === skill.toLowerCase())
    )
      next.push(skill);
  }
  return next;
}

/** The text of a link: its label, or the address without the scheme. */
export function linkText(link: { label?: string; url?: string }) {
  return (
    link.label?.trim() ||
    (link.url || "").replace(/^https?:\/\//, "").replace(/\/$/, "")
  );
}

/** An address a person typed, made absolute: "example.dev" → https://… */
export function linkHref(url: string) {
  const value = url.trim();
  if (!value) return "";
  if (/^(https?:|mailto:)/i.test(value)) return value;
  return `https://${value}`;
}
