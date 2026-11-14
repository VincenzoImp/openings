// Days and deadlines in words, shared by Applications, the application page
// and Today (which loads only this module). No React: tested directly.
import { plural } from "../../ui/format.ts";

const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
const WEEKDAYS = "Sun Mon Tue Wed Thu Fri Sat".split(" ");
const DAY_MS = 86_400_000;

/** A calendar day from "2026-11-12" or a moment; local, at midnight. */
export function dayOf(value: string | Date) {
  if (value instanceof Date)
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, date] = value.split("-").map(Number);
    return new Date(year, month - 1, date);
  }
  return dayOf(new Date(value));
}

/** "2026-11-14": the local calendar day, as the API takes dates. */
export function isoDay(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

/** Whole calendar days from one day to another (negative when earlier). */
export function daysBetween(from: string | Date, to: string | Date) {
  return Math.round((dayOf(to).getTime() - dayOf(from).getTime()) / DAY_MS);
}

/** "12 Oct", with the year only when it is not the current one. */
export function shortDay(value: string | Date, now = new Date()) {
  const day = dayOf(value);
  const text = `${day.getDate()} ${MONTHS[day.getMonth()]}`;
  return day.getFullYear() === now.getFullYear()
    ? text
    : `${text} ${day.getFullYear()}`;
}

export type Tone = "warning" | "danger";
export interface Phrase {
  text: string;
  tone?: Tone;
}
/** A phrase, with its tone only when it has one. */
export const toned = (text: string, tone?: Tone): Phrase =>
  tone ? { text, tone } : { text };

/**
 * A deadline as a row reads it: "due today", "due Fri" within a week, "due
 * 28 Nov", "overdue 3 days". Warning within three days, danger once passed.
 */
export function deadlinePhrase(
  deadline: string | null | undefined,
  now = new Date(),
): Phrase | null {
  if (!deadline) return null;
  const days = daysBetween(now, deadline);
  if (days < 0)
    return { text: `overdue ${plural(-days, "day")}`, tone: "danger" };
  const text =
    days === 0
      ? "due today"
      : days === 1
        ? "due tomorrow"
        : days < 7
          ? `due ${WEEKDAYS[dayOf(deadline).getDay()]}`
          : `due ${shortDay(deadline, now)}`;
  return toned(text, days <= 3 ? "warning" : undefined);
}

/**
 * A deadline on its own, as Today and the stage lists say it: "Due today",
 * "Due tomorrow", "Due Fri", "Due 28 Nov", "Overdue 3 days".
 */
export function deadlineLabel(
  deadline: string | null | undefined,
  now = new Date(),
): Phrase | null {
  const phrase = deadlinePhrase(deadline, now);
  return phrase && { ...phrase, text: capital(phrase.text) };
}
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
