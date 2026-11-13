// How a run and its changes are put into words. No React: tested directly.
import type { Activity, Run, RunStatus } from "../../api";
import { readyReason } from "../../library/ready.ts";
import { dayTime, duration } from "../../library/time.ts";

export const runStatus: Record<
  RunStatus,
  { label: string; tone: "info" | "ready" | "attention" }
> = {
  open: { label: "In progress", tone: "info" },
  finished: { label: "Finished", tone: "ready" },
  interrupted: { label: "Interrupted", tone: "attention" },
};

// The names of application stages and of job queues a change moves between.
const places: Record<string, string> = {
  draft: "Preparing",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
  inbox: "Inbox",
  saved: "Shortlist",
  dismissed: "Dismissed",
};

/** What a change did beyond its name: where it moved a record, the fields it touched. */
export function changeDetail(event: Activity) {
  const payload = event.payload || {};
  const place = (value: unknown) => places[String(value)] || String(value);
  if (payload.to && payload.to !== payload.from)
    return `${payload.from ? place(payload.from) + " → " : ""}${place(payload.to)}`;
  if (Array.isArray(payload.fields) && payload.fields.length)
    return "Fields: " + payload.fields.join(", ").replaceAll("_", " ");
  if (event.kind === "application_ready_cleared") return readyReason(payload);
  return "";
}

/** "Application marked ready" from `application_marked_ready`. */
export function changeLabel(kind?: string) {
  const text = (kind || "updated").replaceAll("_", " ");
  return text[0].toUpperCase() + text.slice(1);
}

// What a count of one kind of change counts, singular and plural.
const counted: Record<string, [string, string]> = {
  application_created: ["application started", "applications started"],
  application_marked_ready: [
    "application marked ready",
    "applications marked ready",
  ],
  application_updated: ["application updated", "applications updated"],
  context_prepared: [
    "frozen copy of your record",
    "frozen copies of your record",
  ],
  document_created: ["document revision", "document revisions"],
  document_reviewed: ["document review", "document reviews"],
  file_uploaded: ["file uploaded", "files uploaded"],
  job_added: ["job added", "jobs added"],
  note_added: ["note", "notes"],
  note_pinned: ["note pinned", "notes pinned"],
  note_unpinned: ["note unpinned", "notes unpinned"],
  question_asked: ["question asked", "questions asked"],
  request_completed: ["request completed", "requests completed"],
  request_declined: ["request declined", "requests declined"],
  request_taken: ["request taken", "requests taken"],
  triage_changed: ["triage decision", "triage decisions"],
  claim_created: ["claim added", "claims added"],
  claim_updated: ["claim edited", "claims edited"],
  knowledge_created: ["Career entry added", "Career entries added"],
  knowledge_updated: ["Career entry edited", "Career entries edited"],
  policy_item_added: ["policy item proposed", "policy items proposed"],
  source_updated: ["source changed", "sources changed"],
  skill_notes_updated: [
    "skill's local notes saved",
    "skills' local notes saved",
  ],
};
/** What `count` changes of one kind are: "document revisions". */
export function countedAs(kind: string, count: number) {
  const words = counted[kind];
  if (words) return words[count === 1 ? 0 : 1];
  return changeLabel(kind).toLowerCase();
}
/** Counts by kind, largest first: [["document_created", 10], …]. */
export function sortedCounts(counts: Record<string, number>) {
  return Object.entries(counts).sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );
}
/** "10 document revisions, 5 applications marked ready, 2 more changes". */
export function countsLine(counts: Record<string, number>, limit = 3) {
  const all = sortedCounts(counts);
  const shown = all
    .slice(0, limit)
    .map(([kind, count]) => `${count} ${countedAs(kind, count)}`);
  const rest = all.slice(limit).reduce((sum, [, count]) => sum + count, 0);
  if (rest) shown.push(`${rest} more ${rest === 1 ? "change" : "changes"}`);
  return shown.join(", ");
}

const changes = (n: number) => `${n} ${n === 1 ? "change" : "changes"}`;

/** One line about what a run did: its summary, or what its changes say. */
export function runLine(run: Run) {
  if (run.status === "interrupted")
    return run.changes_total
      ? `Stopped without a report after ${changes(run.changes_total)}`
      : "Stopped without a report or a change";
  if (run.summary) return run.summary;
  if (run.status === "open")
    return (
      run.note ||
      (run.changes_total
        ? `${countsLine(run.change_counts)} so far`
        : "No change yet")
    );
  return run.changes_total ? countsLine(run.change_counts) : "No change";
}

/** How long a run took, or has taken so far. */
export function runDuration(run: Run, now = new Date()) {
  if (run.status === "open")
    return `${duration(run.started_at, now.toISOString())} so far`;
  if (run.status === "interrupted" && !run.ended_at)
    return `last activity after ${duration(run.started_at, run.last_activity_at)}`;
  return duration(run.started_at, run.ended_at || run.last_activity_at);
}

/** When a run started, how long it took and its scope, on one line. */
export function runWhen(run: Run, now = new Date()) {
  return [
    run.status === "open"
      ? `Started ${lower(dayTime(run.started_at, now))}`
      : dayTime(run.started_at, now),
    runDuration(run, now),
  ]
    .filter(Boolean)
    .join(" · ");
}
const lower = (text: string) =>
  /^(Today|Yesterday)/.test(text)
    ? text[0].toLowerCase() + text.slice(1)
    : text;

/** What the agent last did, for the day nothing waits for the owner. */
export function lastRunLine(run: Run | undefined, now = new Date()) {
  if (!run) return "No agent has worked in this workspace yet.";
  const when = lower(dayTime(run.ended_at || run.last_activity_at, now));
  if (run.status === "open")
    return `Your agent is working on ${run.workflow} now.`;
  return run.status === "finished"
    ? `Your agent last finished ${run.workflow}, ${when}.`
    : `Your agent's last run, ${run.workflow}, stopped without a report, ${when}.`;
}
