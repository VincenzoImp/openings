// Deadlines in words, shared by Applications, the application page and
// Today. No React: tested directly.
import { dayOf, daysBetween, formatDay, plural } from "../../ui/format.ts";

const WEEKDAYS = "Sun Mon Tue Wed Thu Fri Sat".split(" ");

/** The workspace's default no-reply period, until a list names its own. */
export const NO_REPLY_DAYS = 30;

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
          : `due ${formatDay(deadline, now)}`;
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
