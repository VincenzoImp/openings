import {
  actorLabel,
  api,
  formatTime,
  readinessLabels,
  type Application,
  type Json,
} from "../api";
import { useWorkspace } from "../state";
import { Button, Icon } from "../ui";

/** Why the stored Ready step was cleared, from an application_ready_cleared event. */
const clearedReasons: Record<string, string> = {
  unmarked: "The mark was removed",
  document_created: "A new document revision was saved",
  document_deleted: "A document revision was deleted",
  context_prepared: "A new context was prepared",
  file_uploaded: "A file was added to a current revision",
  blocking_requirement: "A blocking requirement is unresolved",
  left_preparing: "The application left Preparing",
};
export function readyReason(payload?: Json) {
  const reason = payload?.reason;
  return typeof reason === "string"
    ? clearedReasons[reason] || reason.replaceAll("_", " ")
    : "";
}

/** What still has to happen before an application can be marked ready. */
const nextStep: Record<string, string> = {
  blocked: "Resolve the blocking requirements first.",
  none: "Save the CV and cover letter first.",
  missing_pdf: "Attach a PDF to every current CV and cover letter revision.",
  unreviewed: "Approve every current revision.",
  reviewed:
    "Every check passes. Mark it ready when you judge the application complete.",
};

/** The stored Ready step, shown wherever a Preparing application is listed. */
export function ReadyTag({ application }: { application: Application }) {
  if (application.status !== "draft") return null;
  if (application.readiness === "ready")
    return (
      <span className="tag green ready-tag">
        <Icon name="check" />
        Ready to apply
      </span>
    );
  if (application.readiness === "reviewed")
    return <span className="tag neutral ready-tag">Not marked ready</span>;
  return null;
}

/** Mark a Preparing application ready to apply, or clear the mark. */
export function ReadyPanel({ application }: { application: Application }) {
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
    <section
      className={`ready-panel ${ready ? "is-ready" : ""}`}
      aria-label="Ready to apply"
    >
      <div>
        <strong>
          {ready
            ? "Ready to apply"
            : readinessLabels[application.readiness || "none"]}
        </strong>
        <p>
          {ready
            ? `Marked by ${actorLabel(application.ready_by) || "unknown"} · ${formatTime(application.ready_at || undefined)}. A new revision, context or blocking requirement clears it.`
            : nextStep[application.readiness || "none"]}
        </p>
      </div>
      {ready ? (
        <Button className="small" disabled={pending} onClick={() => set(false)}>
          Not ready
        </Button>
      ) : (
        <Button
          variant="primary"
          className="small"
          icon="check"
          disabled={pending || application.readiness !== "reviewed"}
          onClick={() => set(true)}
        >
          Mark ready
        </Button>
      )}
    </section>
  );
}
