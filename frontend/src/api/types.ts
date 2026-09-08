/** Types mirroring the JSON the Openings API returns. */

export const JOB_STATUSES = [
  "new",
  "shortlisted",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

/** Every status the user moved a job into; `new` is the inbox. */
export const PIPELINE_STATUSES: JobStatus[] = JOB_STATUSES.filter((status) => status !== "new");

export const NOTE_KINDS = ["note", "qa"] as const;
export type NoteKind = (typeof NOTE_KINDS)[number];

export const ATTACHMENT_KINDS = ["cv", "cover_letter", "form_answers", "other"] as const;
export type AttachmentKind = (typeof ATTACHMENT_KINDS)[number];

export type EventKind = "ingested" | "status" | "label" | "note" | "attachment";

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

export interface JobSummary {
  job_id: string;
  title: string;
  company: string;
  location: string;
  source: string;
  job_url: string | null;
  job_type: string | null;
  is_remote: boolean | null;
  job_level: string | null;
  date_posted: string | null;
  min_amount: number | null;
  max_amount: number | null;
  currency: string | null;
  first_seen: string;
  last_seen: string;
  relevance_score: number;
  status: JobStatus;
  status_changed_at: string | null;
  labels: string[];
}

export interface ScoreExplanation {
  score: number;
  matched: { category: string; weight: number }[];
}

export interface Note {
  id: number;
  job_id: string;
  kind: NoteKind;
  title: string | null;
  body: string;
  created_at: string;
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

export interface JobEvent {
  id: number;
  job_id: string;
  kind: EventKind;
  summary: string;
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface JobDetail extends JobSummary {
  external_id: string | null;
  description: string | null;
  salary_interval: string | null;
  company_url: string | null;
  raw_json: string | null;
  explain: ScoreExplanation;
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
  status?: JobStatus[];
  source?: string[];
  label?: string[];
  company?: string;
  location?: string;
  locations?: string[];
  job_type?: string[];
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
  text?: string;
  sort?: JobSort;
}

export interface CommandResponse {
  success: boolean;
  affected_count: number;
  job_ids: string[];
  message: string | null;
}

export interface AddJobRequest {
  title: string;
  company: string;
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

export interface BlacklistEntry {
  job_id: string;
  title: string;
  company: string;
  location: string;
  blacklisted_at: string;
}

export interface BlacklistListResponse {
  items: BlacklistEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface BlacklistListParams {
  limit?: number;
  offset?: number;
  text?: string;
  company?: string;
  location?: string;
}

export interface SourceStatus {
  name: string;
  kind: string;
  detail: string;
  enabled: boolean;
  active_jobs: number;
}

export interface SourceRunStats {
  name: string;
  tasks: number;
  succeeded: number;
  failed: number;
  rows: number;
  errors: string[];
}

export interface RunRecord {
  id: number | null;
  started_at: string;
  finished_at: string | null;
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

export interface StatsResponse {
  total_jobs: number;
  by_status: Record<JobStatus, number>;
  new_today: number;
  seen_today: number;
  avg_relevance_score: number;
  blacklisted: number;
}

/** `[bin_start, count]` pairs. */
export type ScoreDistribution = number[][];

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
  purged_blacklist: number;
  protected: number;
  total_deleted: number;
}

export interface SemanticResult {
  job_id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  similarity: number;
  relevance_score: number | null;
  source: string | null;
  status: JobStatus | null;
  job_url: string | null;
}

export interface DashboardAuthResponse {
  token_required: boolean;
}

export type ExportFormat = "csv" | "json";
