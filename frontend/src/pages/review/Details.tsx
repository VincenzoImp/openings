import { useState, type FormEvent } from "react";
import {
  actorLabel,
  api,
  localToday,
  readinessLabels,
  type Application,
  type Stage,
} from "../../api";
import { Banner, Button, Field } from "../../design";
import { ConfirmDialog } from "../../library/common";
import { dayTime } from "../../library/time";
import { useWorkspace } from "../../state";
import type { Links } from "../activity/records";
import { outcomeLabels, stageLabels } from "../applications/model";
import { AskAgent } from "./AskAgent";

const priorities: Record<number, string> = {
  1: "P1 · highest",
  2: "P2 · high",
  3: "P3 · normal",
  4: "P4 · low",
  5: "P5 · lowest",
};
const nextStep: Record<string, string> = {
  blocked: "Resolve the blocking requirements first.",
  none: "The CV and the letter are not saved yet.",
  missing_pdf: "A current CV or letter has no PDF yet.",
  unreviewed: "A current revision is not approved yet.",
  reviewed: "Every check passes. Mark it ready when you judge it complete.",
};
const SENT: Stage[] = ["applied", "interview", "offer"];

/** True when moving from `before` to `stage` with `outcome` records an employer response. */
function recordsAnswer(app: Application, stage: Stage, outcome: string) {
  const before = app.status;
  if (stage === "interview") return before === "draft" || before === "applied";
  if (stage === "offer")
    return ["draft", "applied", "interview"].includes(before);
  if (stage !== "closed" || (before === "closed" && app.outcome === outcome))
    return false;
  const sent = !!app.applied_at || SENT.includes(before);
  if (outcome === "accepted")
    return sent && !app.responses?.some((item) => item.kind === "offer");
  return outcome === "rejected" && sent;
}

/** The stored Ready step of a Preparing application, and the switch that sets it. */
function Ready({ application }: { application: Application }) {
  const { mutate, pending } = useWorkspace();
  if (application.status !== "draft") return null;
  const ready = application.readiness === "ready";
  const set = (value: boolean) =>
    void mutate(
      () =>
        api(`/applications/${application.id}/ready`, "POST", {
          expected_version: application.version,
          ready: value,
        }),
      value ? "Marked ready to apply." : "No longer marked ready.",
    );
  return (
    <Banner
      tone={ready ? "neutral" : "info"}
      title={
        ready
          ? "Ready to apply"
          : readinessLabels[application.readiness || "none"]
      }
      action={
        ready ? (
          <Button size="sm" disabled={pending} onClick={() => set(false)}>
            Not ready
          </Button>
        ) : (
          <Button
            size="sm"
            variant="primary"
            disabled={pending || application.readiness !== "reviewed"}
            onClick={() => set(true)}
          >
            Mark ready
          </Button>
        )
      }
    >
      {ready
        ? `Marked by ${actorLabel(application.ready_by) || "someone"}, ${dayTime(application.ready_at)}. A new revision, frozen copy or blocking requirement clears it.`
        : nextStep[application.readiness || "none"]}
    </Banner>
  );
}

/**
 * The application's pinned note: its standing guidance, which the agent reads
 * first and new frozen copies of the record include. Saving edits the pinned
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
        hint="Standing guidance for this application: your agent reads it first, and new frozen copies of your record include it. Other notes are in the Timeline."
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
            {actorLabel(pinned.author) || "Unknown"},{" "}
            {dayTime(pinned.updated_at || pinned.created_at)}
          </span>
        )}
      </div>
    </form>
  );
}

/**
 * The application's stage and plan, the Ready step, its pinned note, requests
 * for the agent, the job it belongs to, and its permanent deletion.
 */
export function Details({
  application,
  onDeleted,
  ...links
}: Links & { application: Application; onDeleted: () => void }) {
  const { mutate, pending } = useWorkspace();
  const [stage, setStage] = useState<Stage>(application.status);
  const [outcome, setOutcome] = useState(application.outcome || "not_pursued");
  const [removing, setRemoving] = useState(false);
  const answers = recordsAnswer(application, stage, outcome);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "");
    const applied = text("applied_at");
    await mutate(
      () =>
        api(`/applications/${application.id}`, "PATCH", {
          expected_version: application.version,
          ...(stage !== application.status ? { status: stage } : {}),
          ...(stage === "closed" ? { outcome } : {}),
          ...(stage === "closed" && outcome === "no_response"
            ? { concluded_on: text("concluded_on") || null }
            : {}),
          ...(answers ? { response_date: text("response_date") || null } : {}),
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
          {answers && (
            <Field
              label="Day of the employer's answer"
              hint="The move records the employer's response on this day."
            >
              <input
                type="date"
                name="response_date"
                max={localToday()}
                defaultValue={localToday()}
              />
            </Field>
          )}
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
      <AskAgent
        subjectType="application"
        subjectId={application.id}
        {...links}
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
            The application is removed for good with its frozen copies,
            documents, files, responses and history. The job and its other
            applications stay. To stop and keep everything, close it as Not
            pursued instead.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
