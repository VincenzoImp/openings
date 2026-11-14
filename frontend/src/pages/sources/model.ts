// What the Sources screen says about a source, a check and the schedule.
// Pure functions without React, so they are tested on their own
// (tests/sources.test.mjs).
import { formatDate, formatDay } from "../../ui/format.ts";

/** A source as the screen reads it (the API's Source, structurally). */
export interface SourceView {
  id: string;
  name: string;
  kind: string;
  url: string;
  enabled: boolean;
  automatic_collection: boolean;
  version: number;
  config: Record<string, unknown>;
  filters: Record<string, unknown>;
  schedule: Record<string, unknown>;
  counts?: Record<string, number>;
  last_run?: Record<string, unknown> | null;
  last_error?: string | null;
  last_outcome?: string | null;
  last_run_at?: unknown;
  last_counts?: unknown;
  next_run_at?: string | null;
}

/** A collection run (a check) as Recent checks reads it. */
export interface CheckView {
  id: string;
  state: string;
  source_id?: string | null;
  source_name?: string | null;
  counts?: Record<string, unknown>;
  tasks?: Record<string, unknown>[];
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

/** The three kinds a person chooses between. */
export type SourceKind = "search" | "company" | "feed";

export const KIND_LABELS: Record<SourceKind, string> = {
  search: "Search",
  company: "Company careers page",
  feed: "RSS feed",
};

export function kindOf(source: { kind: string }): SourceKind {
  if (source.kind === "jobspy") return "search";
  if (source.kind === "rss") return "feed";
  return "company";
}

/** The job sites a search asks, by id, in the order of the form. */
export const SITES: [string, string][] = [
  ["linkedin", "LinkedIn"],
  ["indeed", "Indeed"],
  ["glassdoor", "Glassdoor"],
];
/** Sites that search one country's site, and so need a country. */
export const NATIONAL_SITES = ["indeed", "glassdoor"];

const siteName = (id: string) =>
  SITES.find(([key]) => key === id)?.[1] ?? capitalize(id);

export function capitalize(value: string) {
  return value ? value[0].toUpperCase() + value.slice(1) : value;
}

/** "boards.greenhouse.io/northstar" from a URL, without the scheme. */
export function shortUrl(url: string) {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.replace(/\/$/, "");
    return parsed.host.replace(/^www\./, "") + path;
  } catch {
    return url;
  }
}

const text = (value: unknown) =>
  typeof value === "string" ? value.trim() : "";
const list = (value: unknown) =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];

/** The sites a search asks, as names: "LinkedIn, Indeed". */
export function sitesLine(source: SourceView) {
  return list(source.config.providers).map(siteName).join(", ");
}

/**
 * What a source searches, in one line, without empty parts:
 * "Data engineer · Zurich · LinkedIn, Indeed" or "Greenhouse · northstar".
 */
export function describeSource(
  source: SourceView,
  labels: Record<string, string> = {},
) {
  const kind = kindOf(source);
  if (kind === "search")
    return [
      text(source.config.query),
      text(source.config.location) || capitalize(text(source.config.country)),
      sitesLine(source),
    ]
      .filter(Boolean)
      .join(" · ");
  const where = source.url
    ? shortUrl(source.url)
    : text(source.config.url)
      ? shortUrl(text(source.config.url))
      : text(source.config.board);
  const label =
    kind === "feed"
      ? "RSS feed"
      : (labels[source.kind] ?? capitalize(source.kind));
  return [label, where].filter(Boolean).join(" · ");
}

/** "31 found · 9 shortlisted · 3 applied", without zeros. */
export function countsLine(counts?: Record<string, number> | null) {
  if (!counts) return "";
  return (["found", "shortlisted", "applied"] as const)
    .filter((key) => (counts[key] ?? 0) > 0)
    .map((key) => `${counts[key]} ${key}`)
    .join(" · ");
}

/** "3h ago", "yesterday", "on 13 Nov": a past moment in a sentence. */
export function ago(value: string | Date, now = new Date()) {
  const short = formatDate(value, now);
  if (/^\d+[mhd]$/.test(short)) return `${short} ago`;
  if (short === "Just now") return "just now";
  if (short === "Yesterday") return "yesterday";
  return `on ${short}`;
}

/** "14:00" today, "tomorrow 03:30", or "13 Nov 14:00": a coming moment. */
export function clock(value: string | Date, now = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const time = `${String(date.getHours()).padStart(2, "0")}:${String(
    date.getMinutes(),
  ).padStart(2, "0")}`;
  const day = formatDate(date, now);
  if (date.getTime() <= now.getTime() || day === "Today") return time;
  if (day === "Tomorrow") return `tomorrow ${time}`;
  return `${formatDay(date, now)} ${time}`;
}

const ACTIVE = ["queued", "running"];
export const isActive = (state: unknown) =>
  typeof state === "string" && ACTIVE.includes(state);

/** The first sentence of an error, as the tail of "Last check failed: …". */
export function reason(error: string) {
  const first = error
    .trim()
    .split(/(?<=[.!?])\s/)[0]
    .replace(/[.!]$/, "");
  return first ? first[0].toLowerCase() + first.slice(1) : "no reason given";
}

const number = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;

export interface SourceStatus {
  text: string;
  /** Danger: the row's one coloured signal, with Details. */
  failed?: boolean;
  running?: boolean;
}

/**
 * Where a source stands, in one line: checking now, its last check failed,
 * "Checked 2h ago · 4 new", or not checked yet.
 */
export function sourceStatus(
  source: SourceView,
  now = new Date(),
): SourceStatus {
  const run = source.last_run ?? null;
  if (run && isActive(run.state))
    return { text: "Checking now…", running: true };
  if (!source.automatic_collection)
    return {
      text: "Can't be checked automatically: the site gives no posting text",
      failed: true,
    };
  const failed =
    source.last_outcome === "failed" ||
    run?.state === "failed" ||
    (!!source.last_error && run?.state !== "succeeded");
  if (failed)
    return {
      text: `Last check failed: ${reason(source.last_error || "")}`,
      failed: true,
    };
  const when =
    (run?.finished_at as string | undefined) ||
    (source.last_run_at as string | undefined) ||
    (run?.started_at as string | undefined);
  if (!when) return { text: source.enabled ? "Not checked yet" : "Paused" };
  const counts = (run?.counts ?? source.last_counts ?? {}) as Record<
    string,
    unknown
  >;
  const fresh = number(counts.created);
  const checked = `Checked ${ago(when, now)} · ${fresh ? `${fresh} new` : "nothing new"}`;
  return { text: source.enabled ? checked : `Paused · ${checked}` };
}

/** Failing sources first, then active ones, then paused; by name within. */
export function sortSources<T extends SourceView>(sources: T[]) {
  const rank = (source: T) =>
    sourceStatus(source).failed ? 0 : source.enabled ? 1 : 2;
  return [...sources].sort(
    (a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name),
  );
}

// The schedule. Each source keeps its own; the screen shows and sets one
// interval for all of them.
export const INTERVALS = [60, 180, 360, 720, 1440];

/** "6 h", "45 min", "1 day". */
export function intervalLabel(minutes: number) {
  if (minutes === 1440) return "24 h";
  if (minutes % 1440 === 0) return `${minutes / 1440} days`;
  if (minutes % 60 === 0) return `${minutes / 60} h`;
  return `${minutes} min`;
}

/** A source's interval in minutes; null for daily times. */
export function intervalOf(schedule: Record<string, unknown>) {
  if (schedule.kind === "daily") return null;
  return number(schedule.minutes) || 1440;
}

/** The interval every source shares, or null when they differ. */
export function commonInterval(sources: SourceView[]) {
  const values = new Set(sources.map((source) => intervalOf(source.schedule)));
  if (values.size !== 1) return null;
  return [...values][0];
}

/** The country most searches use, to prefill a new one. */
export function usualCountry(sources: SourceView[]) {
  const seen = new Map<string, number>();
  for (const source of sources) {
    const country = text(source.config.country);
    if (country) seen.set(country, (seen.get(country) ?? 0) + 1);
  }
  return [...seen].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
}

/** "Data engineer · Zurich": a name for a search left unnamed. */
export function suggestedName(
  kind: SourceKind,
  values: { query?: string; location?: string; url?: string },
) {
  if (kind === "search")
    return [values.query?.trim(), values.location?.trim()]
      .filter(Boolean)
      .join(" · ");
  const url = values.url?.trim();
  if (!url) return "";
  const detected = detectBoard(url);
  return detected?.board ? capitalize(detected.board) : shortUrl(url);
}

/**
 * The service of a careers page, read from its address, to show it before a
 * Test. The server detects it again on Test and Save (and may look inside a
 * page this does not recognise).
 */
export function detectBoard(
  url: string,
): { kind: string; board: string } | null {
  let parsed: URL;
  try {
    parsed = new URL(url.trim());
  } catch {
    return null;
  }
  const host = parsed.hostname.toLowerCase();
  const parts = parsed.pathname.split("/").filter(Boolean);
  const suffix = (end: string, kind: string) =>
    host.endsWith(end) ? { kind, board: host.slice(0, -end.length) } : null;
  if (/^(job-)?boards(-api)?\.greenhouse\.io$/.test(host))
    return {
      kind: "greenhouse",
      board:
        parsed.searchParams.get("for") ||
        (parts[0] === "v1" ? parts[2] : parts[0]) ||
        "",
    };
  if (/^(jobs|api)(\.eu)?\.lever\.co$/.test(host))
    return { kind: "lever", board: parts[0] === "v0" ? parts[2] : parts[0] };
  if (/^(jobs|api)\.ashbyhq\.com$/.test(host))
    return {
      kind: "ashby",
      board: host.startsWith("api") ? parts[2] : parts[0],
    };
  if (host === "apply.workable.com")
    return { kind: "workable", board: parts[0] };
  if (/^(jobs|careers)\.smartrecruiters\.com$/.test(host))
    return { kind: "smartrecruiters", board: parts[0] };
  if (host === "ats.rippling.com") return { kind: "rippling", board: parts[0] };
  if (host === "join.com" && parts[0] === "companies")
    return { kind: "joincom", board: parts[1] };
  if (/\.wd\d+\.myworkdayjobs\.com$/.test(host))
    return { kind: "workday", board: host.split(".")[0] };
  if (host.endsWith(".oraclecloud.com"))
    return { kind: "oracle", board: host.split(".")[0] };
  return (
    suffix(".recruitee.com", "recruitee") ??
    suffix(".jobs.personio.de", "personio") ??
    suffix(".breezy.hr", "breezy") ??
    suffix(".bamboohr.com", "bamboohr")
  );
}

/** The job sites the sources ask, as provider ids of the request gate. */
export function sitesInUse(sources: SourceView[]) {
  const ids = new Set<string>();
  for (const source of sources) {
    if (source.kind === "jobspy")
      for (const site of list(source.config.providers)) ids.add(site);
    else ids.add(source.kind);
  }
  return ids;
}

/** What one check found, or why it failed. */
export function checkLine(check: CheckView) {
  if (check.state === "running") return "Checking now…";
  if (check.state === "queued") return "Waiting to start";
  if (check.state === "cancelled") return "Stopped";
  if (check.state === "failed") {
    const error = check.tasks
      ?.map((task) => task.error)
      .find((value): value is string => typeof value === "string" && !!value);
    return `Failed: ${reason(error || "")}`;
  }
  const counts = check.counts ?? {};
  const found = number(counts.received);
  const fresh = number(counts.created);
  if (!found) return "Nothing found";
  return `${found} found · ${fresh ? `${fresh} new` : "nothing new"}`;
}

/** The failed tasks of a check, to queue them again. */
export function failedTasks(check: CheckView) {
  return (check.tasks ?? [])
    .filter((task) => task.state === "failed" && typeof task.id === "string")
    .map((task) => task.id as string);
}

/** Comma-separated words as a list, without empty ones. */
export function terms(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

/** "Posted within" choices, in hours. */
export const POSTED_WITHIN: [number, string][] = [
  [24, "24 hours"],
  [72, "3 days"],
  [168, "7 days"],
  [336, "14 days"],
  [720, "30 days"],
];
