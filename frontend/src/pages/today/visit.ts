// "Since your last visit": which moment Today counts from.
//
// The rule: a visit lasts while Today keeps being opened; it ends when Today
// has not been open for 30 minutes. The next time Today opens, "since your
// last visit" starts at the last moment Today was open in the visit before.
// So the list is stable while the owner works (a reload, or a look at a run
// and back, changes nothing) and moves on only after a real absence. The
// browser remembers it (localStorage); without storage, or on the very first
// visit, Today shows the last 7 days and says so.

export const VISIT_KEY = "openings-today-visit";
export const VISIT_GAP_MS = 30 * 60_000;
export const FIRST_VISIT_DAYS = 7;

export interface Visit {
  /** Where "since your last visit" starts; null on the first visit. */
  since: string | null;
  /** The last moment Today was open. */
  seen: string;
}

/** The stored visit, or null when nothing usable is stored. */
export function parseVisit(raw: string | null): Visit | null {
  try {
    const value = JSON.parse(raw || "null") as Partial<Visit> | null;
    if (!value || Number.isNaN(Date.parse(value.seen || ""))) return null;
    const since =
      value.since && !Number.isNaN(Date.parse(value.since))
        ? value.since
        : null;
    return { since, seen: value.seen! };
  } catch {
    return null;
  }
}

/** The visit when Today opens at `now`: the same one, or a new one after an absence. */
export function openVisit(stored: Visit | null, now: Date): Visit {
  const seen = now.toISOString();
  if (!stored) return { since: null, seen };
  const away = now.valueOf() - Date.parse(stored.seen);
  return away > VISIT_GAP_MS
    ? { since: stored.seen, seen }
    : { since: stored.since, seen };
}

/** The moment the "since" lists start from, for the API. */
export function sinceOf(visit: Visit, now: Date) {
  return (
    visit.since ??
    new Date(now.valueOf() - FIRST_VISIT_DAYS * 86_400_000).toISOString()
  );
}

interface Store {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
function storage(): Store | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}
function remember(visit: Visit, store: Store | null) {
  try {
    store?.setItem(VISIT_KEY, JSON.stringify(visit));
  } catch {
    // Storage can be unavailable; the visit then lasts for this page only.
  }
}
/** Open Today now: read the stored visit, decide, and remember it. */
export function beginVisit(now = new Date(), store = storage()): Visit {
  let stored: Visit | null = null;
  try {
    stored = parseVisit(store?.getItem(VISIT_KEY) ?? null);
  } catch {
    // Unreadable storage counts as a first visit.
  }
  const visit = openVisit(stored, now);
  remember(visit, store);
  return visit;
}
/** Today is still open, or is being left, at `now`. */
export function touchVisit(visit: Visit, now = new Date(), store = storage()) {
  remember({ since: visit.since, seen: now.toISOString() }, store);
}
