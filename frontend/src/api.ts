export type Json = Record<string, unknown>;
export interface ListResult<T> {
  items: T[];
  total: number;
  stage_counts?: Record<string, number>;
  ready_count?: number;
  facets?: Record<string, string[]>;
  /** On the application list: the no-reply period and how many wait past it. */
  no_reply?: NoReply;
}
/** The period after which a sent application has had no reply, from the settings. */
export interface NoReply {
  days: number;
  source: "settings" | "default";
  /** Applied applications sent longer ago than `days`. */
  due?: number;
}
export type ResponseKind = "rejection" | "interview" | "offer" | "other";
/** An employer's answer to a sent application. */
export interface EmployerResponse {
  id: string;
  application_id: string;
  job_id?: string;
  kind: ResponseKind;
  /** The day it arrived, YYYY-MM-DD. */
  date: string;
  note: string;
  version: number;
  created_by: Actor;
  updated_by: Actor;
  created_at: string;
  updated_at: string;
}
export interface Versioned {
  id: string;
  version: number;
  created_at?: string;
  updated_at?: string;
}
export type Triage = "inbox" | "saved" | "dismissed";
export type Stage = "draft" | "applied" | "interview" | "offer" | "closed";
export interface ApplicationSummary extends Versioned {
  status: Stage;
  outcome: string | null;
}
/** What collection found out about a job, without a model. */
export interface JobSignals {
  /** False until the signals of a job collected before 0.21 are computed. */
  computed: boolean;
  language: string | null;
  language_confidence: number | null;
  /** Groups of language codes; one language of a group is enough. */
  required: string[][];
  welcome: string[];
  duplicate_checked: boolean;
  duplicate: {
    job_id: string;
    confidence: number;
    tier: "high" | "medium" | "low";
  } | null;
  no_longer_listed: boolean;
  unlisted_at: string | null;
}
/** Who dismissed a job, by kind; "system" also covers an unknown actor. */
export type DismissedBy = "agent" | "owner" | "system";
export interface Dismissal {
  at: string | null;
  by: Actor;
  category: DismissedBy;
  reason: string;
}
/** One sighting of a posting by a source. */
export interface Observation {
  id: string;
  source_id: string | null;
  source_name: string | null;
  source_kind: string | null;
  identity: string;
  url: string;
  first_seen_at: string;
  last_seen_at: string;
  unlisted_at: string | null;
}
export interface JobCounts {
  all: number;
  inbox: number;
  shortlist: number;
  applications: number;
  dismissed: number;
  dismissed_by: Record<DismissedBy, number>;
}
export interface Job extends Versioned {
  title: string;
  company: string;
  location: string;
  url: string;
  posting: string;
  posting_preview?: string;
  complete?: boolean;
  is_remote?: boolean | null;
  date_posted?: string;
  job_type?: string;
  postings?: Observation[];
  triage: Triage;
  metadata: Json;
  salary?: string | Json | number;
  source?: string;
  notes?: Note[];
  application: ApplicationSummary | null;
  application_count: number;
  signals: JobSignals;
  dismissal: Dismissal | null;
}
export interface JobList extends ListResult<Job> {
  counts?: JobCounts;
  /** With `hide_unspoken_required`: the jobs of these filters that require a language the owner does not speak. */
  unspoken_required?: {
    spoken_languages: string[];
    count: number;
    /** Whether they are left out of this list. */
    hidden: boolean;
  };
}
export interface YieldCounts {
  collected: number;
  to_review: number;
  shortlisted: number;
  applied: number;
  responded: number;
  interviews: number;
  offers: number;
  dismissed: number;
  likely_duplicates: number;
  no_longer_listed: number;
}
export interface YieldRow extends YieldCounts {
  source_id: string | null;
  name: string;
  kind: "search" | "company" | "feed" | "manual";
  kind_label: string;
  source_kind: string | null;
  enabled: boolean | null;
  last_run_at: string | null;
  last_error: string | null;
  providers: (YieldCounts & { provider: string; label: string })[];
  dismissed_by: Record<DismissedBy, number>;
  kept_rate: number | null;
  withheld: string | null;
}
export interface SourceYield {
  period: { since: string | null; until: string | null };
  min_sample: number;
  items: YieldRow[];
  total: YieldCounts &
    Pick<YieldRow, "name" | "dismissed_by" | "kept_rate" | "withheld"> & {
      sources: number;
    };
}
export interface DuplicateJob extends Versioned {
  title: string;
  company: string;
  location: string;
  url: string;
  source?: string;
  triage: Triage;
  complete?: boolean;
  application: ApplicationSummary | null;
  application_count: number;
  applications: ApplicationSummary[];
  posting_hash: string | null;
  similarity: number | null;
  /** Against the group's reference record; null on the reference itself. */
  confidence: number | null;
  reasons: DuplicateReasons | null;
}
export interface DuplicateReasons {
  matched: string[];
  conflicts: string[];
}
export interface DuplicateGroup {
  job_ids: string[];
  signals: string[];
  confidence: number;
  tier: "high" | "medium" | "low";
  reasons: DuplicateReasons;
  size: number;
  identical_postings: boolean;
  reference_id: string;
  open_application_ids: string[];
  merge_blocked: boolean;
  items: DuplicateJob[];
}
export interface BulkResult {
  total: number;
  succeeded: number;
  failed: number;
  items: {
    id: string;
    ok: boolean;
    error?: { code: string; message: string; status: number };
  }[];
}
export interface Note {
  id: string;
  body: string;
  text?: string;
  created_at: string;
  updated_at?: string;
  version?: number;
  job_id?: string;
  application_id?: string | null;
  scope?: "job" | "application";
  author?: Actor;
  /** At most one pinned note per job and per application; listed first. */
  pinned?: boolean;
  pinned_at?: string | null;
}
export type TimelineKind = "note" | "event" | "response";
/** One entry of a job's or an application's timeline: a note or a recorded change. */
export interface TimelineItem {
  type: "note" | "event";
  kind: TimelineKind;
  id: string;
  created_at: string;
  scope: { type: "job" | "application"; id: string };
  job_id: string;
  application_id: string | null;
  actor: Actor;
  batch_id: string | null;
  note: {
    body: string;
    version: number;
    updated_at: string;
    pinned: boolean;
    pinned_at: string | null;
  } | null;
  event: {
    kind: string;
    payload: Json;
    subject: { type: string | null; id: string | null };
  } | null;
}
export interface TimelinePage {
  scope: { type: "job" | "application"; id: string; job_id: string };
  items: TimelineItem[];
  total: number;
  /** Entries of each kind for the other filters. */
  counts: Record<TimelineKind, number>;
  limit: number;
  offset: number;
}
export interface Question {
  id: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: string[];
  max_length?: number;
}
export const requirementKinds = {
  authorship: "Authorship",
  attachment: "Attachment",
  reference: "Reference",
  format: "Format",
  language: "Language",
  eligibility: "Eligibility",
  deadline: "Deadline",
  other: "Other",
} as const;
export type RequirementKind = keyof typeof requirementKinds;
export interface Requirement {
  id?: string;
  kind: RequirementKind;
  text: string;
  blocking: boolean;
  resolved: boolean;
  note: string;
}
export type Readiness =
  "blocked" | "none" | "missing_pdf" | "unreviewed" | "reviewed" | "ready";
export const readinessLabels: Record<Readiness, string> = {
  blocked: "Blocked by a requirement",
  none: "No documents",
  missing_pdf: "Missing PDF",
  unreviewed: "Needs review",
  reviewed: "Reviewed, not marked ready",
  ready: "Ready to apply",
};
export interface Application extends Versioned {
  job_id: string;
  status: Stage;
  outcome: string | null;
  /** The application's pinned note: its standing guidance. */
  pinned_note?: Note | null;
  questions: Question[];
  answers: Record<string, unknown>;
  job?: Job;
  applied_at?: string | null;
  priority?: number | null;
  deadline?: string | null;
  requirements?: Requirement[];
  readiness?: Readiness;
  ready_at?: string | null;
  ready_by?: Actor;
  open_requirements?: number;
  blocking_requirements?: number;
  documents_count?: number;
  preparation?: {
    kind: string;
    revisions: number;
    pdf: number;
    approved: number;
  }[];
  stale_inputs?: StaleInput[];
  /** The first changes since the current revisions were written. */
  stale_changes?: StaleChange[];
  stale_changes_total?: number;
  /** The day an application closed as no_response was concluded. */
  concluded_on?: string | null;
  responses?: EmployerResponse[];
  last_response?: {
    id: string;
    kind: ResponseKind;
    date: string;
    count: number;
  } | null;
}
export type StaleInput =
  "profile" | "preferences" | "template" | "knowledge" | "claim";
export interface StaleChange {
  input: StaleInput;
  /** A Profile part (null: the whole Profile), `<section>:<hash>` of a statement, or a record. */
  id: string | null;
  label: string;
  state:
    | "changed"
    | "deleted"
    | "unapproved"
    | "added"
    | "removed"
    | "unconfirmed"
    | "confirmed";
  frozen_version: number | null;
  current_version: number | null;
  /** A statement's Preferences section. */
  section?: PreferenceSectionName;
}
export interface Staleness {
  application_id: string;
  stale: boolean;
  inputs: StaleInput[];
  changes: StaleChange[];
  documents: {
    document_id: string;
    kind: string;
    title: string;
    context_id: string | null;
    context_created_at: string | null;
    status: "current" | "stale" | "no_context";
    /** How the frozen copy was compared; null without one. */
    comparison: {
      profile: "parts" | "whole";
      preferences: "items" | "not_frozen";
    } | null;
    changes: StaleChange[];
  }[];
}
/** Two revisions' text compared line by line (`/documents/{id}/comparison`). */
export interface Comparison {
  document_id: string;
  other_id: string;
  /** Whether each side has text: a CV or letter without a source has none. */
  text: { document: boolean; other: boolean };
  added: number;
  removed: number;
  lines: { change: "same" | "added" | "removed"; text: string }[];
}
export interface Profile {
  name: string;
  headline: string;
  location: string;
  email: string;
  phone: string;
  summary: string;
  links: unknown[];
  metadata: Json;
  version: number;
}
export interface CareerDates {
  kind: "single" | "period";
  start: string;
  end: string | null;
  current: boolean;
}
export interface Knowledge extends Versioned {
  kind: KnowledgeKind;
  title: string;
  narrative: string;
  narrative_preview?: string;
  claim_preview?: string;
  organization: string;
  dates: CareerDates | null;
  skills: string[];
  position: number;
  claim_count?: number;
  file_count?: number;
  metadata: Json;
}
export const knowledgeKinds = {
  experience: "Experience",
  project: "Projects",
  course: "Courses",
  education: "Education",
  award: "Awards",
  publication: "Publications",
  fact: "Facts",
  skill: "Skills",
  language: "Languages",
  other: "Other",
} as const;
export type KnowledgeKind = keyof typeof knowledgeKinds;
export interface Claim extends Versioned {
  knowledge_id: string;
  text: string;
  text_preview?: string;
  knowledge_title?: string;
  knowledge_organization?: string;
  position: number;
  approved: boolean;
  /** In the CV unless the job gives a reason to leave it out. */
  default_in_cv: boolean;
  role: ClaimRole;
  group: string;
  metadata: Json;
}
export const claimRoles = {
  core: "Core",
  supporting: "Supporting",
  bench: "Bench",
} as const;
export type ClaimRole = keyof typeof claimRoles;
/** Typed limits and any other free-form key (engine, date_format). */
export interface TemplateRules extends Json {
  max_pages?: number;
  max_bullets?: number;
  max_bullet_chars?: number;
}
export interface Template extends Versioned {
  name: string;
  kind: "resume" | "cover_letter";
  tex: string;
  guidance: string;
  rules: TemplateRules;
  is_default: boolean;
  file_count?: number;
  updated_at?: string;
}
export const preferenceSections = {
  looking_for: "What I'm looking for",
  ruled_out: "What I rule out",
  facts: "Facts about me",
  writing: "Writing rules",
  working_with_me: "Working with me",
} as const;
export type PreferenceSectionName = keyof typeof preferenceSections;
export type WritingScope = "all" | "cv" | "letter";
/** One statement in the owner's words; only a writing rule has a scope. */
export interface PreferenceItem {
  text: string;
  scope?: WritingScope;
}
export interface PreferenceSection {
  section: PreferenceSectionName;
  title: string;
  description: string;
  items: PreferenceItem[];
  version: number;
  updated_at: string | null;
  /** "owner", "agent:<name>" or "system". */
  updated_by: string | null;
}
/** The two typed settings: the no-reply period and the languages spoken. */
export interface WorkspaceSettings {
  no_reply_days: number;
  /** ISO 639-1 codes. */
  spoken_languages: string[];
  version: number;
  updated_at: string | null;
}
export interface Preferences {
  sections: PreferenceSection[];
  settings: WorkspaceSettings;
}
export interface Document extends Versioned {
  application_id: string;
  context_id: string | null;
  kind: string;
  title: string;
  /** Structured content of form answers and other kinds; a CV or letter has none. */
  content?: Json;
  /** Text derived from the revision's .tex source; null without one. */
  text?: string | null;
  /** Content a CV or letter stored before 0.22, read-only. */
  legacy_content?: Json | null;
  /** The SHA-256 of the revision's source, which its PDF names. */
  source_sha256?: string | null;
  note?: string;
  claim_ids?: string[];
  knowledge_ids?: string[];
  previous_id?: string;
  review_state: string;
  revision_number?: number;
  files?: WorkspaceFile[];
  file_count?: number;
}
export interface WorkspaceFile {
  id: string;
  name: string;
  size: number;
  media_type: string;
  sha256?: string;
  /** For a revision's PDF: the SHA-256 of the source it was built from. */
  source_sha256?: string | null;
  created_at?: string;
  download_url?: string;
  url?: string;
  /** Always 1: a file never changes. A delete names it. */
  version?: number;
}
export interface Source extends Versioned {
  name: string;
  kind: string;
  config: Json;
  url?: string;
  enabled: boolean;
  automatic_collection: boolean;
  filters: Json;
  schedule: Json;
  next_run_at?: string;
  last_run_at?: string;
  last_error?: string;
  last_result?: Json;
  last_outcome?: string;
  last_counts?: Json;
  last_task_id?: string;
  last_run?: CollectionRun;
  last_diagnostics?: { warnings?: string[] }[];
}
export interface BackgroundTask {
  id: string;
  kind: "collect";
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  run_id?: string;
  source_id?: string;
  source_name?: string;
  job_id?: string;
  job_title?: string;
  payload?: Json;
  result?: Json;
  attempts?: number;
  next_run_at?: string;
  created_at: string;
  updated_at?: string;
  error?: string;
}
export interface CollectionRun {
  id: string;
  source_id: string;
  source_name: string;
  source_version: number;
  source_snapshot?: Json;
  overrides?: Json;
  state: string;
  counts: Record<string, number>;
  processing_seconds?: number;
  waiting_seconds?: number;
  total_seconds?: number;
  planned_at?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  next_run_at?: string;
  task_ids: string[];
  tasks?: BackgroundTask[];
}
export type TokenKind = "owner" | "agent";
export const tokenKinds: Record<TokenKind, string> = {
  agent: "Agent",
  owner: "Owner",
};
/**
 * Who made a change: "owner" (the dashboard or an owner token),
 * "agent:<token name>", "system" (collection, the worker, an upgrade), or
 * null when it was written before attribution was recorded.
 */
export type Actor = string | null;
/** One recorded change (`/events`, the overview's latest changes). */
export interface Activity {
  id?: string;
  kind?: string;
  created_at: string;
  payload?: Json;
  application_id?: string | null;
  job_id?: string | null;
  actor?: Actor;
  /** One id per REST request or MCP tool call that wrote it. */
  batch_id?: string | null;
  subject?: { type: string | null; id: string | null; label?: string };
}
/** Counts and rates of one group of sent applications (insights). */
export interface InsightMetrics {
  sent: number;
  responded: number;
  interviews: number;
  offers: number;
  rejections: number;
  no_reply: number;
  waiting: number;
  response_rate: number | null;
  interview_rate: number | null;
  offer_rate: number | null;
  withheld: "too_few_sent" | null;
  median_days_to_response: number | null;
  median_withheld: "too_few_dated_answers" | null;
  timed: number;
  undated: number;
}
export interface InsightGroup extends InsightMetrics {
  key: string;
  label: string;
}
export type InsightDimension =
  "role_family" | "seniority" | "location" | "source_kind" | "source" | "month";
export interface Insights {
  min_sample: number;
  period: { applied_since: string | null; applied_until: string | null };
  overall: InsightMetrics;
  time_to_response: {
    key: string;
    label: string;
    count: number;
    share: number | null;
  }[];
  groups: Record<InsightDimension, InsightGroup[]>;
  excluded: { preparing: number; closed_unsent: number };
  no_reply: NoReply;
}
export interface FunnelStep {
  stage: string;
  count: number;
  outcomes: Record<string, number>;
}
export interface Overview {
  sent: number;
  interviews: number;
  offers: number;
  active: number;
  drafts: number;
  ready?: number;
  inbox: number;
  incomplete: number;
  funnel: FunnelStep[];
  activity: Activity[];
  [key: string]: unknown;
}
export interface Session {
  configured: boolean;
  authenticated: boolean;
  csrf_token?: string;
}
let csrfToken = "";
export function setCsrf(value: string) {
  csrfToken = value;
}
export class ApiError extends Error {
  status: number;
  code: string;
  path: string;
  /** Structured details of the error, such as the current version. */
  details: Json;
  constructor(
    message: string,
    status: number,
    code = "request_failed",
    path = "",
    details: Json = {},
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.path = path;
    this.details = details;
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(
    path.startsWith("/api/") ? path : "/api/v1" + path,
    {
      method,
      credentials: "same-origin",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    },
  );
  let value;
  try {
    value = response.status === 204 ? {} : await response.json();
  } catch (error) {
    if (
      signal?.aborted ||
      (error instanceof DOMException && error.name === "AbortError")
    )
      throw error;
    throw new ApiError(
      "The server returned an unreadable response. Refresh this view to try again.",
      response.status,
      "invalid_response",
      path,
    );
  }
  if (
    response.status === 401 &&
    path !== "/auth/session" &&
    path !== "/auth/login"
  )
    window.dispatchEvent(new Event("openings:unauthorized"));
  if (!response.ok) {
    const error = value.error;
    const fields = Array.isArray(error?.details)
      ? error.details
          .slice(0, 3)
          .map((detail: { field?: unknown[]; message?: string }) => {
            const field = detail.field
              ?.filter((part) => part !== "body" && part !== "query")
              .join(".");
            return `${field ? field + ": " : ""}${detail.message || "Invalid value."}`;
          })
          .join(" ")
      : "";
    throw new ApiError(
      (typeof error === "string"
        ? error
        : error?.message ||
          value.detail ||
          `Request failed (${response.status})`) + (fields ? " " + fields : ""),
      response.status,
      error?.code,
      path,
      error?.details && !Array.isArray(error.details) ? error.details : {},
    );
  }
  if (
    !["GET", "HEAD"].includes(method) &&
    !/\/(preview|test|download|uploads|auth)(\/|$)/.test(path)
  ) {
    setTimeout(
      () =>
        window.dispatchEvent(
          new CustomEvent("openings:changed", { detail: path }),
        ),
      0,
    );
  }
  return value as T;
}
export function list<T>(path: string, signal?: AbortSignal) {
  return api<ListResult<T>>(path, "GET", undefined, signal);
}
export function version<T extends { version: number }>(
  record: T,
  fields: unknown,
) {
  return { ...(fields as object), expected_version: record.version };
}
export function text(value: unknown): string {
  return value == null ? "" : String(value);
}
export function date(value?: string) {
  if (!value) return "Not yet";
  const d = new Date(value);
  return Number.isNaN(d.valueOf())
    ? value
    : d.toLocaleDateString("en", { month: "short", day: "numeric" });
}
/** Format a calendar date (YYYY-MM-DD) without shifting it across time zones. */
export function calendarDate(value?: string | null) {
  if (!value) return "";
  const d = new Date(value + "T00:00:00Z");
  if (Number.isNaN(d.valueOf())) return value;
  return d.toLocaleDateString("en", {
    month: "short",
    day: "numeric",
    year:
      d.getUTCFullYear() === new Date().getFullYear() ? undefined : "numeric",
    timeZone: "UTC",
  });
}
export function localToday(d = new Date()) {
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}
export async function sha256(file: File) {
  if (!globalThis.crypto?.subtle) return undefined;
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
    ),
  )
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");
}
/** The media type an upload declares: a .tex source is TeX whatever the browser says. */
export function mediaTypeOf(file: File) {
  if (/\.(tex|ltx)$/i.test(file.name)) return "application/x-tex";
  if (/\.pdf$/i.test(file.name)) return "application/pdf";
  return file.type || "application/octet-stream";
}
/**
 * Upload one file to its owner. A revision's PDF names the SHA-256 of the
 * source it was built from (`sourceSha256`).
 */
export async function uploadFile(
  file: File,
  ownerType: string,
  ownerId: string,
  sourceSha256?: string | null,
): Promise<WorkspaceFile> {
  const ticket = await api<{
    url: string;
    headers?: Record<string, string>;
    method?: string;
  }>("/files/uploads", "POST", {
    owner_type: ownerType,
    owner_id: ownerId,
    name: file.name,
    size: file.size,
    sha256: await sha256(file),
    media_type: mediaTypeOf(file),
    ...(sourceSha256 ? { source_sha256: sourceSha256 } : {}),
  });
  const response = await fetch(ticket.url, {
    method: ticket.method || "PUT",
    headers: ticket.headers,
    body: file,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.error?.message || "The file could not be uploaded.",
      response.status,
      body?.error?.code,
    );
  }
  window.dispatchEvent(
    new CustomEvent("openings:changed", { detail: "/files" }),
  );
  return response.json() as Promise<WorkspaceFile>;
}
export async function fileUrl(file: WorkspaceFile) {
  if (file.url) return file.url;
  if (file.download_url) return file.download_url;
  const result = await api<{ url: string }>(
    `/files/${file.id}/download`,
    "POST",
  );
  return result.url;
}
export function download(
  name: string,
  content: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function binary(
  path: string,
  method: string,
  body?: Blob,
  headers: Record<string, string> = {},
) {
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers,
    body,
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new ApiError(
      result.error?.message || result.detail || "The file operation failed.",
      response.status,
    );
  }
  return response;
}
export function newId() {
  return (
    globalThis.crypto?.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  );
}
export async function copyText(value: string) {
  if (navigator.clipboard?.writeText)
    return navigator.clipboard.writeText(value);
  const input = document.createElement("textarea");
  input.value = value;
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.append(input);
  input.select();
  const copied = document.execCommand("copy");
  input.remove();
  if (!copied) throw new Error("Select and copy the displayed text manually.");
}

export function formatTime(value?: string) {
  if (!value) return "Not scheduled";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : parsed.toLocaleString("en", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

export async function downloadWorkspaceFile(file: WorkspaceFile) {
  const url = new URL(await fileUrl(file), location.origin);
  url.searchParams.set("inline", "false");
  const link = document.createElement("a");
  link.href = url.toString();
  link.download = file.name.split("/").pop() || file.name;
  document.body.append(link);
  link.click();
  link.remove();
}

export function careerEntryLabel(
  entry: Pick<Knowledge, "title" | "organization">,
) {
  return [entry.title, entry.organization].filter(Boolean).join(" · ");
}
export function careerDates(dates: CareerDates | null | undefined) {
  if (!dates) return "";
  const monthNames = [
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
  const format = (value: string) => {
    const [year, month] = value.split("-");
    return month ? `${monthNames[Number(month) - 1]} ${year}` : year;
  };
  if (dates.kind === "single") return format(dates.start);
  return `${format(dates.start)} – ${dates.current ? "Present" : dates.end ? format(dates.end) : ""}`;
}
