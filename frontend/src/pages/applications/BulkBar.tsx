import { useState } from "react";
import { api, type BulkResult } from "../../api";
import { Button, Dialog, Field } from "../../design";
import { plural } from "../../library/common";
import { useWorkspace } from "../../state";
import { outcomeLabels, stageLabels, type BulkAction } from "./model";

type Action = "close" | "reopen" | "delete";

/**
 * The actions on the selected applications: close with an outcome (no reply
 * among them), reopen, delete; only those valid for
 * every selected application are offered. Each application is changed on its
 * own; the ones that fail are reported, the rest go through.
 */
export function BulkBar({
  selection,
  actions,
  hint,
  onClear,
  onResult,
}: {
  /** Selected application ids with the version they were selected at. */
  selection: Record<string, number>;
  /** The actions valid for the whole selection (`bulkActions`). */
  actions: BulkAction[];
  hint?: string;
  onClear: () => void;
  onResult: (result: BulkResult) => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [dialog, setDialog] = useState<Action | null>(null);
  const [outcome, setOutcome] = useState("rejected");
  const [stage, setStage] = useState("applied");
  const ids = Object.keys(selection);
  const count = plural(ids.length, "application");
  async function run(action: string, extra: Record<string, string> = {}) {
    let result: BulkResult | undefined;
    const ok = await mutate(
      async () => {
        result = await api<BulkResult>("/applications/bulk", "POST", {
          action,
          ...extra,
          items: ids.map((id) => ({ id, expected_version: selection[id] })),
        });
      },
      action === "delete" ? "Applications deleted." : "Applications updated.",
    );
    if (ok && result) onResult(result);
    setDialog(null);
  }
  return (
    <div className="bulkbar" role="group" aria-label="Selected applications">
      <strong className="num">{ids.length} selected</strong>
      {hint && <span className="muted grow only-desktop">{hint}</span>}
      {actions.includes("no_reply") && (
        <Button
          size="sm"
          disabled={pending}
          onClick={() => run("close", { outcome: "no_response" })}
        >
          Close as no reply
        </Button>
      )}
      {actions.includes("close") && (
        <Button size="sm" disabled={pending} onClick={() => setDialog("close")}>
          Close…
        </Button>
      )}
      {actions.includes("reopen") && (
        <Button
          size="sm"
          disabled={pending}
          onClick={() => setDialog("reopen")}
        >
          Reopen…
        </Button>
      )}
      {actions.includes("delete") && (
        <Button
          size="sm"
          variant="danger"
          disabled={pending}
          onClick={() => setDialog("delete")}
        >
          Delete…
        </Button>
      )}
      <Button size="sm" variant="quiet" onClick={onClear}>
        Clear
      </Button>
      {dialog === "close" && (
        <Dialog
          title={`Close ${count}?`}
          onClose={() => setDialog(null)}
          footer={
            <>
              <Button onClick={() => setDialog(null)}>Keep them open</Button>
              <Button
                variant="primary"
                disabled={pending}
                onClick={() => run("close", { outcome })}
              >
                Close {count}
              </Button>
            </>
          }
        >
          <div className="stack">
            <p>
              Record one outcome for each. Documents and history are kept. A
              rejection is recorded as the employer's answer of today; no reply
              closes only applications that were sent.
            </p>
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
          </div>
        </Dialog>
      )}
      {dialog === "reopen" && (
        <Dialog
          title={`Reopen ${count}?`}
          onClose={() => setDialog(null)}
          footer={
            <>
              <Button onClick={() => setDialog(null)}>Keep them closed</Button>
              <Button
                variant="primary"
                disabled={pending}
                onClick={() => run("reopen", { status: stage })}
              >
                Reopen {count}
              </Button>
            </>
          }
        >
          <div className="stack">
            <p>
              Move the selected Closed applications back to a stage. A job has
              at most one open application.
            </p>
            <Field label="Stage">
              <select
                value={stage}
                onChange={(event) => setStage(event.target.value)}
              >
                {(
                  ["shortlisted", "applied", "interview", "offer"] as const
                ).map((value) => (
                  <option key={value} value={value}>
                    {stageLabels[value]}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Dialog>
      )}
      {dialog === "delete" && (
        <Dialog
          title={`Delete ${count}?`}
          onClose={() => setDialog(null)}
          footer={
            <>
              <Button onClick={() => setDialog(null)}>Keep them</Button>
              <Button
                variant="danger"
                disabled={pending}
                onClick={() => run("delete")}
              >
                Delete {count}
              </Button>
            </>
          }
        >
          <p>
            Each application is removed for good, with its documents, files and
            history. The jobs stay in your workspace. To stop without losing
            anything, close them as Not pursued instead.
          </p>
        </Dialog>
      )}
    </div>
  );
}
