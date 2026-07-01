import type {
  BlacklistListParams,
  BlacklistListResponse,
  CleanupResponse,
  CommandResponse,
  DashboardAuthResponse,
  ExportFormat,
  FacetsResponse,
  JobListParams,
  JobListResponse,
  JobRecord,
  SemanticJobResult,
  ScoreDistribution,
  StatsResponse,
} from "./types";

const API_ROOT = "/api";
const DASHBOARD_TOKEN_STORAGE_KEY = "job-search-tool.dashboard-token";

function storage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function getDashboardToken(): string | null {
  const token = storage()?.getItem(DASHBOARD_TOKEN_STORAGE_KEY)?.trim();
  return token || null;
}

export function setDashboardToken(token: string | null): void {
  const store = storage();
  if (!store) {
    return;
  }

  const normalized = token?.trim() ?? "";
  if (normalized) {
    store.setItem(DASHBOARD_TOKEN_STORAGE_KEY, normalized);
  } else {
    store.removeItem(DASHBOARD_TOKEN_STORAGE_KEY);
  }
}

export function clearDashboardToken(): void {
  setDashboardToken(null);
}

function handleRejectedAuth(response: Response): void {
  if (response.status !== 401 && response.status !== 403) {
    return;
  }

  clearDashboardToken();
  globalThis.dispatchEvent(new Event("job-search-tool.dashboard-token-invalid"));
}

function requestHeaders(init?: RequestInit): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const incoming = init?.headers;
  if (incoming instanceof Headers) {
    incoming.forEach((value, key) => {
      headers[key] = value;
    });
  } else if (incoming) {
    Object.assign(headers, incoming);
  }

  const token = getDashboardToken();
  if (token) {
    headers["X-Job-Search-Token"] = token;
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: requestHeaders(init),
  });

  if (!response.ok) {
    handleRejectedAuth(response);
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: requestHeaders(init),
  });

  if (!response.ok) {
    handleRejectedAuth(response);
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.blob();
}

export function getDashboardAuthStatus(): Promise<DashboardAuthResponse> {
  return request<DashboardAuthResponse>("/dashboard/auth");
}

function query(params: object): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry !== undefined && entry !== "") {
          search.append(key, String(entry));
        }
      });
    } else if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

function jobIdsPayload(jobIds: string[] | string): string[] {
  return Array.isArray(jobIds) ? jobIds : [jobIds];
}

export function listJobs(params: JobListParams = {}): Promise<JobListResponse> {
  return request<JobListResponse>(`/jobs${query(params)}`);
}

export function getFacets(): Promise<FacetsResponse> {
  return request<FacetsResponse>("/jobs/facets");
}

export function getJob(jobId: string): Promise<JobRecord> {
  return request<JobRecord>(`/jobs/${encodeURIComponent(jobId)}`);
}

export function searchSimilarJobs(params: {
  q: string;
  n_results?: number;
  min_score?: number;
  site?: string;
}): Promise<SemanticJobResult[]> {
  return request<SemanticJobResult[]>(
    `/jobs/search/semantic${query({
      q: params.q,
      n_results: params.n_results,
      min_score: params.min_score,
      site: params.site,
    })}`,
  );
}

export function setBookmarked(
  jobIds: string[] | string,
  bookmarked: boolean,
): Promise<CommandResponse> {
  return request<CommandResponse>("/jobs/bookmark", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIdsPayload(jobIds), bookmarked }),
  });
}

export function setApplied(jobIds: string[] | string, applied: boolean): Promise<CommandResponse> {
  return request<CommandResponse>("/jobs/applied", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIdsPayload(jobIds), applied }),
  });
}

export function blacklistJobs(jobIds: string[]): Promise<CommandResponse> {
  return request<CommandResponse>("/blacklist", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export function deleteJobs(jobIds: string[]): Promise<CommandResponse> {
  return request<CommandResponse>("/jobs/delete", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export function listBlacklistedJobs(
  params: BlacklistListParams = {},
): Promise<BlacklistListResponse> {
  return request<BlacklistListResponse>(`/blacklist${query(params)}`);
}

export function unblacklistJobs(jobIds: string[]): Promise<CommandResponse> {
  return request<CommandResponse>("/blacklist/remove", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export function purgeBlacklist(olderThanDays?: number): Promise<CommandResponse> {
  return request<CommandResponse>("/blacklist/purge", {
    method: "POST",
    body: JSON.stringify({ older_than_days: olderThanDays ?? null }),
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

export function deleteJobsBelowScore(score: number): Promise<CommandResponse> {
  return request<CommandResponse>("/cleanup/delete-below-score", {
    method: "POST",
    body: JSON.stringify({ score }),
  });
}

export function deleteStaleJobs(days: number): Promise<CommandResponse> {
  return request<CommandResponse>("/cleanup/delete-stale", {
    method: "POST",
    body: JSON.stringify({ days }),
  });
}

export function purgeCleanupBlacklist(olderThanDays?: number): Promise<CommandResponse> {
  return request<CommandResponse>("/cleanup/purge-blacklist", {
    method: "POST",
    body: JSON.stringify({ older_than_days: olderThanDays ?? null }),
  });
}

export function exportJobs(payload: {
  format: ExportFormat;
  job_ids?: string[];
  filters?: JobListParams;
}): Promise<Blob> {
  if (payload.job_ids) {
    return requestBlob("/export/jobs", {
      method: "POST",
      body: JSON.stringify({ job_ids: payload.job_ids, format: payload.format }),
    });
  }

  return requestBlob(
    `/export/jobs${query({ ...(payload.filters ?? {}), format: payload.format })}`,
  );
}
