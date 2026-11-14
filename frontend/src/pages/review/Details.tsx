import { useState, type FormEvent } from "react";
import {
  api,
  localToday,
  type Application,
  type DocumentKind,
  type Stage,
} from "../../api";
import { Banner, Button, Field, actorPhrase } from "../../design";
import { ConfirmDialog } from "../../library/common";
import { dayTime } from "../../library/time";
import { useWorkspace } from "../../state";
import { missingText, outcomeLabels, stageLabels } from "../applications/model";

const priorities: Record<number, string> = {
  1: "P1 · highest",
  2: "P2 · high",
  3: "P3 · normal",
  4: "P4 · low",
  5: "P5 · lowest",
};
/** Ready, as computed from the required documents and the blocking requirements. */
function Ready({ application }: { application: Application }) {
  if (application.status !== "shortlisted") return null;
  const missing = missingText(application);
  return (
    <Banner
      tone={application.ready ? "neutral" : "info"}
      title={application.ready ? "Ready to apply" : "Not ready yet"}
    >
      {application.ready
        ? "Every required document is uploaded and no blocking requirement is open. Send it, then mark it applied."
        : `${missing}. Ready follows by itself once each required document has its PDF and every blocking requirement is resolved.`}
    </Banner>
  );
}

/**
 * The application's pinned note: its standing guidance, which the agent reads
 * first. Saving edits the pinned
 * note or pins a new one; unpinning keeps the note in the timeline.
 */
function PinnedNote({ application }: { application: Application }) {
  const { mutate, pending } = useWorkspace();
  const pinned = application.pinned_note;
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = String(new FormData(event.currentTarget).get("body") || "");
    if (!body.trim() || body === pinned?.body) return;
    await mutate(
      () =>
        pinned
          ? api(`/notes/${pinned.id}`, "PATCH", {
              body,
              expected_version: pinned.version,
            })
          : api(`/jobs/${application.job_id}/notes`, "POST", {
              body,
              application_id: application.id,
              pinned: true,
            }),
      "Pinned note saved.",
    );
  }
  return (
    <form className="stack" onSubmit={save} aria-label="Pinned note">
      <Field
        label="Pinned note"
        hint="Standing guidance for this application: your agent reads it first. Other notes are in the Timeline."
      >
        <textarea
          name="body"
          rows={5}
          maxLength={30000}
          required
          defaultValue={pinned?.body || ""}
        />
      </Field>
      <div className="row">
        <Button size="sm" disabled={pending}>
          {pinned ? "Save the pinned note" : "Pin this note"}
        </Button>
        {pinned && (
          <Button
            size="sm"
            variant="quiet"
            disabled={pending}
            onClick={() =>
              void mutate(
                () =>
                  api(`/notes/${pinned.id}/pin`, "POST", {
                    expected_version: pinned.version,
                    pinned: false,
                  }),
                "Note unpinned. It stays in the Timeline.",
              )
            }
          >
            Unpin
          </Button>
        )}
        {pinned && (
          <span className="caption">
            {[
              dayTime(pinned.updated_at || pinned.created_at),
              actorPhrase(pinned.author),
            ]
              .filter(Boolean)
              .join(" ")}
          </span>
        )}
      </div>
    </form>
  );
}

/**
 * The application's stage and plan, whether it is Ready, its pinned note, the job
 * it belongs to, and its permanent deletion.
 */
export function Details({
  application,
  onDeleted,
}: {
  application: Application;
  onDeleted: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [stage, setStage] = useState<Stage>(application.status);
  const [outcome, setOutcome] = useState(application.outcome || "not_pursued");
  const [removing, setRemoving] = useState(false);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "");
    const applied = text("applied_at");
    const required = (["cv", "letter"] as DocumentKind[]).filter((kind) =>
      form.get(`required_${kind}`),
    );
    await mutate(
      () =>
        api(`/applications/${application.id}`, "PATCH", {
          expected_version: application.version,
          ...(stage !== application.status ? { status: stage } : {}),
          ...(stage === "closed" ? { outcome } : {}),
          ...(stage === "closed" && outcome === "no_response"
            ? { concluded_on: text("concluded_on") || null }
            : {}),
          required_documents: required,
          priority: Number(text("priority")) || null,
          deadline: text("deadline") || null,
          // The field shows minutes; an unchanged one keeps the stored time.
          ...(applied !== (application.applied_at?.slice(0, 16) || "")
            ? {
                applied_at: applied
                  ? new Date(applied + "Z").toISOString()
                  : null,
              }
            : {}),
        }),
      "Details saved.",
    );
  }
  return (
    <div className="stack">
      <Ready application={application} />
      <form className="stack" onSubmit={save} aria-label="Stage and plan">
        <div className="form-grid">
          <Field label="Stage">
            <select
              value={stage}
              onChange={(event) => setStage(event.target.value as Stage)}
            >
              {Object.entries(stageLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          {stage === "closed" && (
            <Field label="Outcome">
              <select
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
              >
                {Object.entries(outcomeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {stage === "closed" && outcome === "no_response" && (
            <Field label="Concluded on">
              <input
                type="date"
                name="concluded_on"
                max={localToday()}
                defaultValue={application.concluded_on || localToday()}
              />
            </Field>
          )}
          <fieldset className="field">
            <legend>Required documents</legend>
            <div className="row">
              {(["cv", "letter"] as DocumentKind[]).map((kind) => (
                <label key={kind} className="toggle">
                  <input
                    type="checkbox"
                    name={`required_${kind}`}
                    defaultChecked={(
                      application.required_documents || ["cv", "letter"]
                    ).includes(kind)}
                  />
                  {kind === "cv" ? "CV" : "Letter"}
                </label>
              ))}
            </div>
            <p className="caption">
              Ready needs each required document as a PDF.
            </p>
          </fieldset>
          <Field label="Priority" hint="Orders the preparation work.">
            <select
              name="priority"
              defaultValue={String(application.priority ?? "")}
            >
              <option value="">Not set</option>
              {Object.entries(priorities).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Deadline" hint="The employer's closing date, if known.">
            <input
              type="date"
              name="deadline"
              defaultValue={application.deadline || ""}
            />
          </Field>
          <Field
            label="Sent at (UTC)"
            hint="Moving to a sent stage records the current time when this is empty."
          >
            <input
              type="datetime-local"
              name="applied_at"
              defaultValue={application.applied_at?.slice(0, 16) || ""}
            />
          </Field>
        </div>
        <div className="row">
          <Button variant="primary" size="sm" disabled={pending}>
            Save details
          </Button>
        </div>
      </form>
      <PinnedNote
        key={`${application.pinned_note?.id}-${application.pinned_note?.version}`}
        application={application}
      />
      <section className="stack" aria-labelledby="job-title">
        <h3 id="job-title">The job</h3>
        <p className="muted">
          Its posting, notes, files and every application to it are on the job.
        </p>
        <div className="row">
          <a className="btn sm" href={`#jobs?job=${application.job_id}`}>
            Open the job
          </a>
          <Button
            size="sm"
            variant="quiet danger"
            onClick={() => setRemoving(true)}
          >
            Delete this application
          </Button>
        </div>
      </section>
      {removing && (
        <ConfirmDialog
          title="Delete this application?"
          confirm="Delete the application"
          keep="Keep the application"
          onClose={() => setRemoving(false)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/applications/${application.id}?expected_version=${application.version}`,
                    "DELETE",
                  ),
                "Application deleted.",
              )
            ) {
              setRemoving(false);
              onDeleted();
            }
          }}
        >
          <p>
            The application is removed for good with its documents, files,
            replies and history. The job and its other applications stay. To
            stop and keep everything, close it as Not pursued instead.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
