// What the Jobs screen reads from its address and shows about a job, in
// words: the tab and filters, the list request, the day groups, a row's one
// signal, the properties of the detail and the posting's structure. No
// React and no requests: tested directly (tests/jobs.test.mjs).
import type { Schema } from "../../api/client";
import type { operations } from "../../api/schema";
import { EMPTY, daysBetween, formatDay, isoDay } from "../../ui/format.ts";

export type JobSummary = Schema<"JobSummary">;
export type Job = Schema<"Job">;
export type ListQuery = NonNullable<
  operations["jobs_list"]["parameters"]["query"]
>;

export type Section = "new" | "dismissed" | "all";
export const SECTIONS: { id: Section; label: string }[] = [
  { id: "new", label: "New" },
  { id: "dismissed", label: "Dismissed" },
  { id: "all", label: "All" },
];

/** The filters of the address; each narrows the list and shows as a chip. */
export const FILTERS = [
  "source",
  "company",
  "location",
  "posting_language",
  "requires",
  "signal",
  "created_since",
  "dismissed_by",
  "hide_unspoken",
] as const;
export type FilterKey = (typeof FILTERS)[number];

export const SORTS = {
  newest: "Newest",
  oldest: "Oldest",
  company: "Company",
  title: "Title",
  dismissed: "Recently dismissed",
} as const;
export type Sort = keyof typeof SORTS;

/** The screen's state, read from `#jobs?section=…&job=…&q=…`. */
export interface View {
  section: Section;
  job: string;
  q: string;
  sort: Sort;
  filters: Record<FilterKey, string>;
}

export function readView(query: URLSearchParams): View {
  const section = query.get("section");
  const sort = query.get("sort") as Sort | null;
  const filters = Object.fromEntries(
    FILTERS.map((key) => [key, query.get(key) ?? ""]),
  ) as Record<FilterKey, string>;
  const tab: Section =
    section === "dismissed" || section === "all" ? section : "new";
  return {
    section: tab,
    job: query.get("job") ?? "",
    q: query.get("q") ?? "",
    sort: sort && sort in SORTS ? sort : defaultSort(tab),
    filters,
  };
}

export const defaultSort = (section: Section): Sort =>
  section === "dismissed" ? "dismissed" : "newest";

/** The sorts a tab offers: "Recently dismissed" only in Dismissed. */
export const sortsOf = (section: Section) =>
  (Object.keys(SORTS) as Sort[]).filter(
    (sort) => sort !== "dismissed" || section === "dismissed",
  );

/** The address of a view: only what differs from the defaults is written. */
export function viewQuery(view: View): Record<string, string | undefined> {
  const query: Record<string, string | undefined> = {
    section: view.section === "new" ? undefined : view.section,
    q: view.q || undefined,
    sort: view.sort === defaultSort(view.section) ? undefined : view.sort,
    job: view.job || undefined,
  };
  for (const key of FILTERS) {
    if (key === "dismissed_by" && view.section !== "dismissed") continue;
    query[key] = view.filters[key] || undefined;
  }
  return query;
}

/** Whether any filter (search included) narrows the list. */
export const narrowed = (view: View) =>
  !!view.q || FILTERS.some((key) => activeFilter(view, key));

const activeFilter = (view: View, key: FilterKey) =>
  !!view.filters[key] &&
  (key !== "dismissed_by" || view.section === "dismissed");

/** The list request of a view. */
export function listQuery(view: View, limit: number): ListQuery {
  const { filters } = view;
  const query: ListQuery = {
    limit,
    sort:
      view.sort === "dismissed" && view.section !== "dismissed"
        ? "newest"
        : view.sort,
    include_counts: true,
    // Always named, so the list says how many jobs the switch would hide.
    hide_unspoken_required: filters.hide_unspoken === "true",
  };
  if (view.section !== "all") query.triage = view.section;
  if (view.q.trim()) query.q = view.q.trim();
  for (const key of [
    "source",
    "company",
    "location",
    "posting_language",
    "requires",
    "created_since",
  ] as const)
    if (filters[key]) query[key] = filters[key];
  if (filters.signal === "incomplete") query.complete = false;
  else if (filters.signal)
    query.signal = filters.signal as NonNullable<ListQuery["signal"]>;
  if (view.section === "dismissed" && filters.dismissed_by)
    query.dismissed_by = filters.dismissed_by;
  return query;
}

/* ------------------------------------------------------------- languages */

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
/** The languages a posting's own language is recognised in. */
export const POSTING_LANGUAGES = ["en", "de", "fr", "it"];
const either = (codes: string[]) => codes.map(languageName).join(" or ");

/* ------------------------------------------------------------ the filters */

export const SIGNALS: Record<string, string> = {
  likely_duplicate: "Possible duplicate",
  no_longer_listed: "No longer listed",
  language_required: "Requires a language",
  incomplete: "Text incomplete",
};
export const DISMISSED_BY: Record<string, string> = {
  owner: "You",
  agent: "An agent",
  system: "Job sources",
};

const PROVIDERS: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  glassdoor: "Glassdoor",
  zip_recruiter: "ZipRecruiter",
  google: "Google Jobs",
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  workable: "Workable",
  rss: "Feed",
  manual: "Added by hand",
};
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
/** A source as words: "linkedin" is "LinkedIn". */
export const sourceName = (source: string) =>
  PROVIDERS[source] || capital(source.replaceAll("_", " "));
/** Where a job came from: "LinkedIn", "Greenhouse", "Added by hand". */
export function sourceLabel(job: Pick<JobSummary, "source" | "metadata">) {
  const meta = job.metadata ?? {};
  return sourceName(String(job.source || meta.source || meta.ats || "manual"));
}

/** A chip of an active filter: its field and value, in words. */
export interface Chip {
  key: FilterKey;
  field: string;
  value: string;
}
export function chipsOf(view: View, now = new Date()): Chip[] {
  const chips: Chip[] = [];
  const { filters } = view;
  const add = (key: FilterKey, field: string, value: string) => {
    if (activeFilter(view, key)) chips.push({ key, field, value });
  };
  add("source", "Source", sourceName(filters.source));
  add("company", "Company", filters.company);
  add("location", "Location", filters.location);
  add("posting_language", "Written in", languageName(filters.posting_language));
  add("requires", "Requires", languageName(filters.requires));
  add("signal", "Label", SIGNALS[filters.signal] || filters.signal);
  add("created_since", "Found", foundSince(filters.created_since, now));
  add(
    "dismissed_by",
    "Dismissed by",
    DISMISSED_BY[filters.dismissed_by] ||
      filters.dismissed_by.replace(/^agent:/, ""),
  );
  if (filters.hide_unspoken === "true")
    chips.push({
      key: "hide_unspoken",
      field: "Languages",
      value: "Only ones I speak",
    });
  return chips;
}

/** The date choices of the Found filter, as `created_since` dates. */
export function foundChoices(now = new Date()) {
  const day = (back: number) => {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    date.setDate(date.getDate() - back);
    return isoDay(date);
  };
  return [
    { value: day(0), label: "Today" },
    { value: day(6), label: "Last 7 days" },
    { value: day(29), label: "Last 30 days" },
  ];
}
function foundSince(value: string, now: Date) {
  const choice = foundChoices(now).find((item) => item.value === value);
  if (choice) return choice.label;
  const day = formatDay(value, now);
  return day === EMPTY ? value : `Since ${day}`;
}

/**
 * What the languages switch says: "would hide 3 of 40", or "hides 3 of 40"
 * while it is on, counting the list as it would be without hiding.
 */
export function unspokenLine(
  report: { count?: unknown; hidden?: unknown } | null | undefined,
  total: number,
) {
  if (!report || typeof report.count !== "number") return "";
  const all = report.hidden ? total + report.count : total;
  return `${report.hidden ? "hides" : "would hide"} ${report.count} of ${all}`;
}

/* ---------------------------------------------------------------- the list */

/** Rows under a day header: "Today", "Yesterday", "Earlier". */
export interface Group<Row> {
  label: string;
  rows: Row[];
}
const DAY_LABELS = ["Today", "Yesterday", "Earlier"];
function dayBucket(value: string | null | undefined, now: Date) {
  if (!value) return 2;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 2;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (date >= start) return 0;
  start.setDate(start.getDate() - 1);
  return date >= start ? 1 : 2;
}
/**
 * The rows of a list by day, when the list is in time order: by when a job
 * was found, or in Dismissed by when it was dismissed. In alphabetical order
 * there is one unnamed group.
 */
export function groupRows<Row extends JobSummary>(
  rows: Row[],
  view: Pick<View, "sort" | "section">,
  now = new Date(),
): Group<Row>[] {
  if (view.sort === "company" || view.sort === "title")
    return rows.length ? [{ label: "", rows }] : [];
  const groups: Group<Row>[] = [];
  for (const row of rows) {
    const when = view.sort === "dismissed" ? row.dismissal?.at : row.created_at;
    const label = DAY_LABELS[dayBucket(when, now)];
    const last = groups.at(-1);
    if (last?.label === label) last.rows.push(row);
    else groups.push({ label, rows: [row] });
  }
  return groups;
}

/**
 * The job to show once `id` leaves the list: the next row, or the previous
 * one at the end; "" when it was the only one.
 */
export function neighbour(ids: readonly string[], id: string) {
  const index = ids.indexOf(id);
  if (index < 0) return ids[0] ?? "";
  return ids[index + 1] ?? ids[index - 1] ?? "";
}

/** Whether a job moved to `triage` leaves the list of `section`. */
export function leaves(section: Section, triage: string) {
  if (section === "new") return triage !== "new";
  if (section === "dismissed") return triage !== "dismissed";
  return false;
}

/** When applications close, from what the source reported. */
export function deadlineOf(metadata: Record<string, unknown> | undefined) {
  for (const key of [
    "deadline",
    "application_deadline",
    "valid_through",
    "closes_at",
  ]) {
    const value = metadata?.[key];
    if (typeof value === "string" && !Number.isNaN(Date.parse(value)))
      return value;
  }
  return null;
}

/**
 * The one signal a row may carry, most telling first: no longer listed,
 * a possible duplicate, or incomplete text.
 */
export function rowSignal(job: Pick<JobSummary, "signals" | "complete">) {
  if (job.signals?.no_longer_listed) return "unlisted" as const;
  if (job.signals?.duplicate) return "duplicate" as const;
  if (job.complete === false) return "incomplete" as const;
  return null;
}
export const SIGNAL_TIPS = {
  unlisted: "No longer listed by its source",
  duplicate: "Possible duplicate",
  incomplete: "Posting text incomplete",
};

/** Whether a deadline is close enough to show in warning: within 7 days. */
export function closesSoon(deadline: string, now = new Date()) {
  const days = daysBetween(now, deadline);
  return days >= 0 && days < 7;
}

/** A passed deadline: the posting is closed. */
export const closed = (deadline: string, now = new Date()) =>
  daysBetween(now, deadline) < 0;

/* -------------------------------------------------------------- the detail */

/** Who made a change: "by you", "by <token name>", "by job sources". */
export function actorPhrase(label?: string | null) {
  if (!label) return "";
  if (label === "owner") return "by you";
  if (label === "system") return "by job sources";
  if (label.startsWith("agent:")) return `by ${label.slice(6) || "an agent"}`;
  return `by ${label}`;
}

/** The signals of a job as short tags, most telling first. */
export function signalTags(job: Pick<JobSummary, "signals" | "complete">) {
  const tags: string[] = [];
  const signals = job.signals;
  if (signals?.no_longer_listed) tags.push("No longer listed");
  if (signals?.duplicate) tags.push("Possible duplicate");
  for (const group of signals?.required ?? [])
    tags.push(`Requires ${either(group)}`);
  if (job.complete === false) tags.push("Text incomplete");
  return tags;
}

/** "Posting in German · Requires French or English". */
export function languageLine(job: Pick<JobSummary, "signals">) {
  const parts: string[] = [];
  if (job.signals?.language)
    parts.push(`Posting in ${languageName(job.signals.language)}`);
  for (const group of job.signals?.required ?? [])
    parts.push(`Requires ${either(group)}`);
  return parts.join(" · ");
}

const money = (value: unknown) =>
  typeof value === "number"
    ? value >= 1000
      ? `${Math.round(value / 1000)}k`
      : String(value)
    : "";
/** A salary as the source gave it: "CHF 115k–135k a year". */
export function salaryText(metadata: Record<string, unknown> | undefined) {
  const salary = metadata?.salary;
  if (typeof salary === "string") return salary.trim();
  if (!salary || typeof salary !== "object") return "";
  const value = salary as Record<string, unknown>;
  const low = money(value.min_amount),
    high = money(value.max_amount);
  const range = low && high && low !== high ? `${low}–${high}` : low || high;
  if (!range) return "";
  const interval =
    typeof value.interval === "string"
      ? ({ yearly: "a year", monthly: "a month", hourly: "an hour" } as const)[
          value.interval as "yearly"
        ] || value.interval
      : "";
  return [value.currency, range, interval].filter(Boolean).join(" ");
}

/** "Remote", "Hybrid", "On site", or nothing when the source did not say. */
export function workStyle(metadata: Record<string, unknown> | undefined) {
  const place = metadata?.workplace_type;
  if (typeof place === "string" && place)
    return capital(place.replaceAll("_", " ").toLowerCase());
  if (metadata?.is_remote === true) return "Remote";
  return "";
}

const JOB_TYPES: Record<string, string> = {
  fulltime: "Full time",
  parttime: "Part time",
  internship: "Internship",
  contract: "Contract",
  temporary: "Temporary",
};
/** A job type as words: "fulltime" is "Full time". */
export function jobTypeText(value?: string | null) {
  if (!value) return "";
  return (
    JOB_TYPES[value.toLowerCase().replace(/[\s_-]/g, "")] ||
    capital(value.replaceAll("_", " "))
  );
}

/** A block of posting text: a heading, a paragraph or a list. */
export type Block =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; items: string[] };

const BULLET = /^\s*(?:[-*•–·]|\d{1,2}[.)])\s+/;
const MARKDOWN_HEADING = /^#{1,4}\s+(.+?)\s*#*$/;
/** A short line on its own that reads as a heading ("Responsibilities:"). */
function headingText(line: string) {
  const text = line.trim();
  const heading = MARKDOWN_HEADING.exec(text);
  if (heading) return heading[1];
  const bold = /^\*\*(.+?)\*\*:?$/.exec(text);
  if (bold) return bold[1];
  if (text.length > 60 || BULLET.test(text)) return null;
  if (/[.,;!?)]$/.test(text)) return null;
  if (!/^[\p{Lu}\p{N}]/u.test(text)) return null;
  if (text.split(/\s+/).length > 8) return null;
  return text.replace(/:$/, "");
}

/**
 * The structure of a posting's plain text: blank lines separate blocks;
 * bullet lines become lists; a short line alone, or one that leads a block,
 * becomes a heading. Lines inside a paragraph keep their breaks.
 */
export function postingBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  const chunks = text
    .replace(/\r\n?/g, "\n")
    .split(/\n\s*\n/)
    .map((chunk) => chunk.split("\n").filter((line) => line.trim()))
    .filter((lines) => lines.length);
  for (const lines of chunks) {
    let rest = lines;
    const heading = headingText(rest[0]);
    if (heading != null && (rest.length > 1 || chunks.length > 1)) {
      blocks.push({ kind: "heading", text: heading });
      rest = rest.slice(1);
    }
    let paragraph: string[] = [];
    let list: string[] = [];
    const flush = () => {
      if (paragraph.length)
        blocks.push({ kind: "paragraph", text: paragraph.join("\n") });
      if (list.length) blocks.push({ kind: "list", items: list });
      paragraph = [];
      list = [];
    };
    for (const line of rest) {
      if (BULLET.test(line)) {
        if (paragraph.length) {
          blocks.push({ kind: "paragraph", text: paragraph.join("\n") });
          paragraph = [];
        }
        list.push(line.replace(BULLET, "").trim());
      } else {
        if (list.length) {
          blocks.push({ kind: "list", items: list });
          list = [];
        }
        const inner = headingText(line);
        if (inner != null && line.trim().length < 40 && rest.length > 1) {
          flush();
          blocks.push({ kind: "heading", text: inner });
        } else paragraph.push(line.trim());
      }
    }
    flush();
  }
  return blocks;
}

const MATCHED: Record<string, string> = {
  apply_target: "the same apply link",
  requisition_id: "the same requisition ID",
  posting_text: "identical posting text",
  near_identical_text: "nearly identical text",
  similar_text: "similar text",
  company_title: "the same company and role",
  company: "the same company",
  title: "the same role",
  similar_title: "a similar role",
  location: "the same place",
};
const CONFLICTS: Record<string, string> = {
  apply_target: "a different posting ID",
  requisition_id: "a different requisition ID",
  location: "a different place",
  seniority: "a different level",
  posting_text: "different text",
  posting_date: "posted months apart",
  ambiguous: "it matches another vacancy too",
};
/** Why two records look like one vacancy, in a sentence, without a score. */
export function reasonsLine(reasons: unknown) {
  const value = (reasons ?? {}) as { matched?: string[]; conflicts?: string[] };
  const matched = (value.matched ?? []).map(
    (key) => MATCHED[key] || key.replaceAll("_", " "),
  );
  const conflicts = (value.conflicts ?? []).map(
    (key) => CONFLICTS[key] || key.replaceAll("_", " "),
  );
  if (!matched.length && !conflicts.length) return "";
  const parts = [];
  if (matched.length) parts.push(`Both have ${matched.join(", ")}`);
  if (conflicts.length)
    parts.push(
      `${matched.length ? "but" : "They have"} ${conflicts.join(", ")}`,
    );
  return parts.join(", ") + ".";
}

const EVENTS: Record<string, string> = {
  job_added: "Found",
  job_refreshed: "Posting refreshed by its source",
  job_edited: "Details corrected",
  jobs_merged: "Merged with another record",
  duplicate_cleared: "Kept apart from a possible duplicate",
  application_created: "Application started",
  application_updated: "Application changed",
  application_deleted: "Application removed",
  note_deleted: "Note deleted",
  note_pinned: "Note pinned",
  note_unpinned: "Note unpinned",
};
/** What a recorded change is called in the history. */
export function eventTitle(event: {
  kind?: unknown;
  payload?: unknown;
}): string {
  const kind = String(event.kind ?? "");
  const payload = (event.payload ?? {}) as Record<string, unknown>;
  if (kind === "triage_changed") {
    if (payload.to === "dismissed") return "Dismissed";
    if (payload.to === "shortlisted") return "Shortlisted";
    return payload.from === "dismissed" ? "Restored" : "Back to New";
  }
  return EVENTS[kind] || capital(kind.replaceAll("_", " "));
}
