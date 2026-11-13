import { useState, type FormEvent } from "react";
import {
  api,
  type Activity,
  type Job,
  type ListResult,
  type Note,
} from "../../api";
import {
  ActorChip,
  Button,
  Dialog,
  ErrorBanner,
  Field,
  IconButton,
  Loading,
} from "../../design";
import type { ActorLike } from "../../design/actor";
import { ConfirmDialog } from "../../library/common";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { changeDetail, changeLabel } from "../activity/wording";

type JobNote = Note & { author?: ActorLike; application_id?: string | null };
type Entry =
  | { kind: "event"; at: string; event: Activity }
  | { kind: "note"; at: string; note: JobNote };
const NONE = { items: [], total: 0 };
const TITLES: Record<string, string> = {
  job_added: "Collected",
  job_refreshed: "Posting refreshed by its source",
  job_edited: "Details edited",
  jobs_merged: "Merged with another record",
  duplicate_cleared: "Marked as a different vacancy",
  application_created: "Application started",
  application_updated: "Application changed",
  application_deleted: "Application deleted",
};
// Notes are listed themselves.
const HIDDEN = new Set(["note_added", "note_edited", "note_deleted"]);

function title(event: Activity) {
  if (event.kind === "triage_changed") {
    const to = event.payload?.to;
    const rule = event.payload?.rule ? " by a policy rule" : "";
    return to === "dismissed"
      ? `Dismissed${rule}`
      : to === "saved"
        ? "Shortlisted"
        : event.payload?.from === "dismissed"
          ? "Restored"
          : "Returned to review";
  }
  return TITLES[event.kind || ""] || changeLabel(event.kind);
}

/** Everything recorded about the job, newest first, with its notes and a form to add one. */
export function JobTimeline({ job }: { job: Job }) {
  const { mutate, pending } = useWorkspace();
  const events = useFresh<ListResult<Activity>>(
    `/events?job_id=${encodeURIComponent(job.id)}&limit=100`,
    NONE,
    ["jobs", "applications", "notes"],
  );
  const notes = useFresh<ListResult<JobNote>>(
    `/jobs/${encodeURIComponent(job.id)}/notes`,
    NONE,
    ["jobs", "notes"],
  );
  const [removing, setRemoving] = useState<JobNote | null>(null);
  const [editing, setEditing] = useState<JobNote | null>(null);
  const entries: Entry[] = [
    ...events.data.items
      .filter((event) => !HIDDEN.has(event.kind || ""))
      .map((event) => ({
        kind: "event" as const,
        at: event.created_at,
        event,
      })),
    ...notes.data.items.map((note) => ({
      kind: "note" as const,
      at: note.created_at,
      note,
    })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    if (!body) return;
    if (
      await mutate(
        () => api(`/jobs/${job.id}/notes`, "POST", { body }),
        "Note added.",
      )
    )
      form.reset();
  }
  async function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const body = String(new FormData(event.currentTarget).get("body") || "");
    if (
      await mutate(
        () =>
          api(`/notes/${editing.id}`, "PATCH", {
            body,
            expected_version: editing.version,
          }),
        "Note saved.",
      )
    )
      setEditing(null);
  }
  return (
    <section className="detail-section" aria-labelledby="timeline-title">
      <h3 id="timeline-title">Timeline</h3>
      <form className="stack" onSubmit={add} aria-label="Add a note">
        <Field
          label="A note on this job"
          hint="Only you and your agent read it."
        >
          <textarea
            id="job-note"
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
      {[events, notes].map(
        (part, index) =>
          part.error && (
            <ErrorBanner key={index} message={part.error} retry={part.reload} />
          ),
      )}
      {events.loading || notes.loading ? (
        <Loading label="Loading the timeline…" />
      ) : (
        <ul className="list compact" aria-label="Timeline of this job">
          {entries.map((entry) =>
            entry.kind === "event" ? (
              <li key={"e" + entry.event.id}>
                <div className="grow">
                  <div className="title">{title(entry.event)}</div>
                  {entry.event.kind !== "triage_changed" &&
                    changeDetail(entry.event) && (
                      <div className="meta">{changeDetail(entry.event)}</div>
                    )}
                </div>
                <ActorChip
                  actor={entry.event.actor}
                  detail={entry.event.run_workflow || undefined}
                />
                <span className="caption num">{dayTime(entry.at)}</span>
              </li>
            ) : (
              <li key={"n" + entry.note.id}>
                <div className="grow">
                  <div className="title">Note</div>
                  <div className="meta prose">{entry.note.body}</div>
                </div>
                <ActorChip actor={entry.note.author} />
                <span className="caption num">{dayTime(entry.at)}</span>
                <IconButton
                  icon="edit"
                  label="Edit this note"
                  onClick={() =>
                    api<JobNote>(`/notes/${entry.note.id}`).then(
                      setEditing,
                      () => setEditing(entry.note),
                    )
                  }
                />
                <IconButton
                  icon="trash"
                  label="Delete this note"
                  onClick={() => setRemoving(entry.note)}
                />
              </li>
            ),
          )}
        </ul>
      )}
      {editing && (
        <Dialog title="Edit the note" onClose={() => setEditing(null)}>
          <form className="stack" onSubmit={edit}>
            <Field label="Note">
              <textarea
                name="body"
                rows={6}
                required
                defaultValue={editing.body}
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
      {removing && (
        <ConfirmDialog
          title="Delete this note?"
          confirm="Delete the note"
          keep="Keep the note"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () => api(`/notes/${removing.id}`, "DELETE"),
                "Note deleted.",
              )
            )
              setRemoving(null);
          }}
        >
          <p className="prose">{removing.body}</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
