// What the Jobs screen shows about a job, in words: its tab, its signals, who
// dismissed it and where it came from. No React: tested directly.
import type { DismissedBy, Job, JobCounts } from "../../api";
import { dayTime } from "../../library/time.ts";

/** Changes to these REST resources read the jobs again (useFresh scopes). */
export const JOB_SCOPES = [
  "jobs",
  "applications",
  "notes",
  "files",
  "settings",
];

export type Section = "review" | "shortlist" | "dismissed" | "all";
export const SECTIONS: { id: Section; label: string }[] = [
  { id: "review", label: "To review" },
  { id: "shortlist", label: "Shortlist" },
  { id: "dismissed", label: "Dismissed" },
  { id: "all", label: "All" },
];
const QUEUES: Record<Section, string | null> = {
  review: "inbox",
  shortlist: "shortlist",
  dismissed: "dismissed",
  all: null,
};
export const sectionOf = (value: string): Section =>
  SECTIONS.some((item) => item.id === value) ? (value as Section) : "review";

/** The filters of the address; the shell maps the old Inbox's names to them. */
export const DEFAULTS = {
  section: "review",
  q: "",
  signal: "",
  complete: "",
  /** Empty: the tab's own order (most recently dismissed in Dismissed). */
  sort: "",
  dismissed_by: "",
  /** "true": leave out the jobs requiring a language the owner does not speak. */
  hide_unspoken: "",
  company: "",
  location: "",
  source: "",
  remote: "",
  job_type: "",
  created_since: "",
  created_until: "",
  /** The language the posting is written in, by code (`en`). */
  posting_language: "",
  posting_language_not: "",
  /** A language the posting requires. */
  requires: "",
  offset: "0",
  job: "",
};
export type Filters = typeof DEFAULTS;
/** Filters that narrow the list, as opposed to the tab, order, page and selection. */
export const NARROWING: (keyof Filters)[] = [
  "q",
  "signal",
  "complete",
  "dismissed_by",
  "company",
  "location",
  "source",
  "remote",
  "job_type",
  "created_since",
  "created_until",
  "posting_language",
  "posting_language_not",
  "requires",
];

export const SIGNAL_FILTERS: Record<string, string> = {
  likely_duplicate: "Possible duplicate",
  no_longer_listed: "No longer listed",
  language_required: "Requires a language",
  pending: "Signals pending",
};
export const SORTS: Record<string, string> = {
  newest: "Newest first",
  oldest: "Oldest first",
  company: "Company A to Z",
  title: "Role A to Z",
  dismissed: "Recently dismissed",
};
export const DISMISSED_BY: { id: "" | DismissedBy; label: string }[] = [
  { id: "", label: "All" },
  { id: "agent", label: "By an agent" },
  { id: "owner", label: "By you" },
  { id: "other", label: "Other" },
];

/** The order a tab lists its jobs in when none is chosen. */
export const sortOf = (filters: Filters) => {
  const section = sectionOf(filters.section);
  if (filters.sort && (filters.sort !== "dismissed" || section === "dismissed"))
    return filters.sort;
  return section === "dismissed" ? "dismissed" : "newest";
};

/** The list request of a tab and its filters. */
export function listQuery(filters: Filters, limit: number) {
  const query = new URLSearchParams();
  const section = sectionOf(filters.section);
  const queue = QUEUES[section];
  if (queue) query.set("queue", queue);
  for (const key of NARROWING) {
    const value = filters[key];
    if (!value || (key === "dismissed_by" && section !== "dismissed")) continue;
    query.set(key, value);
  }
  // Always named, so the list reports how many jobs the toggle hides.
  query.set(
    "hide_unspoken_required",
    filters.hide_unspoken === "true" ? "true" : "false",
  );
  query.set("sort", sortOf(filters));
  query.set("limit", String(limit));
  const offset = Number(filters.offset) || 0;
  if (offset) query.set("offset", String(offset));
  return query;
}

/** The count a tab shows. */
export function sectionCount(section: Section, counts?: JobCounts) {
  if (!counts) return undefined;
  return section === "review"
    ? counts.inbox
    : section === "shortlist"
      ? counts.shortlist
      : section === "dismissed"
        ? counts.dismissed
        : undefined;
}

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

export type Tone = "ready" | "attention" | "danger" | "info" | "agent";
export interface Label {
  text: string;
  tone?: Tone;
}

/**
 * The languages the owner speaks, from the settings (Preferences, Facts about
 * me), as a set of codes. Null when none is listed.
 */
export function ownLanguages(codes: string[] | null | undefined) {
  return codes?.length ? new Set(codes) : null;
}

/**
 * What the languages toggle says: "would hide 3 of 40", or "hides 3 of 40"
 * while it is on, counting the list as it would be without hiding.
 */
export function unspokenLine(
  report: { count: number; hidden: boolean } | undefined,
  total: number,
) {
  if (!report) return "";
  const all = report.hidden ? total + report.count : total;
  return `${report.hidden ? "hides" : "would hide"} ${report.count} of ${all}`;
}

/**
 * The signals of a job as short tags, most telling first. `full` adds what a
 * list row leaves out: a requirement or posting language the owner meets.
 * With the owner's languages, a requirement none of them meets needs attention.
 */
export function signalTags(
  job: Job,
  {
    full = false,
    own = null,
  }: { full?: boolean; own?: Set<string> | null } = {},
): Label[] {
  const signals = job.signals;
  const tags: Label[] = [];
  const met = (codes: string[]) => !!own && codes.some((code) => own.has(code));
  if (signals?.no_longer_listed)
    tags.push({ text: "No longer listed", tone: "danger" });
  if (signals?.duplicate)
    tags.push({
      text: "Possible duplicate",
      tone: "info",
    });
  for (const group of signals?.required || [])
    if (full || !met(group))
      tags.push({
        text: `Requires ${either(group)}`,
        tone: own && !met(group) ? "attention" : undefined,
      });
  if (signals?.language && (full || !met([signals.language])))
    tags.push({ text: `In ${languageName(signals.language)}` });
  if (job.complete === false)
    tags.push({ text: "Text incomplete", tone: "attention" });
  return tags;
}

/** Who dismissed a job, in words: "You", the token's name or "System". */
export function dismissedBy(job: Job) {
  const dismissal = job.dismissal;
  if (!dismissal) return "";
  if (dismissal.category === "owner") return "You";
  if (dismissal.by.kind === "token") return dismissal.by.name || "An API token";
  if (dismissal.by.kind === "system") return "System";
  return "Not recorded";
}

/** One line on a dismissal: who, when and why. */
export function dismissalLine(job: Job, now = new Date()) {
  const dismissal = job.dismissal;
  if (!dismissal) return "";
  const when = dismissal.at ? dayTime(dismissal.at, now) : "";
  return [`Dismissed by ${lowerYou(dismissedBy(job))}`, when]
    .filter(Boolean)
    .join(" · ");
}
const lowerYou = (text: string) => (text === "You" ? "you" : text);

const PROVIDERS: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  glassdoor: "Glassdoor",
  zip_recruiter: "ZipRecruiter",
  google: "Google Jobs",
  rss: "RSS",
  manual: "Added by hand",
};
/** Where a job came from, from its source: "LinkedIn", "Greenhouse board". */
export function sourceLabel(job: Pick<Job, "source" | "metadata">) {
  const source = String(
    job.source || job.metadata?.source || job.metadata?.ats || "manual",
  );
  if (PROVIDERS[source]) return PROVIDERS[source];
  if (job.metadata?.ats) return `${capital(String(job.metadata.ats))} board`;
  return capital(source.replaceAll("_", " "));
}
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** The caption of a row: where and when the job was found. */
export function foundLine(job: Job, now = new Date()) {
  return [sourceLabel(job), dayTime(job.created_at, now)]
    .filter(Boolean)
    .join(" · ");
}

/** The state of a job in the All tab: its application, else its queue. */
export function placeTag(job: Pick<Job, "application" | "triage">): Label {
  const stages: Record<string, string> = {
    draft: "Preparing",
    applied: "Applied",
    interview: "Interview",
    offer: "Offer",
    closed: "Closed",
  };
  if (job.application)
    return {
      text: stages[job.application.status] || job.application.status,
      tone: job.application.status === "closed" ? undefined : "info",
    };
  if (job.triage === "saved") return { text: "Shortlist" };
  if (job.triage === "dismissed") return { text: "Dismissed" };
  return { text: "To review" };
}

/** The tabs a triaged job leaves: To review and the Shortlist. */
export const QUEUE_SECTIONS: Section[] = ["review", "shortlist"];

/**
 * The job to show once `id` leaves the list: the next row, or the previous
 * one at the end; "" when it was the only one.
 */
export function neighbour(ids: string[], id: string) {
  const index = ids.indexOf(id);
  if (index < 0) return ids[0] || "";
  return ids[index + 1] || ids[index - 1] || "";
}
