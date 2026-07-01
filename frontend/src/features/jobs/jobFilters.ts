import type { JobListParams } from "../../api/types";

export type StatusFilter = "all" | "bookmarked" | "applied" | "open";

export interface JobFilterValues {
  company: string;
  datePostedFrom: string;
  datePostedTo: string;
  firstSeenFrom: string;
  firstSeenTo: string;
  jobType: string;
  lastSeenFrom: string;
  lastSeenTo: string;
  location: string;
  maxSalary: string;
  maxScore: string;
  minSalary: string;
  minScore: string;
  remoteOnly: boolean;
  site: string;
  sort: NonNullable<JobListParams["sort"]>;
  status: StatusFilter;
  text: string;
}

export const DEFAULT_JOB_FILTERS: JobFilterValues = {
  company: "",
  datePostedFrom: "",
  datePostedTo: "",
  firstSeenFrom: "",
  firstSeenTo: "",
  jobType: "",
  lastSeenFrom: "",
  lastSeenTo: "",
  location: "",
  maxSalary: "",
  maxScore: "",
  minSalary: "",
  minScore: "",
  remoteOnly: false,
  site: "",
  sort: "score",
  status: "all",
  text: "",
};

export function jobFilterKey(filters: JobFilterValues): string {
  return JSON.stringify(filters);
}

function numericFilter(value: string, min = 0, max?: number): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || (max !== undefined && parsed > max)) {
    return undefined;
  }
  return parsed;
}

export function buildJobListParams(
  filters: JobFilterValues,
  page: number,
  pageSize: number,
): JobListParams {
  return {
    applied: filters.status === "applied" ? true : filters.status === "open" ? false : undefined,
    bookmarked:
      filters.status === "bookmarked" ? true : filters.status === "open" ? false : undefined,
    company: filters.company || undefined,
    date_posted_from: filters.datePostedFrom || undefined,
    date_posted_to: filters.datePostedTo || undefined,
    first_seen_from: filters.firstSeenFrom || undefined,
    first_seen_to: filters.firstSeenTo || undefined,
    job_types: filters.jobType ? [filters.jobType] : undefined,
    last_seen_from: filters.lastSeenFrom || undefined,
    last_seen_to: filters.lastSeenTo || undefined,
    limit: pageSize,
    location: filters.location || undefined,
    max_salary: numericFilter(filters.maxSalary),
    max_score: numericFilter(filters.maxScore, 0, 100),
    min_salary: numericFilter(filters.minSalary),
    min_score: numericFilter(filters.minScore, 0, 100),
    offset: page * pageSize,
    remote: filters.remoteOnly ? true : undefined,
    sites: filters.site ? [filters.site] : undefined,
    sort: filters.sort,
    text: filters.text || undefined,
  };
}
