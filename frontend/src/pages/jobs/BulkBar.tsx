import { useState } from "react";
import { api, type BulkResult } from "../../api";
import { Button } from "../../design";
import { ConfirmDialog, plural } from "../../library/common";
import { useWorkspace } from "../../state";
import { DismissDialog } from "./DismissDialog";
import type { Section } from "./model";

type Action = "shortlisted" | "dismissed" | "new" | "forget";
const LABELS: Record<Section, [Action, string][]> = {
  new: [
    ["shortlisted", "Shortlist"],
    ["dismissed", "Dismiss…"],
  ],
  shortlisted: [
    ["new", "Back to New"],
    ["dismissed", "Dismiss…"],
  ],
  dismissed: [["new", "Restore"]],
  all: [
    ["shortlisted", "Shortlist"],
    ["new", "Back to New"],
    ["dismissed", "Dismiss…"],
  ],
};

/**
 * The actions on the selected jobs: shortlist, dismiss with an optional
 * reason, back to New or restore, and forget for good after asking.
 * Each job is changed on its own; the ones that fail are reported.
 */
export function BulkBar({
  section,
  selection,
  onClear,
  onResult,
}: {
  section: Section;
  /** Selected job ids with the version they were selected at. */
  selection: Record<string, number>;
  onClear: () => void;
  onResult: (result: BulkResult) => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [dialog, setDialog] = useState<"dismissed" | "forget" | null>(null);
  const ids = Object.keys(selection);
  const count = plural(ids.length, "job");
  async function run(action: Action, extra: Record<string, string> = {}) {
    let result: BulkResult | undefined;
    const ok = await mutate(
      async () => {
        result = await api<BulkResult>("/jobs/bulk", "POST", {
          action,
          ...extra,
          items: ids.map((id) => ({ id, expected_version: selection[id] })),
        });
      },
      action === "forget"
        ? "Jobs forgotten."
        : action === "dismissed"
          ? "Jobs dismissed. Each one can be restored."
          : "Jobs updated.",
    );
    if (ok && result) onResult(result);
    setDialog(null);
  }
  return (
    <div className="bulkbar" role="group" aria-label="Selected jobs">
      <strong className="num">{ids.length} selected</strong>
      <span className="grow" />
      {LABELS[section].map(([action, label]) => (
        <Button
          key={action}
          size="sm"
          disabled={pending}
          onClick={() =>
            action === "dismissed" ? setDialog("dismissed") : run(action)
          }
        >
          {label}
        </Button>
      ))}
      <Button
        size="sm"
        variant="danger"
        disabled={pending}
        onClick={() => setDialog("forget")}
      >
        Forget…
      </Button>
      <Button size="sm" variant="quiet" onClick={onClear}>
        Clear
      </Button>
      {dialog === "dismissed" && (
        <DismissDialog
          what={count}
          onClose={() => setDialog(null)}
          onConfirm={(reason) => run("dismissed", reason ? { reason } : {})}
        />
      )}
      {dialog === "forget" && (
        <ConfirmDialog
          title={`Forget ${count}?`}
          confirm={`Forget ${count}`}
          keep="Keep them"
          onClose={() => setDialog(null)}
          onConfirm={() => run("forget")}
        >
          <p>
            Each job is removed for good, with its applications, notes and
            files. A job collected again later is a new job. To stop seeing a
            job and keep its history, dismiss it instead.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
