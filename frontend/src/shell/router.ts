// The router: the current route from the location hash, `navigate()` and a
// leave guard. Links are plain `<a href="#jobs">`; the hash change is read
// here. An address that names no route is replaced by Today.
import { useSyncExternalStore } from "react";
import { resolve, match, href, type Route, type RouteId } from "./routes";

export { href, type Route, type RouteId };

type Guard = (proceed: () => void) => boolean;
const guards = new Set<Guard>();

/**
 * Ask before leaving the current address. A guard returns true to let the
 * navigation happen now; false stops it, and the guard calls `proceed` once
 * the person decided to leave (its own in-app dialog). Returns the removal.
 */
export function addLeaveGuard(guard: Guard) {
  guards.add(guard);
  return () => {
    guards.delete(guard);
  };
}
function mayLeave(proceed: () => void) {
  for (const guard of guards) if (!guard(proceed)) return false;
  return true;
}

const listeners = new Set<() => void>();
const hashNow = () => location.hash.replace(/^#/, "");
let last = typeof location === "undefined" ? "" : hashNow();
let cached: Route | null = null;

function emit() {
  if (!match(hashNow())) history.replaceState(null, "", "#today");
  last = hashNow();
  for (const listener of listeners) listener();
}

function onHashChange() {
  const next = hashNow();
  if (next === last) return;
  // A link or the browser's back button: the guard may keep the page.
  if (
    !mayLeave(() => {
      history.pushState(null, "", "#" + next);
      emit();
    })
  ) {
    history.replaceState(null, "", "#" + last);
    return;
  }
  emit();
}

if (typeof window !== "undefined") {
  window.addEventListener("hashchange", onHashChange);
  window.addEventListener("popstate", onHashChange);
  // A screen rewrote its own query (filters, the selected row): no guard.
  window.addEventListener("openings:url", () => {
    if (hashNow() !== last) emit();
  });
  // An address that names no route becomes Today, without a history entry.
  emit();
}

function current(): Route {
  const hash = hashNow();
  if (!cached || cached.hash !== hash) cached = resolve(hash);
  return cached;
}

/** The route on screen; the component renders again when it changes. */
export function useRoute(): Route {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    current,
    current,
  );
}

/**
 * Go to an address ("#jobs?job=…", or href("application", { id })). With
 * `replace` the current history entry is replaced. Screens that read their
 * query from the address (useUrlState) are told with a popstate event.
 */
export function navigate(to: string, { replace = false } = {}) {
  const target = to.replace(/^#?/, "#");
  const go = () => {
    if (replace) history.replaceState(null, "", target);
    else history.pushState(null, "", target);
    emit();
    window.dispatchEvent(new PopStateEvent("popstate"));
  };
  if (target.slice(1) === last) {
    window.dispatchEvent(new PopStateEvent("popstate"));
    return;
  }
  if (mayLeave(go)) go();
}
