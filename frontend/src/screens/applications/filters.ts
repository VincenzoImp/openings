// The list's state in its address: `#applications?stage=ready&sort=deadline`.
// Filters the server reads (search, outcome, waiting) and the ones applied to
// the rows read (priority, deadline, source). No React: tested directly.
import {
  OUTCOMES,
  daysBetween,
  type AppFacts,
  type SortKey,
  type StageFilter,
} from "./model.ts";

export interface Filters {
  stage: StageFilter;
  q: string;
  sort: SortKey;
  outcome: string;
  priority: string;
  deadline: string;
  source: string;
  /** Sent applications past the no-reply period (Today's "Waiting"). */
  waiting: boolean;
  stats: boolean;
}

const STAGES = [
  "shortlisted",
  "ready",
  "applied",
  "interview",
  "offer",
  "closed",
  "all",
];
const SORT_KEYS = ["needs", "deadline", "updated", "applied"];

export function readFilters(query: URLSearchParams): Filters {
  const stage = query.get("stage") || "all";
  const sort = query.get("sort") || "needs";
  return {
    stage: (STAGES.includes(stage) ? stage : "all") as StageFilter,
    q: query.get("q") || "",
    sort: (SORT_KEYS.includes(sort) ? sort : "needs") as SortKey,
    outcome: OUTCOMES[query.get("outcome") || ""] ? query.get("outcome")! : "",
    priority: /^[1-5]$/.test(query.get("priority") || "")
      ? query.get("priority")!
      : "",
    deadline: DEADLINES[query.get("deadline") || ""]
      ? query.get("deadline")!
      : "",
    source: query.get("source") || "",
    waiting: query.get("waiting") === "1",
    stats: query.get("section") === "stats",
  };
}

/** The address query of a set of filters; defaults are left out. */
export function writeFilters(filters: Filters): Record<string, string> {
  const query: Record<string, string> = {};
  if (filters.stats) query.section = "stats";
  if (filters.stage !== "all") query.stage = filters.stage;
  if (filters.q) query.q = filters.q;
  if (filters.sort !== "needs") query.sort = filters.sort;
  for (const key of ["outcome", "priority", "deadline", "source"] as const)
    if (filters[key]) query[key] = filters[key];
  if (filters.waiting) query.waiting = "1";
  return query;
}

export const DEADLINES: Record<string, string> = {
  week: "Due within 7 days",
  overdue: "Overdue",
  set: "Has a deadline",
  none: "No deadline",
};
export const PRIORITIES: Record<string, string> = {
  "1": "1 · Highest",
  "2": "2 · High",
  "3": "3 · Medium",
  "4": "4 · Low",
  "5": "5 · Lowest",
};

/** Whether a row passes the filters the dashboard applies itself. */
export function passes(
  app: AppFacts & { job: unknown },
  filters: Filters,
  now = new Date(),
) {
  if (filters.priority && String(app.priority ?? "") !== filters.priority)
    return false;
  if (filters.source) {
    const job = (app.job ?? {}) as { source?: unknown };
    if (String(job.source ?? "") !== filters.source) return false;
  }
  if (filters.deadline) {
    const days = app.deadline ? daysBetween(now, app.deadline) : null;
    const ok = {
      week: days != null && days >= 0 && days <= 7,
      overdue: days != null && days < 0,
      set: days != null,
      none: days == null,
    }[filters.deadline];
    if (!ok) return false;
  }
  return true;
}

/** The active filters as chips: field and value. */
export function filterChips(filters: Filters, noReplyDays: number) {
  const chips: { key: keyof Filters; field: string; value: string }[] = [];
  if (filters.waiting)
    chips.push({
      key: "waiting",
      field: "Waiting",
      value: `no reply for over ${noReplyDays} days`,
    });
  if (filters.priority)
    chips.push({
      key: "priority",
      field: "Priority",
      value: PRIORITIES[filters.priority],
    });
  if (filters.deadline)
    chips.push({
      key: "deadline",
      field: "Deadline",
      value: DEADLINES[filters.deadline],
    });
  if (filters.source)
    chips.push({ key: "source", field: "Source", value: filters.source });
  if (filters.outcome)
    chips.push({
      key: "outcome",
      field: "Outcome",
      value: OUTCOMES[filters.outcome],
    });
  return chips;
}

/** The filters without any narrowing: same stage, view and sort. */
export const cleared = (filters: Filters): Filters => ({
  ...filters,
  q: "",
  outcome: "",
  priority: "",
  deadline: "",
  source: "",
  waiting: false,
});
