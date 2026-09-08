/** Types mirroring the JSON the Openings API returns. */

export const JOB_STATUSES = [
  "new",
  "shortlisted",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
  "blacklisted",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

/** The statuses a job moves through once the user acted on it. */
export const PIPELINE_STATUSES: JobStatus[] = [
  "shortlisted",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
];

/** Statuses shown when no filter is given: everything except blacklisted. */
export const ACTIVE_STATUSES: JobStatus[] = JOB_STATUSES.filter((s) => s !== "blacklisted");

export const NOTE_KINDS = ["note", "qa"] as const;
export type NoteKind = (typeof NOTE_KINDS)[number];

export const ATTACHMENT_KINDS = ["cv", "cover_letter", "form_answers", "other"] as const;
export type AttachmentKind = (typeof ATTACHMENT_KINDS)[number];

export type EventKind =
  "ingested" | "posting" | "status" | "label" | "note" | "attachment" | "updated" | "merged";

export const JOB_SORTS = [
  "score",
  "date",
  "first_seen",
  "updated",
  "company",
  "title",
  "salary",
] as const;
export type JobSort = (typeof JOB_SORTS)[number];
export type SortDirection = "asc" | "desc";

export interface JobSummary {
  job_id: string;
  title: string;
  company: string;
  location: string;
  source: string;
  external_id: string | null;
  job_url: string | null;
  job_type: string | null;
  is_remote: boolean | null;
  job_level: string | null;
  date_posted: string | null;
  min_amount: number | null;
  max_amount: number | null;
  currency: string | null;
  salary_interval: string | null;
  company_url: string | null;
  first_seen: string;
  last_seen: string;
  relevance_score: number;
  status: JobStatus;
  status_changed_at: string | null;
  postings_count: number;
  notes_count: number;
  attachments_count: number;
  labels: string[];
}

export interface ScoreExplanation {
  score: number;
  matched: { category: string; weight: number }[];
}

export interface Posting {
  id: number;
  job_id: string;
  key: string;
  source: string;
  external_id: string | null;
  url: string | null;
  first_seen: string;
  last_seen: string;
}

export interface Note {
  id: number;
  job_id: string;
  kind: NoteKind;
  title: string | null;
  body: string;
  created_at: string;
  updated_at: string | null;
}

export interface Attachment {
  id: number;
  job_id: string;
  kind: AttachmentKind;
  filename: string;
  sha256: string;
  size_bytes: number;
  note: string | null;
  created_at: string;
}

export interface AttachmentEntry extends Attachment {
  job_title: string;
  company: string;
}

export interface JobEvent {
  id: number;
  job_id: string;
  kind: EventKind;
  summary: string;
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface JobDetail extends JobSummary {
  description: string | null;
  raw_json: string | null;
  explain: ScoreExplanation;
  postings: Posting[];
  notes: Note[];
  attachments: Attachment[];
  events: JobEvent[];
}

export interface JobListResponse {
  items: JobSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobListParams {
  limit?: number;
  offset?: number;
  statuses?: JobStatus[];
  sources?: string[];
  labels?: string[];
  company?: string;
  location?: string;
  locations?: string[];
  job_types?: string[];
  remote?: boolean;
  min_score?: number;
  max_score?: number;
  min_salary?: number;
  max_salary?: number;
  date_posted_from?: string;
  date_posted_to?: string;
  first_seen_from?: string;
  first_seen_to?: string;
  last_seen_from?: string;
  last_seen_to?: string;
  status_changed_from?: string;
  status_changed_to?: string;
  has_attachments?: boolean;
  without_labels?: boolean;
  text?: string;
  sort?: JobSort;
  direction?: SortDirection;
}

export interface CommandResponse {
  success: boolean;
  affected_count: number;
  job_ids: string[];
  message: string | null;
}

export interface PostingFields {
  title?: string;
  company?: string;
  location?: string;
  job_url?: string | null;
  description?: string | null;
  date_posted?: string | null;
  job_type?: string | null;
  is_remote?: boolean | null;
  job_level?: string | null;
  min_amount?: number | null;
  max_amount?: number | null;
  currency?: string | null;
  salary_interval?: string | null;
  company_url?: string | null;
}

export interface AddJobRequest extends PostingFields {
  title: string;
  company: string;
  source?: string | null;
  external_id?: string | null;
  status?: JobStatus;
  labels?: string[];
  note?: string | null;
}

export interface NoteRequest {
  kind: NoteKind;
  title?: string | null;
  body: string;
}

export interface SourceRunStats {
  name: string;
  tasks: number;
  succeeded: number;
  failed: number;
  rows: number;
  errors: string[];
  started_at?: string;
}

export interface SourceStatus {
  name: string;
  kind: string;
  detail: string;
  enabled: boolean;
  active_jobs: number;
  last_run: SourceRunStats | null;
}

export interface RunRecord {
  id: number | null;
  started_at: string;
  finished_at: string | null;
  running: boolean;
  duration_seconds: number;
  total_found: number;
  unique_found: number;
  saved: number;
  new_jobs: number;
  notified: number;
  success: boolean;
  sources: SourceRunStats[];
  errors: string[];
}

export interface RunStatus {
  running: boolean;
  run: RunRecord | null;
  requested: boolean;
}

export interface StatsResponse {
  total_jobs: number;
  by_status: Record<JobStatus, number>;
  new_today: number;
  seen_today: number;
  avg_relevance_score: number;
  blacklisted: number;
  attachments: number;
  notes: number;
}

/** `[bin_start, count]` pairs. */
export type ScoreDistribution = [number, number][];

export interface Facet {
  value: string;
  count: number;
}

export interface FacetsResponse {
  statuses: Facet[];
  sources: Facet[];
  companies: Facet[];
  locations: Facet[];
  job_types: Facet[];
  labels: Facet[];
}

export interface CleanupReport {
  deleted_below_score: number;
  deleted_stale: number;
  protected: number;
  total_deleted: number;
}

export interface SemanticResult extends JobSummary {
  similarity: number;
}

export interface DashboardAuthResponse {
  token_required: boolean;
}

export interface SettingsSummary {
  version: string;
  profile: { name: string; headline: string; target: string };
  scoring: {
    save_threshold: number;
    notify_threshold: number;
    weights: Record<string, number>;
    keywords: Record<string, string[]>;
  };
  scheduler: { interval_hours: number; run_on_startup: boolean };
  sources: {
    jobspy: {
      enabled: boolean;
      sites: string[];
      locations: string[];
      queries: string[];
      job_types: string[];
      hours_old: number;
    };
    companies: { name: string; ats: string; slug: string; locations: string[] }[];
    feeds: { name: string; url: string }[];
    adzuna: { enabled: boolean };
  };
  notifications: { telegram: boolean };
  retention: { max_age_days: number };
  attachments: { max_size_mb: number };
  embeddings: { enabled: boolean; status: string };
  timezone: string;
  data_dir: string;
}

export type ExportFormat = "csv" | "json";
