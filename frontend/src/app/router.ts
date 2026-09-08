import { useSyncExternalStore } from "react";

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
}

const NAVIGATE_EVENT = "openings.navigate";

function isView(value: string | null): value is View {
  return VIEWS.some((view) => view.id === value);
}

export function parseRoute(search: string): Route {
  const params = new URLSearchParams(search);
  const view = params.get("view");
  return { view: isView(view) ? view : "inbox", jobId: params.get("job") };
}

export function routeHref(route: Partial<Route>, current?: Route): string {
  const base = current ?? parseRoute(window.location.search);
  const view = route.view ?? base.view;
  const jobId = route.jobId === undefined ? base.jobId : route.jobId;
  const params = new URLSearchParams();
  params.set("view", view);
  if (jobId) {
    params.set("job", jobId);
  }
  return `?${params.toString()}`;
}

export function navigate(route: Partial<Route>, options: { replace?: boolean } = {}): void {
  const href = routeHref(route);
  if (options.replace) {
    window.history.replaceState(null, "", href);
  } else {
    window.history.pushState(null, "", href);
  }
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
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
  return parseRoute(search);
}
