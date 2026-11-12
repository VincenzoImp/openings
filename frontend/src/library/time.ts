// Times as the owner reads them: "Today 09:12", "Yesterday 18:12", "6 Nov".
// Pure functions of a value and "now", so they can be tested without a clock.

const DAY = 86_400_000;
const startOfDay = (d: Date) =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
/** Whole local days from `value` to `now`: 0 today, 1 yesterday, -1 tomorrow. */
export function daysAgo(value: Date, now = new Date()) {
  return Math.round((startOfDay(now) - startOfDay(value)) / DAY);
}
const parse = (value?: string | null) => {
  const d = value ? new Date(value) : null;
  return d && !Number.isNaN(d.valueOf()) ? d : null;
};

/** "09:31" in the owner's time zone. */
export function clock(value?: string | null) {
  const d = parse(value);
  return d
    ? d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : "";
}
/** "6 Nov", with the year when it is not this one. */
export function shortDate(d: Date, now = new Date()) {
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: d.getFullYear() === now.getFullYear() ? undefined : "numeric",
  });
}
/** The heading of a day in a timeline: "Today", "Yesterday", "Monday 9 November". */
export function dayLabel(value?: string | null, now = new Date()) {
  const d = parse(value);
  if (!d) return "Earlier";
  const ago = daysAgo(d, now);
  if (ago === 0) return "Today";
  if (ago === 1) return "Yesterday";
  return d.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: d.getFullYear() === now.getFullYear() ? undefined : "numeric",
  });
}
/** When something happened: "Today 09:12", "Monday 19:05", "6 Nov". */
export function dayTime(value?: string | null, now = new Date()) {
  const d = parse(value);
  if (!d) return "";
  const ago = daysAgo(d, now);
  if (ago === 0) return `Today ${clock(value)}`;
  if (ago === 1) return `Yesterday ${clock(value)}`;
  if (ago > 1 && ago < 7)
    return `${d.toLocaleDateString("en-GB", { weekday: "long" })} ${clock(value)}`;
  return shortDate(d, now);
}
/** A length of time in the unit a person would say: "41 min", "2 h 5 min". */
export function duration(from?: string | null, to?: string | null) {
  const start = parse(from),
    end = parse(to);
  if (!start || !end) return "";
  const minutes = Math.round((end.valueOf() - start.valueOf()) / 60_000);
  if (minutes < 1) return "under a minute";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48)
    return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  return `${Math.round(hours / 24)} days`;
}

export interface DeadlineTag {
  text: string;
  tone: "danger" | "attention" | "neutral";
}
/** The tag of a calendar deadline (YYYY-MM-DD): overdue, tomorrow, this week, later. */
export function deadlineTag(
  deadline?: string | null,
  now = new Date(),
): DeadlineTag | null {
  if (!deadline) return null;
  const [year, month, day] = deadline.slice(0, 10).split("-").map(Number);
  const d = new Date(year, month - 1, day);
  if (Number.isNaN(d.valueOf())) return null;
  const left = -daysAgo(d, now);
  const date = shortDate(d, now);
  if (left < 0) return { text: `Overdue since ${date}`, tone: "danger" };
  if (left === 0) return { text: "Closes today", tone: "danger" };
  if (left === 1) return { text: "Closes tomorrow", tone: "danger" };
  return { text: `Closes ${date}`, tone: left <= 7 ? "attention" : "neutral" };
}

/** A calendar day `days` before `now`, as YYYY-MM-DD in UTC (the API's dates). */
export function dayBefore(days: number, now = new Date()) {
  return new Date(now.valueOf() - days * DAY).toISOString().slice(0, 10);
}
