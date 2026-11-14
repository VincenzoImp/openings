// What Today shows, derived from application rows and counts. No React:
// tested directly (tests/today.test.mjs).
import { daysBetween } from "../../ui/format.ts";

/** The fields of an application row Today reads. */
export interface Row {
  id: string;
  stage: string;
  ready: boolean;
  deadline?: string | null;
  priority?: number | null;
  applied_at?: string | null;
  /** "cv", "letter" and "requirement:<id>" still missing. */
  missing: string[];
  open_requirements: number;
  blocking_requirements: number;
  job: { title?: unknown; company?: unknown };
}

/** Whether a deadline falls in the next seven days (today included). */
export const dueThisWeek = (
  deadline: string | null | undefined,
  now = new Date(),
) =>
  Boolean(deadline) &&
  daysBetween(now, deadline!) >= 0 &&
  daysBetween(now, deadline!) <= 7;

const count = (n: number, one: string, many = `${one}s`) =>
  `${n} ${n === 1 ? one : many}`;

/** The one line under the title: only the parts that are not zero. */
export function summaryParts({
  ready,
  deadlines,
  newJobs,
}: {
  ready: number;
  deadlines: number;
  newJobs: number;
}) {
  return [
    ready && `${ready} ready to apply`,
    deadlines && `${count(deadlines, "deadline")} this week`,
    newJobs && count(newJobs, "new job"),
  ].filter(Boolean) as string[];
}

/** "Good morning", "Good afternoon" or "Good evening", with the first name. */
export function greeting(name: string, now = new Date()) {
  const hour = now.getHours();
  const part =
    hour < 5
      ? "evening"
      : hour < 12
        ? "morning"
        : hour < 18
          ? "afternoon"
          : "evening";
  const first = name.trim().split(/\s+/)[0];
  return first ? `Good ${part}, ${first}` : `Good ${part}`;
}

/** What one application still needs, in a few words. */
export function missingText(
  row: Pick<Row, "missing" | "open_requirements">,
  requirements: Record<string, string> = {},
) {
  const documents = row.missing.filter(
    (item) => item === "cv" || item === "letter",
  );
  if (documents.length)
    return `Missing: ${documents
      .map((item) => (item === "cv" ? "CV" : "letter"))
      .join(" and ")}`;
  const open = row.missing.find((item) => item.startsWith("requirement:"));
  const text = open && requirements[open.slice("requirement:".length)];
  if (text) return `${clip(text, 48)} not done`;
  return row.open_requirements === 1
    ? "1 requirement open"
    : `${row.open_requirements} requirements open`;
}

const clip = (text: string, max: number) =>
  text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;

/**
 * Needs attention: Shortlisted applications due within a week that are not
 * Ready, then Ready ones with an open requirement. Closest deadline first.
 */
export function needsAttention<T extends Row>(
  shortlisted: T[],
  now = new Date(),
) {
  const due = shortlisted.filter(
    (row) => !row.ready && row.deadline && daysBetween(now, row.deadline) <= 7,
  );
  const open = shortlisted.filter(
    (row) => row.ready && row.open_requirements > 0,
  );
  return [...due, ...open];
}

/** Whole days since an application was sent. */
export const daysSince = (moment: string, now = new Date()) =>
  Math.max(0, daysBetween(moment, now));

/** "Data Engineer" and "Northstar Labs", with a fallback title. */
export function roleOf(row: Pick<Row, "job">) {
  return {
    title: String(row.job.title || "") || "Untitled role",
    company: String(row.job.company || ""),
  };
}
