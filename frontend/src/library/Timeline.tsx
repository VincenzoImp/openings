import { useState, type FormEvent } from "react";
import {
  api,
  type Activity,
  type ReplyKind,
  type TimelineItem,
  type TimelineKind,
  type TimelinePage,
} from "../api";
import {
  ActorChip,
  Button,
  Chips,
  Dialog,
  EmptyState,
  ErrorBanner,
  Field,
  FilterBar,
  IconButton,
  Loading,
  Tag,
} from "../design";
import { changeDetail, changeLabel } from "../pages/activity/wording";
import { useWorkspace } from "../state";
import { ConfirmDialog, Pager } from "./common";
import { readyReason } from "./ready";
import { dayTime } from "./time";
import { useFresh } from "./useFresh";

const PAGE = 30;
// Filters appear once a timeline has more entries than this.
const FILTERS_FROM = 5;
const NONE: TimelinePage = {
  scope: { type: "job", id: "", job_id: "" },
  items: [],
  total: 0,
  counts: { note: 0, event: 0, reply: 0 },
  limit: PAGE,
  offset: 0,
};
// A note, a pin or an employer reply changes what the timeline shows.
const SCOPES = [
  "jobs",
  "applications",
  "notes",
  "documents",
  "files",
  "questions",
  "requests",
];
const TITLES: Record<string, string> = {
  job_added: "Collected",
  job_refreshed: "Posting refreshed by its source",
  job_edited: "Details edited",
  jobs_merged: "Merged with another record",
  duplicate_cleared: "Marked as a different vacancy",
  application_created: "Application started",
  application_updated: "Application changed",
  application_deleted: "Application deleted",
  application_marked_ready: "Marked ready",
  application_ready_cleared: "No longer marked ready",
  application_ready_mark_archived: "Was marked ready (before 0.24)",
  reply_added: "Employer reply recorded",
  reply_edited: "Employer reply corrected",
  reply_removed: "Employer reply removed",
  response_added: "Employer reply recorded",
  response_edited: "Employer reply corrected",
  response_removed: "Employer reply removed",
  note_deleted: "Note deleted",
  note_pinned: "Note pinned",
  note_unpinned: "Note unpinned",
  document_created: "Document revision saved",
  document_reviewed: "Document revision approved",
};
const REPLIES: Record<ReplyKind, string> = {
  rejection: "Rejection",
  interview: "Interview invitation",
  offer: "Offer",
  other: "Other reply",
};

type Event = NonNullable<TimelineItem["event"]>;
const asActivity = (event: Event, at: string): Activity => ({
  kind: event.kind,
  payload: event.payload,
  created_at: at,
});

/** What a change is called on a timeline. */
export function eventTitle(event: Event) {
  if (event.kind === "triage_changed") {
    const to = event.payload?.to;
    return to === "dismissed"
      ? "Dismissed"
      : to === "shortlisted" || to === "saved"
        ? "Shortlisted"
        : event.payload?.from === "dismissed"
          ? "Restored"
          : "Back to New";
  }
  return TITLES[event.kind] || changeLabel(event.kind);
}

/** The line under a change: the reply and its day, the reason, the fields. */
export function eventDetail(event: Event, at: string) {
  const payload = event.payload || {};
  if (/^(reply|response)_/.test(event.kind) && payload.kind) {
    const kind = REPLIES[payload.kind as ReplyKind] || String(payload.kind);
    const day = payload.date
      ? " · " +
        new Date(String(payload.date) + "T12:00:00").toLocaleDateString(
          "en-GB",
          { day: "numeric", month: "short", year: "numeric" },
        )
      : "";
    return kind + day;
  }
  if (event.kind === "application_ready_cleared") return readyReason(payload);
  if (event.kind === "triage_changed") return "";
  return changeDetail(asActivity(event, at));
}

const KIND_FILTERS: { id: string; label: string; kinds: TimelineKind[] }[] = [
  { id: "", label: "Everything", kinds: [] },
  { id: "note", label: "Notes", kinds: ["note"] },
  { id: "event", label: "Changes", kinds: ["event"] },
  { id: "reply", label: "Replies", kinds: ["reply"] },
];

interface Filters {
  kind: string;
  who: string;
  scope: string;
  since: string;
  until: string;
}
const CLEAR: Filters = { kind: "", who: "", scope: "", since: "", until: "" };

/**
 * The timeline of a job or of an application: notes and recorded changes in
 * one list, the pinned note first. An application's timeline also shows its
 * job's entries, each marked with its scope. Notes are added, pinned, edited
 * and deleted here.
 */
export function RecordTimeline({
  jobId,
  applicationId,
  label,
}: {
  jobId: string;
  /** Show this application's timeline instead of the job's. */
  applicationId?: string;
  /** The accessible name of the list. */
  label: string;
}) {
  const { mutate, pending } = useWorkspace();
  const [filters, setFilters] = useState<Filters>(CLEAR);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<TimelineItem | null>(null);
  const [removing, setRemoving] = useState<TimelineItem | null>(null);
  const set = (patch: Partial<Filters>) => {
    setFilters({ ...filters, ...patch });
    setOffset(0);
  };
  const query = new URLSearchParams({
    limit: String(PAGE),
    offset: String(offset),
  });
  for (const kind of KIND_FILTERS.find((item) => item.id === filters.kind)
    ?.kinds || [])
    query.append("kinds", kind);
  if (filters.who) query.append("who", filters.who);
  if (filters.scope) query.set("scope", filters.scope);
  if (filters.since) query.set("since", filters.since);
  if (filters.until) query.set("until", filters.until);
  const page = useFresh<TimelinePage>(
    applicationId
      ? `/applications/${encodeURIComponent(applicationId)}/timeline?${query}`
      : `/jobs/${encodeURIComponent(jobId)}/timeline?${query}`,
    NONE,
    SCOPES,
  );
  const filtered = Object.values(filters).some(Boolean);
  const counts = page.data.counts;
  const all = counts.note + counts.event + counts.reply;
  const where = applicationId ? "application" : "job";

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    if (!body) return;
    if (
      await mutate(
        () =>
          api(`/jobs/${encodeURIComponent(jobId)}/notes`, "POST", {
            body,
            ...(applicationId ? { application_id: applicationId } : {}),
          }),
        "Note added.",
      )
    )
      form.reset();
  }
  async function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing?.note) return;
    const body = String(new FormData(event.currentTarget).get("body") || "");
    if (
      await mutate(
        () =>
          api(`/notes/${editing.id}`, "PATCH", {
            body,
            expected_version: editing.note?.version,
          }),
        "Note saved.",
      )
    )
      setEditing(null);
  }
  const pin = (item: TimelineItem) =>
    void mutate(
      () =>
        api(`/notes/${item.id}/pin`, "POST", {
          expected_version: item.note?.version,
          pinned: !item.note?.pinned,
        }),
      item.note?.pinned ? "Note unpinned." : "Note pinned.",
    );
  // Read the note again before editing, so the dialog starts from its last version.
  const open = (item: TimelineItem) =>
    api<{ body: string; version: number }>(`/notes/${item.id}`).then(
      (note) =>
        setEditing({
          ...item,
          note: item.note && {
            ...item.note,
            body: note.body,
            version: note.version,
          },
        }),
      () => setEditing(item),
    );

  return (
    <div className="stack">
      <form className="stack" onSubmit={add} aria-label="Add a note">
        <Field
          label={`A note on this ${where}`}
          hint="Only you and your agent read it."
        >
          <textarea
            id={`${where}-note`}
            name="body"
            rows={2}
            maxLength={30000}
            required
          />
        </Field>
        <div className="row">
          <Button size="sm" disabled={pending}>
            Add the note
          </Button>
        </div>
      </form>
      {(filtered || all > FILTERS_FROM) && (
        <FilterBar label="Timeline filters">
          <Chips
            label="Show"
            value={filters.kind}
            onChange={(kind) => set({ kind })}
            options={KIND_FILTERS.map((item) => ({
              id: item.id,
              label: item.label,
              count: item.id ? counts[item.id as TimelineKind] : all,
            }))}
          />
          <select
            className="input"
            aria-label="Made by"
            value={filters.who}
            onChange={(event) => set({ who: event.target.value })}
          >
            <option value="">By anyone</option>
            <option value="owner">By you</option>
            <option value="agent">By an agent</option>
            <option value="system">By the system</option>
            <option value="unknown">Not recorded</option>
          </select>
          {applicationId && (
            <select
              className="input"
              aria-label="Scope"
              value={filters.scope}
              onChange={(event) => set({ scope: event.target.value })}
            >
              <option value="">Application and job</option>
              <option value="application">This application</option>
              <option value="job">The job</option>
            </select>
          )}
          <label className="toggle">
            <span className="muted">From</span>
            <input
              className="input"
              type="date"
              aria-label="From"
              value={filters.since}
              max={filters.until || undefined}
              onChange={(event) => set({ since: event.target.value })}
            />
          </label>
          <label className="toggle">
            <span className="muted">To</span>
            <input
              className="input"
              type="date"
              aria-label="To"
              value={filters.until}
              min={filters.since || undefined}
              onChange={(event) => set({ until: event.target.value })}
            />
          </label>
        </FilterBar>
      )}
      {page.error && <ErrorBanner message={page.error} retry={page.reload} />}
      {page.loading ? (
        <Loading label="Loading the timeline…" />
      ) : page.data.items.length ? (
        <ul className="list compact" aria-label={label}>
          {page.data.items.map((item) => (
            <Entry
              key={item.type + item.id}
              item={item}
              applicationId={applicationId}
              onPin={pin}
              onEdit={open}
              onRemove={setRemoving}
            />
          ))}
        </ul>
      ) : (
        <EmptyState
          title={filtered ? "Nothing matches these filters" : "Nothing yet"}
          action={
            filtered && (
              <Button onClick={() => set(CLEAR)}>Clear filters</Button>
            )
          }
        >
          {filtered
            ? "Try another kind, person or period."
            : "Notes and changes appear here with who made them."}
        </EmptyState>
      )}
      <Pager
        offset={offset}
        total={page.data.total}
        limit={PAGE}
        onChange={setOffset}
        label="Timeline pages"
      />
      {editing?.note && (
        <Dialog title="Edit the note" onClose={() => setEditing(null)}>
          <form className="stack" onSubmit={edit}>
            <Field label="Note">
              <textarea
                name="body"
                rows={6}
                required
                maxLength={30000}
                defaultValue={editing.note.body}
              />
            </Field>
            <div className="row">
              <Button variant="primary" disabled={pending}>
                Save the note
              </Button>
            </div>
          </form>
        </Dialog>
      )}
      {removing?.note && (
        <ConfirmDialog
          title="Delete this note?"
          confirm="Delete the note"
          keep="Keep the note"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/notes/${removing.id}?expected_version=${removing.note?.version}`,
                    "DELETE",
                  ),
                "Note deleted.",
              )
            )
              setRemoving(null);
          }}
        >
          <p className="prose">{removing.note.body}</p>
        </ConfirmDialog>
      )}
    </div>
  );
}

/** One note or change, with its scope, who made it and when. */
function Entry({
  item,
  applicationId,
  onPin,
  onEdit,
  onRemove,
}: {
  item: TimelineItem;
  applicationId?: string;
  onPin: (item: TimelineItem) => void;
  onEdit: (item: TimelineItem) => void;
  onRemove: (item: TimelineItem) => void;
}) {
  // On a job's timeline the application entries are marked; on an
  // application's, the job's.
  const marked = applicationId
    ? item.scope.type === "job"
    : item.scope.type === "application";
  // Under the text: the reply and scope tags, who made it and when, so a
  // narrow pane keeps the text wide.
  const line = (
    <div className="row entry-line">
      {item.kind === "reply" && <Tag tone="info">Reply</Tag>}
      {marked && <Tag>{item.scope.type === "job" ? "Job" : "Application"}</Tag>}
      <ActorChip actor={item.actor} detail={item.run?.workflow || undefined} />
      <span className="caption num">{dayTime(item.created_at)}</span>
    </div>
  );
  if (item.note) {
    const note = item.note;
    return (
      <li className={note.pinned ? "is-pinned" : undefined}>
        <div className="grow">
          <div className="title">{note.pinned ? "Pinned note" : "Note"}</div>
          <div className="meta prose">{note.body}</div>
          {line}
        </div>
        <span className="row">
          <IconButton
            icon={note.pinned ? "unpin" : "pin"}
            label={note.pinned ? "Unpin this note" : "Pin this note"}
            onClick={() => onPin(item)}
          />
          <IconButton
            icon="edit"
            label="Edit this note"
            onClick={() => onEdit(item)}
          />
          <IconButton
            icon="trash"
            label="Delete this note"
            onClick={() => onRemove(item)}
          />
        </span>
      </li>
    );
  }
  const event = item.event as Event;
  const detail = eventDetail(event, item.created_at);
  return (
    <li>
      <div className="grow">
        <div className="title">{eventTitle(event)}</div>
        {detail && <div className="meta">{detail}</div>}
        {line}
      </div>
    </li>
  );
}
