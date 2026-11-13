import { useState, type FormEvent } from "react";
import {
  api,
  type Activity,
  type Application,
  type ListResult,
  type Note,
  type ResponseKind,
} from "../../api";
import {
  ActorChip,
  Button,
  ErrorBanner,
  Field,
  IconButton,
  Loading,
} from "../../design";
import type { ActorLike } from "../../design/actor";
import { ConfirmDialog } from "../../library/common";
import { readyReason } from "../../library/ready";
import { dayTime } from "../../library/time";
import { useResource, useWorkspace } from "../../state";
import { changeDetail, changeLabel } from "../activity/wording";
import { responseLabels } from "../applications/model";
import { Responses, day } from "./Responses";

const NONE = { items: [], total: 0 };
type Entry =
  | { kind: "event"; at: string; event: Activity }
  | { kind: "note"; at: string; note: Note & { author?: ActorLike } };

const titles: Record<string, string> = {
  application_created: "Application started",
  application_updated: "Application changed",
  application_marked_ready: "Marked ready",
  application_ready_cleared: "No longer marked ready",
  response_added: "Employer response recorded",
  response_edited: "Employer response corrected",
  response_removed: "Employer response removed",
  note_added: "Note added",
  document_created: "Document revision saved",
  document_reviewed: "Document revision approved",
  context_prepared: "Frozen copy of your record prepared",
};

function detail(event: Activity) {
  const payload = event.payload || {};
  if (event.kind?.startsWith("response_") && payload.kind)
    return `${responseLabels[payload.kind as ResponseKind] || payload.kind}${payload.date ? " · " + day(String(payload.date)) : ""}`;
  if (event.kind === "application_ready_cleared") return readyReason(payload);
  return changeDetail(event);
}

/**
 * Everything recorded about this application, newest first: the employer's
 * responses, then its changes with who made them and the notes written on it.
 */
export function Timeline({
  application,
  reload,
}: {
  application: Application;
  reload: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const events = useResource<ListResult<Activity>>(
    `/applications/${application.id}/events`,
    NONE,
  );
  const notes = useResource<ListResult<Note & { application_id?: string }>>(
    `/jobs/${application.job_id}/notes`,
    NONE,
  );
  const [removing, setRemoving] = useState<Note | null>(null);
  const entries: Entry[] = [
    ...events.data.items.map((event) => ({
      kind: "event" as const,
      at: event.created_at,
      event,
    })),
    ...notes.data.items
      .filter((note) => note.application_id === application.id)
      .map((note) => ({ kind: "note" as const, at: note.created_at, note })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    if (!body) return;
    if (
      await mutate(
        () =>
          api(`/jobs/${application.job_id}/notes`, "POST", {
            body,
            application_id: application.id,
          }),
        "Note added.",
      )
    )
      form.reset();
  }
  return (
    <div className="stack">
      <Responses application={application} reload={reload} />
      <section className="stack" aria-labelledby="history-title">
        <h3 id="history-title">History and notes</h3>
        <form className="stack" onSubmit={add} aria-label="Add a note">
          <Field label="A note on this application">
            <textarea name="body" rows={2} maxLength={30000} required />
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
              <ErrorBanner
                key={index}
                message={part.error}
                retry={part.reload}
              />
            ),
        )}
        {events.loading || notes.loading ? (
          <Loading label="Loading the history…" />
        ) : (
          <ul className="list" aria-label="History and notes">
            {entries.map((entry) =>
              entry.kind === "event" ? (
                <li key={"e" + entry.event.id}>
                  <div className="grow">
                    <div className="title">
                      {titles[entry.event.kind || ""] ||
                        changeLabel(entry.event.kind)}
                    </div>
                    <div className="meta">{detail(entry.event)}</div>
                  </div>
                  <ActorChip actor={entry.event.actor} />
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
                    icon="trash"
                    label="Delete this note"
                    onClick={() => setRemoving(entry.note)}
                  />
                </li>
              ),
            )}
          </ul>
        )}
      </section>
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
    </div>
  );
}
