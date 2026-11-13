// Words and list operations of the Preferences screen, kept free of React.
import type {
  PreferenceItem,
  PreferenceSectionName,
  WritingScope,
} from "../../api";

export const scopeLabels: Record<WritingScope, string> = {
  all: "All documents",
  cv: "CV",
  letter: "Letter",
};

/** What each section's empty state says. */
export const emptyWords: Record<PreferenceSectionName, string> = {
  looking_for:
    "Nothing yet. Say which roles, places and conditions make a job worth a look.",
  ruled_out: "Nothing yet. Say what makes a job not worth applying to.",
  facts:
    "Nothing yet. Record what employers ask about: work authorization, start date, notice, salary.",
  writing:
    "No writing rules yet. Say how your CV and letters are written, and what they never say.",
  working_with_me:
    "Nothing yet. Tell your agent how to work with you: what to ask first, what never to do.",
};

/** A statement's name inside the labels of its controls: its first words. */
export function itemName(text: string, size = 40) {
  const line = text.replace(/\s+/g, " ").trim();
  return line.length > size ? `${line.slice(0, size - 1).trimEnd()}…` : line;
}

/** The request body's items: only a writing rule carries a scope. */
export function itemsBody(
  section: PreferenceSectionName,
  items: PreferenceItem[],
): PreferenceItem[] {
  return items.map((item) =>
    section === "writing"
      ? { text: item.text, scope: item.scope || "all" }
      : { text: item.text },
  );
}

/** The list with the item at `index` moved one place up (-1) or down (1). */
export function moved<T>(items: T[], index: number, step: -1 | 1) {
  const next = [...items];
  const other = index + step;
  if (other < 0 || other >= next.length) return next;
  [next[index], next[other]] = [next[other], next[index]];
  return next;
}

/**
 * Where an edited statement is now: the same place if it still holds the
 * original text, else the first statement with that text, else -1 (it was
 * removed elsewhere, and saving adds it again).
 */
export function placeOf(
  items: PreferenceItem[],
  index: number,
  original: string,
) {
  if (items[index]?.text === original) return index;
  return items.findIndex((item) => item.text === original);
}

/** The section with one statement saved: replaced in place, or added at the end. */
export function saved(
  items: PreferenceItem[],
  draft: PreferenceItem,
  index: number,
  original: string | null,
) {
  const at = original === null ? -1 : placeOf(items, index, original);
  if (at < 0) return [...items, draft];
  return items.map((item, position) => (position === at ? draft : item));
}

/** A no-reply period typed by the owner, in whole days from 1 to 365, or null. */
export function replyDays(text: string) {
  const value = Number(text.trim());
  return Number.isInteger(value) && value >= 1 && value <= 365 ? value : null;
}
