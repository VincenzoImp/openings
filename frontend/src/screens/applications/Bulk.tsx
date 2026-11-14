import { useState } from "react";
import type { Schema } from "../../api/client";
import { useApiMutation } from "../../query/mutation";
import { Button } from "../../ui/Button";
import { Choice } from "../../ui/Choice";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { plural } from "../../ui/format";
import { BulkBar } from "../../ui/List";
import { useToast } from "../../ui/Toast";
import {
  TOUCHES,
  patchApplication,
  useBulk,
  type ApplicationRow,
} from "./data";
import { PrioritySelect, closeOutcomes, errorText } from "./dialogs";
import { OUTCOMES, bulkActions, reopenStage } from "./model";

type Bulk = Schema<"ApplicationBulk">;
type Item = Pick<ApplicationRow, "id" | "version" | "status" | "outcome">;

const groupBy = <T,>(items: T[], key: (item: T) => string) => {
  const groups = new Map<string, T[]>();
  for (const item of items)
    groups.set(key(item), [...(groups.get(key(item)) ?? []), item]);
  return groups;
};

const versionsOf = (result: Schema<"BatchResult">) =>
  new Map(
    result.items
      .filter((item) => item.ok)
      .map((item) => [
        item.id,
        Number((item.result as { version?: number } | null)?.version),
      ]),
  );

/**
 * The bar over selected rows: only the actions valid for the whole
 * selection. Close as no reply, Close… and Reopen are one bulk call per
 * target stage, with Undo; Set priority changes each application.
 */
export function BulkActions({
  selected,
  onClear,
}: {
  selected: ApplicationRow[];
  onClear: () => void;
}) {
  const bulk = useBulk();
  const toast = useToast();
  const [dialog, setDialog] = useState<"close" | "priority" | null>(null);
  const [outcome, setOutcome] = useState("rejected");
  const [priority, setPriority] = useState("");
  const actions = bulkActions(selected);
  const setPriorities = useApiMutation({
    touches: TOUCHES,
    mutationFn: (value: number | null) =>
      Promise.all(
        selected.map((app) =>
          patchApplication(app.id, app.version, { priority: value }),
        ),
      ),
  });

  /** Run bulk calls, one per group, and merge their results. */
  async function run(groups: Bulk[]) {
    const results = [];
    for (const body of groups) results.push(await bulk.mutateAsync(body));
    return results;
  }

  /** Close with an outcome; Undo reopens each to the stage it had. */
  async function close(value: string, items: Item[] = selected) {
    try {
      const [result] = await run([
        {
          action: "close",
          outcome: value as Bulk["outcome"],
          items: items.map((app) => ({
            id: app.id,
            expected_version: app.version,
          })),
        },
      ]);
      onClear();
      const versions = versionsOf(result);
      report(
        result,
        `Closed ${plural(result.succeeded, "application")} as ${OUTCOMES[value].toLowerCase()}`,
        () =>
          reopen(
            items
              .filter((app) => versions.has(app.id))
              .map((app) => ({ ...app, version: versions.get(app.id)! })),
            true,
          ),
      );
    } catch (error) {
      toast.show({ message: errorText(error), tone: "error" });
    }
  }

  /** Reopen to Applied when sent, else Shortlisted (or to `back` stages). */
  async function reopen(items: Item[], undoing = false) {
    try {
      const groups = groupBy(items, (app) =>
        undoing
          ? app.status
          : reopenStage(app as Pick<ApplicationRow, "applied_at">),
      );
      const results = await run(
        [...groups].map(([status, group]) => ({
          action: "reopen",
          status: status as Bulk["status"],
          items: group.map((app) => ({
            id: app.id,
            expected_version: app.version,
          })),
        })),
      );
      onClear();
      const succeeded = results.reduce((sum, item) => sum + item.succeeded, 0);
      if (undoing) {
        toast.show({
          message: `Reopened ${plural(succeeded, "application")}`,
          tone: "success",
        });
        return;
      }
      const versions = new Map(
        results.flatMap((result) => [...versionsOf(result)]),
      );
      const back = groupBy(
        items.filter((app) => versions.has(app.id)),
        (app) => app.outcome || "not_pursued",
      );
      report(
        results[0],
        `Reopened ${plural(succeeded, "application")}`,
        async () => {
          for (const [value, group] of back)
            await close(
              value,
              group.map((app) => ({ ...app, version: versions.get(app.id)! })),
            );
        },
      );
    } catch (error) {
      toast.show({ message: errorText(error), tone: "error" });
    }
  }

  function report(
    result: Schema<"BatchResult">,
    message: string,
    undo: () => void,
  ) {
    if (result.failed)
      toast.show({
        message: `${message}; ${result.failed} could not be changed`,
        tone: "error",
      });
    else
      toast.show({ message, action: { label: "Undo", undo: true, run: undo } });
  }

  const busy = bulk.isPending || setPriorities.isPending;
  return (
    <>
      <BulkBar count={selected.length} onClear={onClear}>
        {actions.includes("no_reply") && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => void close("no_response")}
          >
            Close as no reply
          </Button>
        )}
        {actions.includes("close") && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setOutcome(
                selected.every((app) => app.applied_at)
                  ? "rejected"
                  : "not_pursued",
              );
              setDialog("close");
            }}
          >
            Close…
          </Button>
        )}
        {actions.includes("reopen") && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => void reopen(selected)}
          >
            Reopen
          </Button>
        )}
        {actions.includes("priority") && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setPriority("");
              setDialog("priority");
            }}
          >
            Set priority…
          </Button>
        )}
      </BulkBar>
      <Dialog
        open={dialog === "close"}
        onClose={() => setDialog(null)}
        title={`Close ${selected.length} applications`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => {
                setDialog(null);
                void close(outcome);
              }}
            >
              Close
            </Button>
          </>
        }
      >
        <Choice
          legend="Outcome"
          options={closeOutcomes(selected)}
          value={outcome}
          onChange={setOutcome}
        />
      </Dialog>
      <Dialog
        open={dialog === "priority"}
        onClose={() => setDialog(null)}
        title={`Priority of ${selected.length} applications`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() =>
                setPriorities.mutate(priority ? Number(priority) : null, {
                  onSuccess: () => {
                    setDialog(null);
                    onClear();
                    toast.show({
                      message: `Set the priority of ${plural(selected.length, "application")}`,
                      tone: "success",
                    });
                  },
                  onError: (error) =>
                    toast.show({ message: errorText(error), tone: "error" }),
                })
              }
            >
              Set priority
            </Button>
          </>
        }
      >
        <Field label="Priority">
          <PrioritySelect value={priority} onChange={setPriority} />
        </Field>
      </Dialog>
    </>
  );
}
