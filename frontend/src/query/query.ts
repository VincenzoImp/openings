// The data layer: TanStack Query over the generated client (src/api).
//
// Query keys start with the resource, the first segment of its REST path:
//   ["jobs", "list", filters]   ["jobs", "one", id]   ["applications", "count"]
// A mutation names the resources it touches and invalidates them by that
// prefix (`touches: ["jobs", "applications"]`). Polling and refetch on focus
// keep data fresh; there is no Refresh button.
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";

/** A REST resource: the first segment of its path under /api/v1. */
export type Resource =
  | "applications"
  | "backups"
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
  | "skills"
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
