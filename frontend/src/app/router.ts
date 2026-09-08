import { useMemo, useSyncExternalStore } from "react";

export type View = "inbox" | "pipeline" | "companies" | "runs" | "system";

export const VIEWS: { id: View; label: string; key: string }[] = [
  { id: "inbox", label: "Inbox", key: "1" },
  { id: "pipeline", label: "Pipeline", key: "2" },
  { id: "companies", label: "Companies", key: "3" },
  { id: "runs", label: "Runs", key: "4" },
  { id: "system", label: "System", key: "5" },
];

export interface Route {
  view: View;
  jobId: string | null;
  /** Every other query parameter, owned by the current view (filters, tabs). */
  params: URLSearchParams;
}

const NAVIGATE_EVENT = "openings.navigate";
const RESERVED = new Set(["view", "job"]);

function isView(value: string | null): value is View {
  return VIEWS.some((view) => view.id === value);
}

export function parseRoute(search: string): Route {
  const all = new URLSearchParams(search);
  const view = all.get("view");
  const params = new URLSearchParams();
  for (const [key, value] of all.entries()) {
    if (!RESERVED.has(key)) {
      params.append(key, value);
    }
  }
  return { view: isView(view) ? view : "inbox", jobId: all.get("job"), params };
}

export function routeHref(
  route: Partial<Pick<Route, "view" | "jobId">> & { params?: URLSearchParams | null },
  current?: Route,
): string {
  const base = current ?? parseRoute(window.location.search);
  const view = route.view ?? base.view;
  const jobId = route.jobId === undefined ? base.jobId : route.jobId;
  const keep = route.params === undefined ? base.params : route.params;
  const out = new URLSearchParams();
  out.set("view", view);
  if (jobId) {
    out.set("job", jobId);
  }
  if (keep && view === base.view) {
    for (const [key, value] of keep.entries()) {
      out.append(key, value);
    }
  } else if (keep && route.params !== undefined) {
    for (const [key, value] of keep.entries()) {
      out.append(key, value);
    }
  }
  return `?${out.toString()}`;
}

export function navigate(
  route: Partial<Pick<Route, "view" | "jobId">> & { params?: URLSearchParams | null },
  options: { replace?: boolean } = {},
): void {
  const href = routeHref(route);
  if (href === window.location.search) {
    return;
  }
  if (options.replace) {
    window.history.replaceState(null, "", href);
  } else {
    window.history.pushState(null, "", href);
  }
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

/** Update the current view's parameters in the URL without a history entry. */
export function setParams(patch: Record<string, string | string[] | null | undefined>): void {
  const route = parseRoute(window.location.search);
  const params = new URLSearchParams(route.params);
  for (const [key, value] of Object.entries(patch)) {
    params.delete(key);
    if (value === null || value === undefined || value === "") {
      continue;
    }
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== "") {
        params.append(key, item);
      }
    }
  }
  navigate({ params }, { replace: true });
}

function subscribe(callback: () => void): () => void {
  window.addEventListener("popstate", callback);
  window.addEventListener(NAVIGATE_EVENT, callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener(NAVIGATE_EVENT, callback);
  };
}

function snapshot(): string {
  return window.location.search;
}

export function useRoute(): Route {
  const search = useSyncExternalStore(subscribe, snapshot, snapshot);
  return useMemo(() => parseRoute(search), [search]);
}
