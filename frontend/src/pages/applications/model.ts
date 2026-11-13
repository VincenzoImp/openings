// What the Applications screen shows about an application, in words: its
// stage, plan, documents and the employer's answer. No React: tested directly.
import type { Application, ResponseKind, Stage } from "../../api";
import { daysAgo, deadlineTag, shortDate } from "../../library/time.ts";

export type StageKey =
  "all" | "preparing" | "ready" | "applied" | "interview" | "offer" | "closed";
export const STAGES: { id: StageKey; label: string }[] = [
  { id: "all", label: "All" },
  { id: "preparing", label: "Preparing" },
  { id: "ready", label: "Ready" },
  { id: "applied", label: "Applied" },
  { id: "interview", label: "Interview" },
  { id: "offer", label: "Offer" },
  { id: "closed", label: "Closed" },
];
export const stageLabels: Record<Stage, string> = {
  draft: "Preparing",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};
export const outcomeLabels: Record<string, string> = {
  accepted: "Accepted",
  rejected: "Rejected",
  not_pursued: "Not pursued",
  no_response: "No reply",
};
export const responseLabels: Record<ResponseKind, string> = {
  interview: "Interview",
  rejection: "Rejection",
  offer: "Offer",
  other: "Other answer",
};
export type Tone = "ready" | "attention" | "danger" | "info" | "agent";
export interface Label {
  text: string;
  tone?: Tone;
}

/** The stage chip an application belongs to: Ready is a stage inside Preparing. */
export function stageOf(app: Pick<Application, "status" | "ready_at">) {
  if (app.status === "draft") return app.ready_at ? "ready" : "preparing";
  return app.status as StageKey;
}
export function stageTag(app: Application): Label {
  const stage = stageOf(app);
  const text = STAGES.find((item) => item.id === stage)!.label;
  if (stage === "ready") return { text, tone: "ready" };
  if (["applied", "interview", "offer"].includes(stage))
    return { text, tone: "info" };
  return { text };
}

/** The filters of the address (the shell maps the old page's names to them). */
export const DEFAULTS = {
  stage: "all",
  q: "",
  outcome: "",
  readiness: "",
  sort: "updated",
  applied_since: "",
  applied_until: "",
  waiting: "",
  view: "list",
  offset: "0",
};
export type Filters = typeof DEFAULTS;

/** The list request of a set of filters. */
export function listQuery(filters: Filters, limit: number, offset = 0) {
  const query = new URLSearchParams();
  const stage = filters.stage as StageKey;
  if (stage === "preparing" || stage === "ready") {
    query.set("status", "draft");
    query.set("ready", String(stage === "ready"));
  } else if (stage !== "all") query.set("status", stage);
  for (const key of [
    "q",
    "outcome",
    "readiness",
    "applied_since",
    "applied_until",
  ] as const)
    if (filters[key]) query.set(key, filters[key]);
  if (filters.waiting) query.set("no_reply_due", "true");
  query.set("sort", filters.sort || "updated");
  query.set("limit", String(limit));
  if (offset) query.set("offset", String(offset));
  return query;
}

/** Counts of the stage chips: every stage, for the current search. */
export function stageCounts(result: {
  total: number;
  stage_counts?: Record<string, number>;
  ready_count?: number;
}): Record<StageKey, number> {
  const counts = result.stage_counts || {};
  const ready = result.ready_count || 0;
  return {
    all: result.total,
    preparing: (counts.draft || 0) - ready,
    ready,
    applied: counts.applied || 0,
    interview: counts.interview || 0,
    offer: counts.offer || 0,
    closed: counts.closed || 0,
  };
}

/** Priority, deadline and a blocking requirement, for an application being prepared. */
export function planTags(app: Application, now = new Date()): Label[] {
  const tags: Label[] = [];
  if (app.priority != null)
    tags.push({
      text: `P${app.priority}`,
      tone: app.priority <= 1 ? "attention" : undefined,
    });
  if (app.status === "draft") {
    const deadline = deadlineTag(app.deadline, now);
    if (deadline)
      tags.push({
        text: deadline.text,
        tone: deadline.tone === "neutral" ? undefined : deadline.tone,
      });
    if (app.blocking_requirements)
      tags.push({
        text:
          app.blocking_requirements === 1
            ? "Blocking requirement"
            : `${app.blocking_requirements} blocking requirements`,
        tone: "danger",
      });
  }
  return tags;
}

const KINDS: Record<string, string> = { resume: "CV", cover_letter: "letter" };
/** The state of the CV and letter, from the current revisions. */
export function documentState(app: Application): Label[] {
  const items = (app.preparation || []).filter((item) => KINDS[item.kind]);
  const lines: Label[] = [];
  if (!items.length)
    lines.push({
      text: (app.preparation || []).length ? "Other documents" : "None",
    });
  else {
    const approved = items.filter(
      (item) => item.revisions && item.approved === item.revisions,
    );
    const missing = items.filter((item) => item.pdf < item.revisions);
    if (approved.length === items.length)
      lines.push({
        text:
          items.length === 2
            ? "CV and letter approved"
            : `${capital(KINDS[items[0].kind])} approved`,
      });
    else if (!approved.length)
      lines.push({
        text: missing.length ? "Written, without PDF" : "Written, not approved",
      });
    else
      lines.push({
        text: `${capital(KINDS[approved[0].kind])} approved, ${
          KINDS[items.find((item) => !approved.includes(item))!.kind]
        } not yet`,
      });
  }
  if (app.status === "draft" && app.stale_inputs?.length)
    lines.push({ text: "Inputs changed", tone: "attention" });
  return lines;
}
const capital = (text: string) => text[0].toUpperCase() + text.slice(1);

const day = (value: string) => {
  const [year, month, date] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, date);
};
/** Whole days from one calendar day to another. */
export const daysBetween = (from: string, to: string) =>
  Math.max(
    0,
    Math.round((day(to).valueOf() - day(from).valueOf()) / 86_400_000),
  );
const dayText = (value: string, now: Date) => shortDate(day(value), now);

/** When it was sent, for the Plan column of a sent application. */
export function sentLine(app: Application, now = new Date()) {
  if (app.status === "draft") return "";
  if (!app.applied_at) return app.status === "closed" ? "Never sent" : "";
  return `Sent ${dayText(app.applied_at, now)}`;
}

/**
 * What the employer answered, or how long the wait is. `days` is the
 * no-reply period: a longer wait is shown as needing attention.
 */
export function responseLine(
  app: Application,
  days: number,
  now = new Date(),
): Label & { quiet?: boolean; badge?: boolean } {
  const last = app.last_response;
  const after =
    last && app.applied_at
      ? `, after ${daysBetween(app.applied_at, last.date)} days`
      : "";
  if (app.status === "draft") return { text: "" };
  if (app.status === "closed") {
    if (app.outcome === "no_response") {
      const closed = app.concluded_on || app.updated_at || "";
      const waited =
        app.applied_at && closed
          ? ` after ${daysBetween(app.applied_at, closed)} days`
          : "";
      return { text: `No reply · closed ${dayText(closed, now)}${waited}` };
    }
    if (app.outcome === "not_pursued")
      return {
        text: app.applied_at
          ? "Not pursued"
          : "Not pursued · not counted in Insights",
        quiet: true,
      };
    if (last)
      return {
        text: `${responseLabels[last.kind]} · ${dayText(last.date, now)}${after}`,
      };
    return { text: outcomeLabels[app.outcome || ""] || "Closed", quiet: true };
  }
  if (last)
    return {
      text: `${responseLabels[last.kind]} · ${dayText(last.date, now)}`,
    };
  if (!app.applied_at) return { text: "No reply yet" };
  const waited = daysAgo(new Date(app.applied_at), now);
  if (waited <= 0) return { text: "Sent today" };
  return {
    text: `No reply for ${waited} ${waited === 1 ? "day" : "days"}`,
    tone: app.status === "applied" && waited > days ? "attention" : undefined,
    badge: true,
  };
}

/** True when the owner records an employer response from this row. */
export const awaitsAnswer = (app: Application) =>
  ["applied", "interview", "offer"].includes(app.status);
