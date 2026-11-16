// What the Sources screen says about a source, a check and the schedule.
// Pure functions without React, so they are tested on their own
// (tests/sources.test.mjs).
import type { components } from "../../api/schema";
import { formatDate, formatDay } from "../../ui/format.ts";

/** A source as the screen reads it: the API's Source. */
export type SourceView = components["schemas"]["Source"];

/** A collection run (a check) as Recent checks reads it. */
export type CheckView = components["schemas"]["CollectionRun"];

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

// The markets Indeed and Glassdoor have a site for: the stored value (the
// collector's name for it) and the name a person reads.
const MARKETS = [
  "argentina", "australia", "austria", "bahrain", "belgium", "brazil",
  "canada", "chile", "china", "colombia", "costa rica", "czech republic",
  "denmark", "ecuador", "egypt", "finland", "france", "germany", "greece",
  "hong kong", "hungary", "india", "indonesia", "ireland", "israel", "italy",
  "japan", "kuwait", "luxembourg", "malaysia", "mexico", "morocco",
  "netherlands", "new zealand", "nigeria", "norway", "oman", "pakistan",
  "panama", "peru", "philippines", "poland", "portugal", "qatar", "romania",
  "saudi arabia", "singapore", "south africa", "south korea", "spain",
  "sweden", "switzerland", "taiwan", "thailand", "türkiye", "ukraine",
  "united arab emirates", "uk", "usa", "uruguay", "venezuela", "vietnam",
]; // prettier-ignore
const MARKET_NAMES: Record<string, string> = {
  uk: "United Kingdom",
  usa: "United States",
};
const marketName = (value: string) =>
  MARKET_NAMES[value] ??
  value.replace(/(^|\s)\p{L}/gu, (letter) => letter.toUpperCase());
/** The countries a search can name, by the name a person reads. */
export const COUNTRIES: [value: string, label: string][] = MARKETS.map(
  (value): [string, string] => [value, marketName(value)],
).sort((a, b) => a[1].localeCompare(b[1], "en"));

/** The country a free-text location names ("Zurich, Switzerland"), if any. */
export function countryIn(location: string) {
  const words = location.toLowerCase();
  return (
    COUNTRIES.find(([value, label]) =>
      new RegExp(
        `(^|[\\s,(])(${value}|${label.toLowerCase()})($|[\\s,)])`,
        "u",
      ).test(words),
    )?.[0] ?? ""
  );
}

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
 * "Data engineer · Zurich · LinkedIn, Indeed", "Greenhouse" or "RSS feed · example.test".
 * A board's internal slug is not shown; the source's name says which board.
 */
export function describeSource(
  source: SourceView,
  labels: Record<string, string> = {},
) {
  const kind = kindOf(source);
  if (kind === "search")
    return [
      text(source.config.query),
      text(source.config.location) || marketName(text(source.config.country)),
      sitesLine(source),
    ]
      .filter(Boolean)
      .join(" · ");
  const where = source.url
    ? shortUrl(source.url)
    : text(source.config.url)
      ? shortUrl(text(source.config.url))
      : "";
  const label =
    kind === "feed"
      ? "RSS feed"
      : (labels[source.kind] ?? capitalize(source.kind));
  return [label, where].filter(Boolean).join(" · ");
}

const COUNT_WORDS = {
  found: "found",
  shortlisted: "ever shortlisted",
  applied: "applied",
} as const;
/** What the counts add up: every job the source found, closed ones included. */
export const COUNTS_HINT =
  "Every job this source found, what you ever shortlisted (closed applications included) and applied to.";

/** "31 found · 9 ever shortlisted · 3 applied", without zeros. */
export function countsLine(counts?: Record<string, number> | null) {
  if (!counts) return "";
  return (Object.keys(COUNT_WORDS) as (keyof typeof COUNT_WORDS)[])
    .filter((key) => (counts[key] ?? 0) > 0)
    .map((key) => `${counts[key]} ${COUNT_WORDS[key]}`)
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
  if (run && isActive(run.state)) {
    const counts = (run.counts ?? {}) as Record<string, unknown>;
    const listed = number(counts.listed);
    return {
      text: listed
        ? `Checking now… · fetched ${Math.min(number(counts.received), listed)} of ${listed}`
        : "Checking now…",
      running: true,
    };
  }
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
  // A paused source says so beside its name.
  if (!when) return { text: "Not checked yet" };
  const counts = (run?.counts ?? source.last_counts ?? {}) as Record<
    string,
    unknown
  >;
  const fresh = number(counts.created);
  return {
    text: `Checked ${ago(when, now)} · ${fresh ? `${fresh} new` : "nothing new"}`,
  };
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

/**
 * A reason the server gives for a wait ("… waits until 14:05 UTC …"), with
 * the time in the viewer's own clock when the wait's moment is known.
 */
export function localReason(message: string, until?: unknown) {
  if (typeof until !== "string" || !until) return message;
  const local = clock(until);
  return local ? message.replace(/\b\d{2}:\d{2} UTC\b/, local) : message;
}

/** Whether a previewed posting came with its text. */
export const hasText = (item: Record<string, unknown>) =>
  typeof item.posting === "string" && item.posting.trim() !== "";

type Previewed = {
  items: Record<string, unknown>[];
  total: number;
  listed?: number | null;
};

/**
 * A Test's listing with the text one posting's answer brought. The rest of
 * the answer (its diagnostics) replaces the earlier one's; a refusal keeps
 * the titles the listing gave.
 */
export function withText<T extends Previewed>(before: T, answer: T): T {
  const id = (item: Record<string, unknown>) =>
    String(item.source_key ?? item.url);
  const arrived = new Map(
    answer.items.filter(hasText).map((item) => [id(item), item]),
  );
  return {
    ...answer,
    items: before.items.map((item) => arrived.get(id(item)) ?? item),
    total: before.total,
    listed: answer.listed ?? before.listed,
  };
}

/** What a Test is doing or found: its heading. */
export function testHeading({
  phase,
  total,
  shown,
  listed,
  failed,
  fetched = 0,
  fetching = shown,
}: {
  /** "listing" until the board answers, "details" while the text arrives. */
  phase: "listing" | "details" | "done";
  total: number;
  shown: number;
  listed?: number | null;
  failed?: boolean;
  /** While the text arrives: the postings that have it, of how many. */
  fetched?: number;
  fetching?: number;
}) {
  const count = listed ?? total;
  const jobs = `${count} ${count === 1 ? "job" : "jobs"}`;
  if (phase === "listing") return "Testing…";
  if (phase === "details")
    return `${jobs} listed · fetched ${fetched} of ${fetching}…`;
  if (failed) return "Test failed";
  if (!total && !count) return "No jobs found";
  return shown < count ? `${jobs} found · the first ${shown}` : `${jobs} found`;
}

/** The advice under an empty or refused search: a careers page is read directly. */
export const CAREERS_ADVICE =
  "Job sites can answer with nothing or refuse requests from your network. A company's careers page is read directly: follow one instead.";
