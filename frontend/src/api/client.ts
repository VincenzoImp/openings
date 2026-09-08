import type {
  AddJobRequest,
  Attachment,
  AttachmentEntry,
  AttachmentKind,
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
  NoteKind,
  NoteRequest,
  PostingFields,
  RunRecord,
  RunStatus,
  ScoreDistribution,
  SemanticResult,
  SettingsSummary,
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
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
        .filter(Boolean)
        .join("; ");
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
  signal?: AbortSignal;
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
    signal: options.signal,
  });
  if (response.status === 401) {
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

export function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(header);
  return match?.[1] ?? fallback;
}

export interface Download {
  blob: Blob;
  filename: string;
}

export const api = {
  dashboardAuth: () => request<DashboardAuthResponse>("/dashboard/auth"),

  listJobs: (params: JobListParams = {}, signal?: AbortSignal) =>
    request<JobListResponse>(`/jobs${buildQuery(params as Record<string, unknown>)}`, { signal }),
  getJob: (jobId: string) => request<JobDetail>(`/jobs/${encodeURIComponent(jobId)}`),
  addJob: (payload: AddJobRequest) => request<CommandResponse>("/jobs", { json: payload }),
  updateJob: (jobId: string, fields: PostingFields) =>
    request<JobDetail>(`/jobs/${encodeURIComponent(jobId)}`, { method: "PATCH", json: fields }),
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
  mergeJobs: (primaryId: string, otherIds: string[]) =>
    request<CommandResponse>("/jobs/merge", {
      json: { primary_id: primaryId, other_ids: otherIds },
    }),
  similarJobs: (jobId: string, n = 8) =>
    request<SemanticResult[]>(
      `/jobs/${encodeURIComponent(jobId)}/similar${buildQuery({ n_results: n })}`,
    ),
  semanticSearch: (q: string, params: { n_results?: number; statuses?: JobStatus[] } = {}) =>
    request<SemanticResult[]>(`/jobs/search/semantic${buildQuery({ q, ...params })}`),

  addNote: (jobId: string, payload: NoteRequest) =>
    request<Note>(`/jobs/${encodeURIComponent(jobId)}/notes`, { json: payload }),
  updateNote: (
    jobId: string,
    noteId: number,
    payload: { kind?: NoteKind; title?: string | null; body?: string },
  ) =>
    request<Note>(`/jobs/${encodeURIComponent(jobId)}/notes/${noteId}`, {
      method: "PUT",
      json: payload,
    }),
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
  updateAttachment: (
    jobId: string,
    attachmentId: number,
    payload: { kind?: AttachmentKind; note?: string | null; filename?: string },
  ) =>
    request<Attachment>(`/jobs/${encodeURIComponent(jobId)}/attachments/${attachmentId}`, {
      method: "PATCH",
      json: payload,
    }),
  attachmentUrl: (jobId: string, attachmentId: number, inline = false) =>
    `${API_ROOT}/jobs/${encodeURIComponent(jobId)}/attachments/${attachmentId}${inline ? "?inline=true" : ""}`,
  downloadAttachment: async (jobId: string, attachment: Attachment): Promise<Download> => {
    const response = await send(`/jobs/${encodeURIComponent(jobId)}/attachments/${attachment.id}`);
    return { blob: await response.blob(), filename: filenameFrom(response, attachment.filename) };
  },
  fetchAttachmentBlob: async (jobId: string, attachmentId: number): Promise<Blob> => {
    const response = await send(
      `/jobs/${encodeURIComponent(jobId)}/attachments/${attachmentId}?inline=true`,
    );
    return response.blob();
  },
  deleteAttachment: (jobId: string, attachmentId: number) =>
    request<{ success: boolean }>(
      `/jobs/${encodeURIComponent(jobId)}/attachments/${attachmentId}`,
      { method: "DELETE" },
    ),
  listAttachments: (params: {
    kind?: AttachmentKind;
    statuses?: JobStatus[];
    limit?: number;
    offset?: number;
  }) =>
    request<{ items: AttachmentEntry[]; total: number; limit: number; offset: number }>(
      `/attachments${buildQuery(params)}`,
    ),
  downloadBundle: async (jobId: string): Promise<Download> => {
    const response = await send(`/jobs/${encodeURIComponent(jobId)}/bundle.zip`);
    return { blob: await response.blob(), filename: filenameFrom(response, "openings.zip") };
  },

  listLabels: () => request<{ value: string; count: number }[]>("/labels"),
  renameLabel: (oldName: string, newName: string) =>
    request<CommandResponse>("/labels/rename", { json: { old: oldName, new: newName } }),
  deleteLabel: (label: string) => request<CommandResponse>("/labels/delete", { json: { label } }),

  listBlacklist: (params: { limit?: number; offset?: number; text?: string } = {}) =>
    request<JobListResponse>(`/blacklist${buildQuery(params)}`),
  blacklist: (jobIds: string[], note?: string | null) =>
    request<CommandResponse>("/blacklist", { json: { job_ids: jobIds, note: note ?? null } }),
  unblacklist: (jobIds: string[]) =>
    request<CommandResponse>("/blacklist/remove", { json: { job_ids: jobIds } }),

  listSources: () => request<SourceStatus[]>("/sources"),
  companyStatuses: (company: string) =>
    request<Record<string, number>>(`/companies/${encodeURIComponent(company)}/statuses`),
  listRuns: (limit = 30) => request<RunRecord[]>(`/runs${buildQuery({ limit })}`),
  runStatus: () => request<RunStatus>("/runs/status"),
  requestRun: () => request<RunStatus>("/runs", { method: "POST" }),
  stats: () => request<StatsResponse>("/stats"),
  distribution: (binSize = 5) =>
    request<ScoreDistribution>(`/distribution${buildQuery({ bin_size: binSize })}`),
  facets: (params: { limit?: number; q?: string } = {}) =>
    request<FacetsResponse>(`/jobs/facets${buildQuery(params)}`),
  settings: () => request<SettingsSummary>("/settings"),
  settingsReference: async () => (await send("/settings/reference")).text(),

  exportJobs: async (params: JobListParams, format: ExportFormat): Promise<Download> => {
    const response = await send(
      `/export/jobs${buildQuery({ ...(params as Record<string, unknown>), format })}`,
    );
    return {
      blob: await response.blob(),
      filename: filenameFrom(response, `openings-export.${format}`),
    };
  },

  cleanupPreview: () => request<CleanupReport>("/cleanup/preview"),
  cleanupRun: () => request<CleanupReport>("/cleanup/run", { method: "POST" }),
  deleteBelowScore: (score: number, dryRun = false) =>
    request<CommandResponse>("/cleanup/delete-below-score", {
      json: { score, dry_run: dryRun },
    }),
  deleteStale: (days: number, dryRun = false) =>
    request<CommandResponse>("/cleanup/delete-stale", { json: { days, dry_run: dryRun } }),
};

export type Api = typeof api;
