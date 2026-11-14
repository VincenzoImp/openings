// What Today shows, derived from application rows and counts. No React and
// no imports: tested directly (tests/today.test.mjs).

/** The fields of an application row Today reads. */
export interface Row {
  id: string;
  status: string;
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

const DAY = 86_400_000;

/** A local calendar day as YYYY-MM-DD. */
export function localDay(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Whole days from today to a YYYY-MM-DD day (negative when past). */
export function daysUntil(day: string, now = new Date()) {
  const [year, month, date] = day.slice(0, 10).split("-").map(Number);
  const target = new Date(year, month - 1, date).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target - today.getTime()) / DAY);
}

const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
const WEEKDAYS = "Sun Mon Tue Wed Thu Fri Sat".split(" ");
function shortDay(day: string, now: Date) {
  const [year, month, date] = day.slice(0, 10).split("-").map(Number);
  const text = `${date} ${MONTHS[month - 1]}`;
  return year === now.getFullYear() ? text : `${text} ${year}`;
}

export type Tone = "warning" | "danger";

/**
 * A deadline as a row says it: overdue in danger, within a week in warning,
 * later in plain text.
 */
export function deadlineText(
  deadline: string | null | undefined,
  now = new Date(),
): { text: string; tone?: Tone } | null {
  if (!deadline) return null;
  const days = daysUntil(deadline, now);
  if (days < 0)
    return { text: `Closed ${shortDay(deadline, now)}`, tone: "danger" };
  if (days === 0) return { text: "Closes today", tone: "warning" };
  if (days === 1) return { text: "Closes tomorrow", tone: "warning" };
  if (days <= 7) {
    const [year, month, date] = deadline.slice(0, 10).split("-").map(Number);
    const weekday = WEEKDAYS[new Date(year, month - 1, date).getDay()];
    const when = days < 7 ? weekday : shortDay(deadline, now);
    return { text: `Closes ${when}`, tone: "warning" };
  }
  return { text: `Closes ${shortDay(deadline, now)}` };
}

/** Whether a deadline falls in the next seven days (today included). */
export const dueThisWeek = (
  deadline: string | null | undefined,
  now = new Date(),
) =>
  Boolean(deadline) &&
  daysUntil(deadline!, now) >= 0 &&
  daysUntil(deadline!, now) <= 7;

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
    (row) => !row.ready && row.deadline && daysUntil(row.deadline, now) <= 7,
  );
  const open = shortlisted.filter(
    (row) => row.ready && row.open_requirements > 0,
  );
  return [...due, ...open];
}

/** Whole days since an application was sent. */
export const daysSince = (moment: string, now = new Date()) =>
  Math.max(0, -daysUntil(localDay(new Date(moment)), now));

/** "Data Engineer" and "Northstar Labs", with a fallback title. */
export function roleOf(row: Pick<Row, "job">) {
  return {
    title: String(row.job.title || "") || "Untitled role",
    company: String(row.job.company || ""),
  };
}
