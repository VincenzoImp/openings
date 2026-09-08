import type {
  AddJobRequest,
  Attachment,
  AttachmentKind,
  BlacklistListParams,
  BlacklistListResponse,
  CleanupReport,
  CommandResponse,
  DashboardAuthResponse,
  ExportFormat,
  FacetsResponse,
  JobDetail,
  JobListParams,
  JobListResponse,
  JobStatus,
  Note,
  NoteRequest,
  RunRecord,
  ScoreDistribution,
  SemanticResult,
  SourceStatus,
  StatsResponse,
} from "./types";

const API_ROOT = "/api";
const TOKEN_KEY = "openings.dashboard-token";
export const TOKEN_HEADER = "X-Openings-Token";
export const TOKEN_INVALID_EVENT = "openings.token-invalid";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function storage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  const token = storage()?.getItem(TOKEN_KEY)?.trim();
  return token || null;
}

export function setToken(token: string | null): void {
  const store = storage();
  if (!store) {
    return;
  }
  const normalized = token?.trim() ?? "";
  if (normalized) {
    store.setItem(TOKEN_KEY, normalized);
  } else {
    store.removeItem(TOKEN_KEY);
  }
}

/** Serialize query parameters; arrays repeat the key, empty values are dropped. */
export function buildQuery(params: Record<string, unknown> | undefined): string {
  if (!params) {
    return "";
  }
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") {
          search.append(key, String(item));
        }
      }
    } else {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (payload.detail) {
      return JSON.stringify(payload.detail);
    }
  } catch {
    // fall through to the status text
  }
  return response.statusText || `HTTP ${response.status}`;
}

interface RequestOptions {
  method?: string;
  json?: unknown;
  body?: BodyInit;
}

async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers[TOKEN_HEADER] = token;
  }
  let body = options.body;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    method: options.method ?? (body ? "POST" : "GET"),
    headers,
    body,
  });
  if (response.status === 401 || response.status === 403) {
    globalThis.dispatchEvent(new Event(TOKEN_INVALID_EVENT));
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return response;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options);
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(header);
  return match?.[1] ?? fallback;
}

export const api = {
  dashboardAuth: () => request<DashboardAuthResponse>("/dashboard/auth"),

  listJobs: (params: JobListParams = {}) =>
    request<JobListResponse>(`/jobs${buildQuery(params as Record<string, unknown>)}`),
  getJob: (jobId: string) => request<JobDetail>(`/jobs/${encodeURIComponent(jobId)}`),
  addJob: (payload: AddJobRequest) => request<CommandResponse>("/jobs", { json: payload }),
  setStatus: (jobIds: string[], status: JobStatus, note?: string | null) =>
    request<CommandResponse>("/jobs/status", {
      json: { job_ids: jobIds, status, note: note ?? null },
    }),
  addLabels: (jobIds: string[], labels: string[]) =>
    request<CommandResponse>("/jobs/labels", { json: { job_ids: jobIds, labels } }),
  removeLabels: (jobIds: string[], labels: string[]) =>
    request<CommandResponse>("/jobs/labels/remove", { json: { job_ids: jobIds, labels } }),
  deleteJobs: (jobIds: string[]) =>
    request<CommandResponse>("/jobs/delete", { json: { job_ids: jobIds } }),

  addNote: (jobId: string, payload: NoteRequest) =>
    request<Note>(`/jobs/${encodeURIComponent(jobId)}/notes`, { json: payload }),
  deleteNote: (jobId: string, noteId: number) =>
    request<{ success: boolean }>(`/jobs/${encodeURIComponent(jobId)}/notes/${noteId}`, {
      method: "DELETE",
    }),

  uploadAttachment: (jobId: string, file: File, kind: AttachmentKind, note?: string) => {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("kind", kind);
    if (note) {
      form.append("note", note);
    }
    return request<Attachment>(`/jobs/${encodeURIComponent(jobId)}/attachments`, {
      method: "POST",
      body: form,
    });
  },
  downloadAttachment: async (jobId: string, attachment: Attachment) => {
    const response = await send(`/jobs/${encodeURIComponent(jobId)}/attachments/${attachment.id}`);
    saveBlob(await response.blob(), filenameFrom(response, attachment.filename));
  },
  deleteAttachment: (jobId: string, attachmentId: number) =>
    request<{ success: boolean }>(
      `/jobs/${encodeURIComponent(jobId)}/attachments/${attachmentId}`,
      { method: "DELETE" },
    ),

  listBlacklist: (params: BlacklistListParams = {}) =>
    request<BlacklistListResponse>(`/blacklist${buildQuery(params as Record<string, unknown>)}`),
  blacklist: (jobIds: string[]) =>
    request<CommandResponse>("/blacklist", { json: { job_ids: jobIds } }),
  unblacklist: (jobIds: string[]) =>
    request<CommandResponse>("/blacklist/remove", { json: { job_ids: jobIds } }),
  purgeBlacklist: (olderThanDays?: number | null) =>
    request<CommandResponse>("/blacklist/purge", {
      json: { older_than_days: olderThanDays ?? null },
    }),

  listSources: () => request<SourceStatus[]>("/sources"),
  listRuns: (limit = 20) => request<RunRecord[]>(`/runs${buildQuery({ limit })}`),
  stats: () => request<StatsResponse>("/stats"),
  distribution: (binSize = 5) =>
    request<ScoreDistribution>(`/distribution${buildQuery({ bin_size: binSize })}`),
  facets: () => request<FacetsResponse>("/jobs/facets"),
  semanticSearch: (q: string, nResults = 10) =>
    request<SemanticResult[]>(`/jobs/search/semantic${buildQuery({ q, n_results: nResults })}`),

  exportJobs: async (params: JobListParams, format: ExportFormat) => {
    const response = await send(
      `/export/jobs${buildQuery({ ...(params as Record<string, unknown>), format })}`,
    );
    saveBlob(await response.blob(), filenameFrom(response, `openings-export.${format}`));
  },

  cleanupPreview: () => request<CleanupReport>("/cleanup/preview"),
  cleanupRun: () => request<CleanupReport>("/cleanup/run", { method: "POST" }),
  deleteBelowScore: (score: number) =>
    request<CommandResponse>("/cleanup/delete-below-score", { json: { score } }),
  deleteStale: (days: number) =>
    request<CommandResponse>("/cleanup/delete-stale", { json: { days } }),
};

export type Api = typeof api;
