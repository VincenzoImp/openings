// Words and list operations of the Preferences screen, kept free of React.
import type { Scope, SectionName, Statement } from "../../query/preferences";

export interface SectionInfo {
  name: SectionName;
  title: string;
  /** Two grey example statements shown while the section is empty. */
  examples: Statement[];
}

/** The five sections, in their fixed order. */
export const SECTIONS: SectionInfo[] = [
  {
    name: "looking_for",
    title: "What I'm looking for",
    examples: [
      { text: "Backend or data engineering roles, senior or staff." },
      { text: "Zurich or Basel, or remote within Europe." },
    ],
  },
  {
    name: "ruled_out",
    title: "What I rule out",
    examples: [
      { text: "No defence or gambling companies." },
      { text: "No relocation outside Switzerland." },
    ],
  },
  {
    name: "facts",
    title: "Facts about me",
    examples: [
      { text: "EU citizen with a Swiss B permit." },
      { text: "Notice period: three months to the end of a month." },
    ],
  },
  {
    name: "writing",
    title: "Writing rules",
    examples: [
      { text: "British spelling, plain words.", scope: "all" },
      { text: "Three short paragraphs, under 200 words.", scope: "letter" },
    ],
  },
  {
    name: "working_with_me",
    title: "Working with me",
    examples: [
      { text: "Ask before preparing anything in French." },
      { text: "Show me a sample before dismissing many jobs at once." },
    ],
  },
];

export const sectionTitle = (name: SectionName) =>
  SECTIONS.find((section) => section.name === name)?.title ?? name;

export const SCOPES: { value: Scope; label: string }[] = [
  { value: "all", label: "All" },
  { value: "cv", label: "CV" },
  { value: "letter", label: "Letter" },
];
export const scopeLabels: Record<Scope, string> = {
  all: "All",
  cv: "CV",
  letter: "Letter",
};

/** A statement's name inside the labels of its controls: its first words. */
export function itemName(text: string, size = 40) {
  const line = text.replace(/\s+/g, " ").trim();
  return line.length > size ? `${line.slice(0, size - 1).trimEnd()}…` : line;
}

/** The request body's items: only a writing rule carries a scope. */
export function itemsBody(
  section: SectionName,
  items: Statement[],
): Statement[] {
  return items.map((item) =>
    section === "writing"
      ? { text: item.text, scope: item.scope || "all" }
      : { text: item.text },
  );
}

/** The list with the item at `index` moved one place up (-1) or down (1). */
export function moved<T>(items: T[], index: number, step: -1 | 1) {
  return reordered(items, index, index + step);
}

/** The list with the item at `from` placed at `to` (a drag). */
export function reordered<T>(items: T[], from: number, to: number) {
  const next = [...items];
  if (from < 0 || from >= next.length || to < 0 || to >= next.length)
    return next;
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/** Where a dragged row lands: the index whose middle the pointer passed. */
export function dropIndex(middles: number[], from: number, y: number) {
  return middles.filter((middle, at) => at !== from && middle < y).length;
}

/**
 * Where an edited statement is now: the same place if it still holds the
 * original text, else the first statement with that text, else -1 (it was
 * removed elsewhere, and saving adds it again).
 */
export function placeOf(items: Statement[], index: number, original: string) {
  if (items[index]?.text === original) return index;
  return items.findIndex((item) => item.text === original);
}

/** The section with one statement saved: replaced in place, or added at the end. */
export function saved(
  items: Statement[],
  draft: Statement,
  index: number,
  original: string | null,
) {
  const at = original === null ? -1 : placeOf(items, index, original);
  if (at < 0) return [...items, draft];
  return items.map((item, position) => (position === at ? draft : item));
}

/** The section without the statement at `index` (found again by its text). */
export function removed(items: Statement[], index: number, text: string) {
  const at = placeOf(items, index, text);
  return at < 0 ? items : items.filter((_, position) => position !== at);
}

/** A no-reply period typed by the owner, in whole days from 1 to 365, or null. */
export function replyDays(text: string) {
  const value = Number(text.trim());
  return Number.isInteger(value) && value >= 1 && value <= 365 ? value : null;
}

/** "Hides 4 of your 31 new jobs in Jobs" */
export function hiddenLine(hidden: number, total: number) {
  const jobs = total === 1 ? "new job" : "new jobs";
  return `Hides ${hidden} of your ${total} ${jobs} in Jobs`;
}

/** The languages Preferences offers, by ISO 639-1 code. */
export const LANGUAGES: Record<string, string> = {
  en: "English",
  de: "German",
  fr: "French",
  it: "Italian",
  es: "Spanish",
  nl: "Dutch",
  pt: "Portuguese",
  pl: "Polish",
  sv: "Swedish",
  da: "Danish",
  no: "Norwegian",
  fi: "Finnish",
  cs: "Czech",
  ru: "Russian",
  ja: "Japanese",
  zh: "Chinese",
  ar: "Arabic",
  tr: "Turkish",
  ko: "Korean",
};
export const languageName = (code: string) => LANGUAGES[code] || code;
