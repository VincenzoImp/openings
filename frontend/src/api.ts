export type Json = Record<string, unknown>;
export interface ListResult<T> {
  items: T[];
  total: number;
  stage_counts?: Record<string, number>;
  facets?: Record<string, string[]>;
}
export interface Versioned {
  id: string;
  version: number;
  created_at?: string;
  updated_at?: string;
}
export type Triage = "inbox" | "saved" | "dismissed";
export type Stage = "draft" | "applied" | "interview" | "offer" | "closed";
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
  postings?: Json[];
  triage: Triage;
  score: number | null;
  score_outdated: boolean;
  metadata: Json;
  salary?: string;
  source?: string;
  availability?: string;
  notes?: Note[];
}
export interface Note {
  id: string;
  body: string;
  text?: string;
  created_at: string;
  version?: number;
}
export interface Question {
  id: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: string[];
  max_length?: number;
}
export interface Application extends Versioned {
  job_id: string;
  status: Stage;
  outcome: string | null;
  note: string;
  questions: Question[];
  answers: Record<string, unknown>;
  job?: Job;
  applied_at?: string;
  documents_count?: number;
}
export interface Profile {
  name: string;
  headline: string;
  location: string;
  email: string;
  phone: string;
  scoring_summary?: string;
  roles: string;
  preferences: string;
  summary: string;
  links: unknown[];
  metadata: Json;
  version: number;
}
export interface Knowledge extends Versioned {
  kind: string;
  title: string;
  narrative: string;
  narrative_preview?: string;
  metadata: Json;
}
export interface Claim extends Versioned {
  knowledge_id: string;
  text: string;
  text_preview?: string;
  knowledge_title?: string;
  approved: boolean;
  metadata: Json;
}
export interface Template extends Versioned {
  name: string;
  kind: "resume" | "cover_letter";
  tex: string;
  guidance: string;
  rules: Record<string, number>;
  is_default: boolean;
}
export interface Instructions {
  general: string;
  version: number;
}
export interface Document extends Versioned {
  application_id: string;
  context_id: string | null;
  kind: string;
  title: string;
  content: Json;
  previous_id?: string;
  review_state: string;
  revision_number?: number;
  files?: WorkspaceFile[];
}
export interface WorkspaceFile {
  id: string;
  name: string;
  size: number;
  media_type: string;
  sha256?: string;
  created_at?: string;
  download_url?: string;
  url?: string;
}
export interface Source extends Versioned {
  name: string;
  kind: string;
  config: Json;
  url?: string;
  enabled: boolean;
  filters: Json;
  schedule: Json;
  next_run_at?: string;
  last_run_at?: string;
  last_error?: string;
  last_result?: Json;
  last_outcome?: string;
  last_counts?: Json;
  last_task_id?: string;
}
export interface Scoring {
  enabled: boolean;
  mode: "local" | "remote";
  provider: "laya" | "systemone";
  base_url: string;
  model: string;
  api_key?: string;
  api_key_set?: boolean;
  rubric: string;
  criteria?: string[];
  periodic_rescore: { enabled: boolean; minutes: number; batch_size: number };
  max_len: number;
  timeout_seconds: number;
  version: number;
}
export interface Activity {
  id?: string;
  kind?: string;
  type?: string;
  message?: string;
  title?: string;
  created_at: string;
  payload?: Json;
  application_id?: string;
  job_id?: string;
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
  inbox: number;
  outdated: number;
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
  constructor(
    message: string,
    public status: number,
    public code = "request_failed",
  ) {
    super(message);
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
  const value =
    response.status === 204 ? {} : await response.json().catch(() => ({}));
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
export async function uploadFile(
  file: File,
  ownerType: string,
  ownerId: string,
) {
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
    media_type: file.type || "application/octet-stream",
  });
  const response = await fetch(ticket.url, {
    method: ticket.method || "PUT",
    headers: ticket.headers,
    body: file,
  });
  if (!response.ok)
    throw new ApiError("The file could not be uploaded.", response.status);
  window.dispatchEvent(
    new CustomEvent("openings:changed", { detail: "/files" }),
  );
  return response.json().catch(() => ({}));
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

export function jsonValue(
  form: FormData,
  name: string,
  fallback: unknown = {},
) {
  const raw = String(form.get(name) || "").trim();
  return raw ? JSON.parse(raw) : fallback;
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
