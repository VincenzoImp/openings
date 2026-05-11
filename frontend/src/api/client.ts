import type {
  CleanupResponse,
  CommandResponse,
  DashboardAuthResponse,
  JobListParams,
  JobListResponse,
  JobRecord,
  ScoreDistribution,
  StatsResponse
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

function requestHeaders(init?: RequestInit): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
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
    headers: requestHeaders(init)
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getDashboardAuthStatus(): Promise<DashboardAuthResponse> {
  return request<DashboardAuthResponse>("/dashboard/auth");
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
