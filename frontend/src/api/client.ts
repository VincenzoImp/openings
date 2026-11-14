// The typed API client: openapi-fetch over the types generated from the
// backend's OpenAPI document (schema.d.ts, `npm run api:gen`). A model that
// changes in the backend changes these types, so drift is a compile error.
//
//   const jobs = await call(api.GET("/api/v1/jobs", { params: { query: { q } } }));
//
// The browser session sends the CSRF token on every write; a 401 outside the
// sign-in asks the shell to sign in again ("openings:unauthorized"); a failed
// request throws an ApiError built from the backend's Error model. Bytes
// (downloads and uploads with a grant) are plain fetch calls below.
import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

/** A response or request model of the API, by its schema name. */
export type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];
export type ErrorBody = Schema<"ErrorBody">;
type Grant = Schema<"FileGrant"> | Schema<"OperationGrant">;

let csrfToken = "";
/** Remember the session's CSRF token (GET /api/v1/auth/session). */
export function setCsrf(value: string) {
  csrfToken = value;
}

/** A failed request: the backend's {code, status, message, details}. */
export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(body: Partial<ErrorBody>, status: number) {
    super(body.message || `Request failed (${status})`);
    this.status = body.status ?? status;
    this.code = body.code || "request_failed";
    this.details = body.details ?? null;
  }
  /** The record's current version, when a write conflicted with a newer one. */
  get currentVersion(): number | undefined {
    const details = this.details as { current_version?: number } | null;
    return details?.current_version;
  }
  /** Field errors of a validation failure, as "field: message". */
  get fields(): string[] {
    if (!Array.isArray(this.details)) return [];
    return this.details.map((item: { field?: unknown[]; message?: string }) => {
      const field = item.field
        ?.filter((part) => part !== "body" && part !== "query")
        .join(".");
      return `${field ? field + ": " : ""}${item.message || "Invalid value."}`;
    });
  }
}

const READS = new Set(["GET", "HEAD", "OPTIONS"]);
const SIGN_IN = /\/auth\/(session|login|setup)$/;

function signal(name: string, detail?: string) {
  if (typeof window !== "undefined")
    window.dispatchEvent(new CustomEvent(name, { detail }));
}

const session: Middleware = {
  onRequest({ request }) {
    if (!READS.has(request.method) && csrfToken)
      request.headers.set("X-CSRF-Token", csrfToken);
    return request;
  },
  onResponse({ request, response }) {
    const path = new URL(request.url, "http://localhost").pathname;
    if (response.status === 401 && !SIGN_IN.test(path))
      signal("openings:unauthorized");
    else if (response.ok && !READS.has(request.method))
      signal("openings:changed", path);
    return response;
  },
};

/** The client: paths, methods, parameters and bodies are checked by the compiler. */
export const api = createClient<paths>({
  baseUrl: typeof location === "undefined" ? "http://localhost" : "",
  credentials: "same-origin",
  headers: { Accept: "application/json" },
  // Looked up on each call, so a test can replace it.
  fetch: (request) => fetch(request),
});
api.use(session);

/** The data of a response, or an ApiError. */
export async function call<Data>(
  pending: Promise<{ data?: Data; error?: unknown; response: Response }>,
): Promise<Data> {
  const { data, error, response } = await pending;
  if (response.ok) return data as Data;
  const body = (error as { error?: Partial<ErrorBody> } | undefined)?.error;
  throw new ApiError(body ?? {}, response.status);
}

async function failure(response: Response) {
  const body = await response.json().catch(() => ({}));
  return new ApiError(body?.error ?? {}, response.status);
}

/** Download bytes (a backup, the export, a file's content) with the session. */
export async function download(path: string, init: RequestInit = {}) {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!READS.has(method) && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(path, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) throw await failure(response);
  const disposition = response.headers.get("Content-Disposition") || "";
  const name = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/.exec(
    disposition,
  );
  return {
    blob: await response.blob(),
    filename: decodeURIComponent(name?.[1] || name?.[2] || ""),
  };
}

/** Send or fetch bytes with a grant (files_reserve_upload, a revision's uploads). */
export async function transfer(grant: Grant, body?: Blob) {
  const response = await fetch(grant.url, {
    method: grant.method,
    headers: grant.headers,
    body,
  });
  if (!response.ok) throw await failure(response);
  return response;
}

/** Offer a downloaded blob to the person as a file. */
export function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
