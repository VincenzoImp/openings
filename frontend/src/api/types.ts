export interface JobRecord {
  job_id: string;
  title: string;
  company: string;
  location: string;
  job_url: string | null;
  site: string | null;
  job_type: string | null;
  is_remote: boolean | null;
  job_level: string | null;
  description: string | null;
  date_posted: string | null;
  min_amount: number | null;
  max_amount: number | null;
  currency: string | null;
  company_url: string | null;
  first_seen: string | null;
  last_seen: string | null;
  relevance_score: number;
  applied: boolean;
  bookmarked: boolean;
}

export interface JobListResponse {
  items: JobRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardAuthResponse {
  token_required: boolean;
}

export interface JobListParams {
  limit?: number;
  offset?: number;
  min_score?: number;
  max_score?: number;
  site?: string;
  sites?: string[];
  company?: string;
  location?: string;
  locations?: string[];
  bookmarked?: boolean;
  applied?: boolean;
  remote?: boolean;
  job_type?: string;
  job_types?: string[];
  min_salary?: number;
  max_salary?: number;
  date_posted_from?: string;
  date_posted_to?: string;
  first_seen_from?: string;
  first_seen_to?: string;
  last_seen_from?: string;
  last_seen_to?: string;
  text?: string;
  sort?: "score" | "date" | "company" | "title" | "salary";
}

export interface CommandResponse {
  success: boolean;
  affected_count: number;
  job_ids: string[];
  bookmarked: boolean | null;
  applied: boolean | null;
  message: string | null;
}

export interface FacetItem {
  value: string | boolean;
  count: number;
}

export interface FacetsResponse {
  sites: FacetItem[];
  companies: FacetItem[];
  locations: FacetItem[];
  job_types: FacetItem[];
  remote: FacetItem[];
}

export interface BlacklistedJobRecord {
  job_id: string;
  title: string;
  company: string;
  location: string;
  blacklisted_at: string;
}

export interface BlacklistListParams {
  limit?: number;
  offset?: number;
  text?: string;
  company?: string;
  location?: string;
}

export interface BlacklistListResponse {
  items: BlacklistedJobRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface StatsResponse {
  total_jobs: number;
  seen_today: number;
  new_today: number;
  applied: number;
  blacklisted: number;
  avg_relevance_score: number;
}

export interface CleanupResponse {
  deleted_below_score: number;
  deleted_stale: number;
  purged_blacklist: number;
  protected_bookmarked: number;
  protected_applied: number;
  total_deleted: number;
}

export type ScoreDistribution = [number, number][];

export type ExportFormat = "csv" | "json";
