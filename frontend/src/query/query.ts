// The data layer: TanStack Query over the generated client (src/api).
//
// Query keys start with the resource, the first segment of its REST path:
//   ["jobs", "list", filters]   ["jobs", "one", id]   ["applications", "count"]
// A mutation names the resources it touches and invalidates them by that
// prefix (`touches: ["jobs", "applications"]`). Polling and refetch on focus
// keep data fresh; there is no Refresh button.
import { QueryClient, type QueryKey } from "@tanstack/react-query";
import { ApiError } from "../api/client";

/** A REST resource: the first segment of its path under /api/v1. */
export type Resource =
  | "applications"
  | "career"
  | "collection"
  | "documents"
  | "events"
  | "files"
  | "jobs"
  | "notes"
  | "preferences"
  | "providers"
  | "settings"
  | "sources"
  | "stats"
  | "tasks"
  | "templates"
  | "tokens"
  | "workspace";

/** How often a screen's lists are read again while it is open. */
export const POLL_MS = 30_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: true,
      // A missing record or a refused request does not get better by retrying.
      retry: (count, error) =>
        count < 2 && !(error instanceof ApiError && error.status < 500),
    },
    mutations: { retry: false },
  },
});

/** Read again every query of these resources that is on screen. */
export function invalidate(resources: readonly Resource[]) {
  return Promise.all(
    resources.map((resource) =>
      queryClient.invalidateQueries({ queryKey: [resource] }),
    ),
  );
}

/** The resource of a REST path: "/api/v1/jobs/J-1/triage" → "jobs". */
export function resourceOf(path: string) {
  return path
    .replace(/^\/api\/v1/, "")
    .split("?")[0]
    .split("/")
    .filter(Boolean)[0];
}

/** Whether a query key belongs to one of these resources. */
export const touches = (key: QueryKey, resources: readonly string[]) =>
  resources.includes(String(key[0]));

// Until every screen reads through Query (#222–#227), a write made by an old
// screen is announced as `openings:changed` with its path. Writes of one
// resource change others (shortlisting a job starts an application), so every
// query on screen is read again; only the shell's few queries exist meanwhile.
// Deleted with the old screens in #228.
if (typeof window !== "undefined")
  window.addEventListener("openings:changed", () => {
    void queryClient.invalidateQueries();
  });
