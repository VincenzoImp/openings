import { Fragment, useEffect } from "react";
import { api, type CollectionRun } from "../../api";
import { Button, ErrorBanner, Loading, Tag, ValueTree } from "../../design";
import { plural } from "../../library/common";
import { dayTime } from "../../library/time";
import { useResource, useWorkspace } from "../../state";
import { active, countsLine, seconds, stateTag, waitReason } from "./model";
import { TaskRow } from "./TaskRow";

/** The tasks of an opened run, its timing and the settings it froze. */
function RunTasks({ id }: { id: string }) {
  const detail = useResource<CollectionRun | null>(
    `/collection/runs/${id}`,
    null,
  );
  const run = detail.data;
  const running = active(run?.state);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(detail.reload, 4000);
    return () => clearInterval(timer);
  }, [running]);
  if (detail.error)
    return (
      <tr className="nested">
        <td colSpan={4}>
          <ErrorBanner message={detail.error} retry={detail.reload} />
        </td>
      </tr>
    );
  if (!run)
    return (
      <tr className="nested">
        <td colSpan={4}>
          <Loading label="Loading the tasks…" />
        </td>
      </tr>
    );
  return (
    <>
      {(run.tasks || []).map((task) => (
        <TaskRow key={task.id} task={task} nested />
      ))}
      <tr className="nested">
        <td colSpan={4} className="full">
          <p className="caption">
            Processing {seconds(run.processing_seconds)} · waiting{" "}
            {seconds(run.waiting_seconds)} · total {seconds(run.total_seconds)}
            {active(run.state) ? " so far" : ""}. Each provider resumes from its
            saved progress; Processed and Already archived count sightings, New
            counts records added to the archive.
          </p>
          <details>
            <summary>Settings this run froze</summary>
            <ValueTree
              value={{
                source: run.source_snapshot,
                "run-only limits": run.overrides,
              }}
            />
          </details>
        </td>
      </tr>
    </>
  );
}

/** One collection run, with its tasks when opened. */
export function RunRow({
  run,
  open,
  onToggle,
}: {
  run: CollectionRun;
  open: boolean;
  onToggle: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const tag = stateTag(run);
  const tasks = run.task_ids?.length || run.tasks?.length || 0;
  return (
    <Fragment>
      <tr className={open ? "is-selected" : undefined}>
        <td className="primary">
          <span className="title">{run.source_name}</span>
          <div className="meta">
            {dayTime(run.started_at || run.created_at)} ·{" "}
            {seconds(run.total_seconds)} · {plural(tasks, "task")}
          </div>
        </td>
        <td data-label="Result">
          {countsLine(run.counts, run.state)}
          {waitReason(run) && <div className="meta">{waitReason(run)}</div>}
        </td>
        <td>
          <Tag tone={tag.tone}>{tag.text}</Tag>
        </td>
        <td className="actions">
          {active(run.state) && (
            <Button
              size="sm"
              disabled={pending}
              onClick={() =>
                mutate(
                  () => api(`/collection/runs/${run.id}/cancel`, "POST"),
                  "The run was stopped. Jobs found so far are kept.",
                )
              }
            >
              Stop run
            </Button>
          )}
          <Button
            size="sm"
            variant="quiet"
            aria-expanded={open}
            onClick={onToggle}
          >
            {open ? "Hide tasks" : "Tasks"}
          </Button>
        </td>
      </tr>
      {open && <RunTasks id={run.id} />}
    </Fragment>
  );
}
