// One format per kind of value (principle P12). Dates are relative within a
// week, then "13 Nov", with the year only when it is not the current one.
// Nothing in the interface is written in ISO.

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** The empty value: a dash in text-3, or the field is omitted. */
export const EMPTY = "—";

/** A moment; a date-only "2026-11-12" is that local day, not UTC midnight. */
function toDate(value: Date | string | number) {
  if (value instanceof Date) return value;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, date] = value.split("-").map(Number);
    return new Date(year, month - 1, date);
  }
  return new Date(value);
}

/** The local calendar day of a moment or of "2026-11-12", at midnight. */
export function dayOf(value: Date | string | number) {
  const date = toDate(value);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
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
export function daysBetween(
  from: Date | string | number,
  to: Date | string | number,
) {
  return Math.round((dayOf(to).getTime() - dayOf(from).getTime()) / DAY);
}

/** "13 Nov", or "13 Nov 2025" when the year is not the current one. */
export function formatDay(value: Date | string | number, now = new Date()) {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return EMPTY;
  const day = `${date.getDate()} ${MONTHS[date.getMonth()]}`;
  return date.getFullYear() === now.getFullYear()
    ? day
    : `${day} ${date.getFullYear()}`;
}

/**
 * A moment in the past ("found", "updated"): "Just now", "5m", "3h",
 * "Yesterday", "4d", then the day. A moment in the future (a deadline):
 * "Today", "Tomorrow", then the day.
 */
export function formatDate(value: Date | string | number, now = new Date()) {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return EMPTY;
  const diff = now.getTime() - date.getTime();
  const days = daysBetween(now, date);
  if (diff < 0) {
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    return formatDay(date, now);
  }
  if (diff < MINUTE) return "Just now";
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)}m`;
  if (diff < DAY && days === 0) return `${Math.floor(diff / HOUR)}h`;
  if (days === -1) return "Yesterday";
  if (days > -7) return `${-days}d`;
  return formatDay(date, now);
}

/** The time of day on the 24-hour clock: "14:05". */
export function formatTime(value: Date | string | number) {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return EMPTY;
  return `${String(date.getHours()).padStart(2, "0")}:${String(
    date.getMinutes(),
  ).padStart(2, "0")}`;
}

/** The full moment for a tooltip: "Fri 13 Nov 2026, 14:05". */
export function formatFull(value: Date | string | number) {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return EMPTY;
  return `${WEEKDAYS[date.getDay()]} ${date.getDate()} ${
    MONTHS[date.getMonth()]
  } ${date.getFullYear()}, ${formatTime(date)}`;
}

/** A count with its noun: "1 job", "3 jobs", "2 entries". */
export function plural(count: number, one: string, many = `${one}s`) {
  return `${formatNumber(count)} ${count === 1 ? one : many}`;
}

const numbers = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat("en-GB", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** A count or amount: "25,000"; compact counts read "25k". */
export function formatNumber(
  value: number | null | undefined,
  { compact: short = false } = {},
) {
  if (value == null || Number.isNaN(value)) return EMPTY;
  return (short && Math.abs(value) >= 10_000 ? compact : numbers)
    .format(value)
    .toLowerCase();
}
