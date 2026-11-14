// What Applications and the application page say about an application, in
// words: its stage, its one status phrase, the "Needs action" order, the bulk
// actions valid for a selection, what is missing before Ready, the send queue
// and the history. No React: tests/applications.test.mjs runs it directly.

export type StageKey =
  "shortlisted" | "ready" | "applied" | "interview" | "offer" | "closed";
export type StageFilter = StageKey | "all";

/** The stage chips of the list, in the order of the pipeline. */
export const STAGE_FILTERS: { id: StageFilter; label: string }[] = [
  { id: "shortlisted", label: "Shortlisted" },
  { id: "ready", label: "Ready" },
  { id: "applied", label: "Applied" },
  { id: "interview", label: "Interview" },
  { id: "offer", label: "Offer" },
  { id: "closed", label: "Closed" },
  { id: "all", label: "All" },
];

export const OUTCOMES: Record<string, string> = {
  rejected: "Rejected",
  no_response: "No reply",
  not_pursued: "Not pursued",
  accepted: "Accepted",
};

export type ReplyKind = "interview" | "rejection" | "offer" | "other";
export const REPLY_KINDS: { id: ReplyKind; label: string }[] = [
  { id: "interview", label: "Interview invitation" },
  { id: "rejection", label: "Rejection" },
  { id: "offer", label: "Offer" },
  { id: "other", label: "Other" },
];
const REPLY_WORDS: Record<string, string> = {
  interview: "Interview invitation",
  rejection: "Rejection",
  offer: "Offer",
  other: "Reply",
};

/** The fields of an application these words are made from. */
export interface AppFacts {
  id: string;
  status: string;
  ready: boolean;
  missing?: string[];
  deadline?: string | null;
  priority?: number | null;
  applied_at?: string | null;
  concluded_on?: string | null;
  outcome?: string | null;
  updated_at: string;
  last_reply?: { kind?: unknown; date?: unknown } | null;
  required_documents?: string[];
  requirements?: { id: string; text: string; resolved: boolean }[];
}

/** The stage shown: Ready is a Shortlisted application with nothing missing. */
export function stageOf(app: Pick<AppFacts, "status" | "ready">): StageKey {
  if (app.status === "shortlisted") return app.ready ? "ready" : "shortlisted";
  return (
    ["applied", "interview", "offer", "closed"].includes(app.status)
      ? app.status
      : "shortlisted"
  ) as StageKey;
}

export const isSent = (status: string) =>
  ["applied", "interview", "offer"].includes(status);

const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
const WEEKDAYS = "Sun Mon Tue Wed Thu Fri Sat".split(" ");
const DAY_MS = 86_400_000;

/** A calendar day from "2026-11-12" or a moment; local, at midnight. */
export function dayOf(value: string | Date) {
  if (value instanceof Date)
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, date] = value.split("-").map(Number);
    return new Date(year, month - 1, date);
  }
  return dayOf(new Date(value));
}

/** "2026-11-14": the local calendar day, as the API takes dates. */
export function isoDay(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

/** Whole calendar days from one day to another (negative when earlier). */
export function daysBetween(from: string | Date, to: string | Date) {
  return Math.round((dayOf(to).getTime() - dayOf(from).getTime()) / DAY_MS);
}

/** "12 Oct", with the year only when it is not the current one. */
export function shortDay(value: string | Date, now = new Date()) {
  const day = dayOf(value);
  const text = `${day.getDate()} ${MONTHS[day.getMonth()]}`;
  return day.getFullYear() === now.getFullYear()
    ? text
    : `${text} ${day.getFullYear()}`;
}

const plural = (count: number, word: string) =>
  `${count} ${count === 1 ? word : word + "s"}`;

export type Tone = "warning" | "danger";
export interface Phrase {
  text: string;
  tone?: Tone;
}
/** A phrase, with its tone only when it has one. */
const toned = (text: string, tone?: Tone): Phrase =>
  tone ? { text, tone } : { text };

/**
 * A deadline as a row reads it: "due today", "due Fri" within a week, "due
 * 28 Nov", "overdue 3 days". Warning within three days, danger once passed.
 */
export function deadlinePhrase(
  deadline: string | null | undefined,
  now = new Date(),
): Phrase | null {
  if (!deadline) return null;
  const days = daysBetween(now, deadline);
  if (days < 0)
    return { text: `overdue ${plural(-days, "day")}`, tone: "danger" };
  const text =
    days === 0
      ? "due today"
      : days === 1
        ? "due tomorrow"
        : days < 7
          ? `due ${WEEKDAYS[dayOf(deadline).getDay()]}`
          : `due ${shortDay(deadline, now)}`;
  return toned(text, days <= 3 ? "warning" : undefined);
}

const DOCUMENT_WORDS: Record<string, string> = { cv: "CV", letter: "letter" };

/** "Missing: CV, letter" or "Missing: 1 requirement"; empty when nothing is. */
export function missingPhrase(missing: string[] = []) {
  const documents = missing
    .filter((item) => DOCUMENT_WORDS[item])
    .map((item) => DOCUMENT_WORDS[item]);
  const requirements = missing.filter((item) =>
    item.startsWith("requirement:"),
  ).length;
  const words = [
    ...documents,
    ...(requirements ? [plural(requirements, "requirement")] : []),
  ];
  return words.length ? `Missing: ${words.join(", ")}` : "";
}

const replyDate = (app: AppFacts) =>
  typeof app.last_reply?.date === "string" ? app.last_reply.date : null;

/**
 * The one status phrase of a row, by stage: "Missing: letter", "Ready · due
 * Fri", "Applied 12 Oct · no reply 32 days", "Interview 4 Nov", "Closed ·
 * rejected". A wait longer than the no-reply period is a warning.
 */
export function statusPhrase(
  app: AppFacts,
  noReplyDays: number,
  now = new Date(),
): Phrase {
  const stage = stageOf(app);
  const deadline = deadlinePhrase(app.deadline, now);
  if (stage === "ready")
    return deadline
      ? toned(`Ready · ${deadline.text}`, deadline.tone)
      : { text: "Ready" };
  if (stage === "shortlisted") {
    const missing = missingPhrase(app.missing) || "Shortlisted";
    return deadline
      ? toned(`${missing} · ${deadline.text}`, deadline.tone)
      : { text: missing };
  }
  if (stage === "closed") {
    const outcome = OUTCOMES[app.outcome || ""]?.toLowerCase();
    return { text: outcome ? `Closed · ${outcome}` : "Closed" };
  }
  const reply = replyDate(app);
  if (stage === "interview" || stage === "offer")
    return {
      text: `${stage === "offer" ? "Offer" : "Interview"}${
        reply ? " " + shortDay(reply, now) : ""
      }`,
    };
  if (!app.applied_at) return { text: "Applied" };
  const sent = `Applied ${shortDay(app.applied_at, now)}`;
  if (reply) return { text: `${sent} · replied ${shortDay(reply, now)}` };
  const waited = daysBetween(app.applied_at, now);
  if (waited <= 0) return { text: `${sent} · today` };
  return toned(
    `${sent} · no reply ${plural(waited, "day")}`,
    waited > noReplyDays ? "warning" : undefined,
  );
}

/** Whether a sent application has waited longer than the no-reply period. */
export function overdue(app: AppFacts, noReplyDays: number, now = new Date()) {
  return (
    app.status === "applied" &&
    !app.last_reply &&
    !!app.applied_at &&
    daysBetween(app.applied_at, now) > noReplyDays
  );
}

export type SortKey = "needs" | "deadline" | "updated" | "applied";
export const SORTS: { id: SortKey; label: string }[] = [
  { id: "needs", label: "Needs action" },
  { id: "deadline", label: "Deadline" },
  { id: "updated", label: "Last change" },
  { id: "applied", label: "Applied date" },
];

/**
 * The "Needs action" group: 0 Ready, 1 Shortlisted with a deadline, 2 sent
 * past the no-reply period, 3 everything else.
 */
export function needsRank(
  app: AppFacts,
  noReplyDays: number,
  now = new Date(),
) {
  const stage = stageOf(app);
  if (stage === "ready") return 0;
  if (stage === "shortlisted" && app.deadline) return 1;
  if (overdue(app, noReplyDays, now)) return 2;
  return 3;
}
export const NEEDS_GROUPS = [
  "Ready to send",
  "Shortlisted with a deadline",
  "Waiting too long for a reply",
  "Everything else",
];

const byDeadline = (a: AppFacts, b: AppFacts) =>
  (a.deadline || "9999").localeCompare(b.deadline || "9999") ||
  (a.priority ?? 9) - (b.priority ?? 9);
const byUpdated = (a: AppFacts, b: AppFacts) =>
  b.updated_at.localeCompare(a.updated_at);

/** The rows in the chosen order; "Needs action" groups them by `needsRank`. */
export function sortApplications<T extends AppFacts>(
  items: T[],
  sort: SortKey,
  noReplyDays: number,
  now = new Date(),
): T[] {
  const list = [...items];
  if (sort === "deadline")
    return list.sort((a, b) => byDeadline(a, b) || byUpdated(a, b));
  if (sort === "updated") return list.sort(byUpdated);
  if (sort === "applied")
    return list.sort(
      (a, b) =>
        (b.applied_at || "").localeCompare(a.applied_at || "") ||
        byUpdated(a, b),
    );
  const rank = new Map(
    list.map((app) => [app.id, needsRank(app, noReplyDays, now)]),
  );
  return list.sort((a, b) => {
    const order = rank.get(a.id)! - rank.get(b.id)!;
    if (order) return order;
    if (rank.get(a.id)! <= 1) return byDeadline(a, b) || byUpdated(a, b);
    if (rank.get(a.id) === 2)
      return (a.applied_at || "").localeCompare(b.applied_at || "");
    return byUpdated(a, b);
  });
}

export type BulkAction = "no_reply" | "close" | "reopen" | "priority";
const BULK_VALID: Record<BulkAction, (app: AppFacts) => boolean> = {
  // As the server decides: no_response only for a sent application.
  no_reply: (app) => app.status !== "closed" && !!app.applied_at,
  close: (app) => app.status !== "closed",
  reopen: (app) => app.status === "closed",
  priority: (app) => app.status !== "closed",
};
/** The bulk actions valid for every selected application, in the bar's order. */
export function bulkActions(selected: AppFacts[]): BulkAction[] {
  if (!selected.length) return [];
  return (Object.keys(BULK_VALID) as BulkAction[]).filter((action) =>
    selected.every(BULK_VALID[action]),
  );
}

/** The stage a Closed application reopens to: Applied once it was sent. */
export const reopenStage = (app: Pick<AppFacts, "applied_at">) =>
  app.applied_at ? ("applied" as const) : ("shortlisted" as const);

export interface CheckItem {
  key: string;
  label: string;
  state: "done" | "missing" | "not_needed";
  detail?: string;
}

/**
 * "What's missing": CV and letter (or "not needed"), then the requirements
 * done out of all. Only blocking requirements hold Ready back.
 */
export function checklist(app: AppFacts): CheckItem[] {
  const required = app.required_documents ?? ["cv", "letter"];
  const missing = new Set(app.missing ?? []);
  const items: CheckItem[] = (["cv", "letter"] as const).map((kind) => ({
    key: kind,
    label: kind === "cv" ? "CV" : "Letter",
    state: !required.includes(kind)
      ? "not_needed"
      : missing.has(kind)
        ? "missing"
        : "done",
  }));
  const requirements = app.requirements ?? [];
  if (requirements.length) {
    const done = requirements.filter((item) => item.resolved).length;
    const blocking = [...missing].some((item) =>
      item.startsWith("requirement:"),
    );
    items.push({
      key: "requirements",
      label: "Requirements",
      state: blocking ? "missing" : "done",
      detail: `${done}/${requirements.length} done`,
    });
  }
  return items;
}

/** The first thing missing, which the page's primary action settles. */
export function firstMissing(app: AppFacts) {
  const missing = app.missing ?? [];
  if (missing.includes("cv")) return "cv" as const;
  if (missing.includes("letter")) return "letter" as const;
  const requirement = missing.find((item) => item.startsWith("requirement:"));
  return requirement ? ("requirement" as const) : null;
}

/** What recording a reply of `kind` does to an application in `status`. */
export function replyEffect(
  status: string,
  kind: ReplyKind,
  outcome?: string | null,
) {
  const reopens = status === "closed" && outcome === "no_response";
  if (kind === "interview" && (status === "applied" || reopens))
    return "The application moves to Interview.";
  if (kind === "offer" && (isSent(status) || reopens) && status !== "offer")
    return "The application moves to Offer.";
  if (kind === "rejection" && (isSent(status) || reopens))
    return "A rejection closes the application.";
  return "The stage does not change.";
}

/** The reply an owner most likely records next. */
export const likelyReply = (status: string): ReplyKind =>
  status === "interview" ? "offer" : status === "offer" ? "other" : "interview";

/** Where an application stands in the Ready queue. */
export function queuePlace<T extends { id: string }>(queue: T[], id: string) {
  const index = queue.findIndex((item) => item.id === id);
  if (index < 0) return null;
  return {
    position: index + 1,
    total: queue.length,
    previous: queue[index - 1] ?? null,
    next: queue[index + 1] ?? null,
  };
}

/**
 * The Ready application to open after `id` is marked applied: the next one in
 * the queue, else the first other one; null when it was the last.
 */
export function nextReady<T extends { id: string }>(queue: T[], id: string) {
  const index = queue.findIndex((item) => item.id === id);
  const others = queue.filter((item) => item.id !== id);
  if (!others.length) return null;
  return index < 0 ? others[0] : (queue[index + 1] ?? others[0]);
}

/** The status line at the top of a sent application. */
export function followUpLine(
  app: AppFacts,
  noReplyDays: number,
  now = new Date(),
): Phrase {
  const reply = replyDate(app);
  const kind = String(app.last_reply?.kind ?? "");
  const sent = app.applied_at ? `Applied ${shortDay(app.applied_at, now)}` : "";
  if (app.status === "interview")
    return {
      text: reply
        ? `Interview invitation ${shortDay(reply, now)}`
        : sent || "Interview",
    };
  if (app.status === "offer")
    return { text: reply ? `Offer ${shortDay(reply, now)}` : sent || "Offer" };
  if (reply)
    return {
      text: `${sent ? sent + " · " : ""}${REPLY_WORDS[kind] ?? "Reply"} ${shortDay(reply, now)}`,
    };
  if (!app.applied_at) return { text: "Applied" };
  const waited = daysBetween(app.applied_at, now);
  return waited <= 0
    ? { text: `${sent} · today` }
    : toned(
        `${sent} · no reply for ${plural(waited, "day")}`,
        waited > noReplyDays ? "warning" : undefined,
      );
}

/** "Rejected on 2 Nov after interview", "No reply · closed 12 Nov". */
export function closedSummary(
  app: AppFacts & { replies?: { kind: string; date: string }[] },
  now = new Date(),
) {
  const replies = app.replies ?? [];
  const interviewed = replies.some((reply) => reply.kind === "interview");
  const last = replyDate(app);
  const after = interviewed ? " after interview" : "";
  switch (app.outcome) {
    case "rejected":
      return `Rejected${last ? " on " + shortDay(last, now) : ""}${after}`;
    case "accepted":
      return `Offer accepted${last ? " · offer of " + shortDay(last, now) : ""}`;
    case "no_response":
      return `No reply${
        app.concluded_on ? " · closed " + shortDay(app.concluded_on, now) : ""
      }${
        app.applied_at && app.concluded_on
          ? `, ${plural(daysBetween(app.applied_at, app.concluded_on), "day")} after sending`
          : ""
      }`;
    case "not_pursued":
      return app.applied_at
        ? "Not pursued after sending"
        : "Not pursued · never sent";
    default:
      return "Closed";
  }
}

/** "by you", "by career-agent", "by job sources"; nothing when unknown. */
export function actorPhrase(label?: string | null) {
  if (!label) return "";
  if (label === "owner") return "by you";
  if (label === "system") return "by job sources";
  if (label.startsWith("agent:")) return `by ${label.slice(6) || "an agent"}`;
  return `by ${label}`;
}

const STAGE_WORDS: Record<string, string> = {
  shortlisted: "Shortlisted",
  draft: "Shortlisted",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};

export interface HistoryEntry {
  type: string;
  kind: string;
  event?: { kind?: string; payload?: Record<string, unknown> } | null;
  note?: { body?: unknown } | null;
}

/**
 * One history entry in words, and whether it shows by default (replies,
 * stage changes, notes) or only with "Show all changes".
 */
export function historyLine(
  entry: HistoryEntry,
  reply?: { kind: string; date: string; note?: string } | null,
  now = new Date(),
): { text: string; detail?: string; main: boolean } {
  if (entry.type === "note")
    return { text: "Note", detail: String(entry.note?.body ?? ""), main: true };
  const kind = entry.event?.kind ?? "";
  const payload = entry.event?.payload ?? {};
  const from = String(payload.from ?? ""),
    to = String(payload.to ?? "");
  if (entry.kind === "reply" || kind.startsWith("reply_")) {
    const words = reply
      ? `${REPLY_WORDS[reply.kind] ?? "Reply"} · ${shortDay(reply.date, now)}`
      : "Reply";
    if (kind === "reply_removed") return { text: "Reply removed", main: false };
    if (kind === "reply_edited")
      return { text: `Reply corrected: ${words}`, main: false };
    const moved = to && to !== from ? ` · moved to ${STAGE_WORDS[to]}` : "";
    return { text: `${words}${moved}`, detail: reply?.note || "", main: true };
  }
  if (kind === "application_created")
    return { text: "Application started", main: true };
  if (kind === "application_updated" && to && to !== from) {
    const text =
      to === "applied" && from === "shortlisted"
        ? "Marked applied"
        : from === "applied" && to === "shortlisted"
          ? "Marked applied undone"
          : to === "closed"
            ? "Closed"
            : from === "closed"
              ? `Reopened as ${STAGE_WORDS[to] ?? to}`
              : `Moved to ${STAGE_WORDS[to] ?? to}`;
    return { text, main: true };
  }
  const fields = Array.isArray(payload.fields)
    ? (payload.fields as string[]).map((field) => field.replaceAll("_", " "))
    : [];
  if (kind === "application_updated")
    return {
      text: fields.length ? `Changed ${fields.join(", ")}` : "Changed",
      main: false,
    };
  if (kind === "document_created")
    return { text: "Document revision added", main: false };
  if (kind === "document_deleted")
    return { text: "Document revision removed", main: false };
  const words = kind.replaceAll("_", " ") || "Change";
  return { text: words[0].toUpperCase() + words.slice(1), main: false };
}

/** The current revisions: those no later revision replaces. */
export function currentOf<
  T extends { id: string; kind: string; created_at: string },
>(revisions: (T & { previous_id?: string | null })[], kind: string) {
  const replaced = new Set(revisions.map((item) => item.previous_id));
  return (
    revisions
      .filter((item) => item.kind === kind && !replaced.has(item.id))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null
  );
}
