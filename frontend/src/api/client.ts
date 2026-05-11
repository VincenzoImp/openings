import type {
  CleanupResponse,
  CommandResponse,
  JobListParams,
  JobListResponse,
  JobRecord,
  ScoreDistribution,
  StatsResponse
} from "./types";

const API_ROOT = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    ...init
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function query(params: JobListParams): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export function listJobs(params: JobListParams = {}): Promise<JobListResponse> {
  return request<JobListResponse>(`/jobs${query(params)}`);
}

export function getJob(jobId: string): Promise<JobRecord> {
  return request<JobRecord>(`/jobs/${encodeURIComponent(jobId)}`);
}

export function setBookmarked(
  jobId: string,
  bookmarked: boolean
): Promise<CommandResponse> {
  return request<CommandResponse>(`/jobs/${encodeURIComponent(jobId)}/bookmark`, {
    method: "PUT",
    body: JSON.stringify({ bookmarked })
  });
}

export function setApplied(
  jobId: string,
  applied: boolean
): Promise<CommandResponse> {
  return request<CommandResponse>(`/jobs/${encodeURIComponent(jobId)}/applied`, {
    method: "PUT",
    body: JSON.stringify({ applied })
  });
}

export function blacklistJobs(jobIds: string[]): Promise<CommandResponse> {
  return request<CommandResponse>("/jobs/blacklist", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds })
  });
}

export function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>("/stats");
}

export function getDistribution(): Promise<ScoreDistribution> {
  return request<ScoreDistribution>("/distribution");
}

export function previewCleanup(): Promise<CleanupResponse> {
  return request<CleanupResponse>("/cleanup/preview");
}

export function runCleanup(): Promise<CleanupResponse> {
  return request<CleanupResponse>("/cleanup/run", { method: "POST" });
}
