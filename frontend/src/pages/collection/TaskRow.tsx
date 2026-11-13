import { Fragment, useState } from "react";
import { api, formatTime, type BackgroundTask } from "../../api";
import { Button, ErrorBanner, Loading, Tag, ValueTree } from "../../design";
import { plural } from "../../library/common";
import { dayTime } from "../../library/time";
import { useResource, useWorkspace } from "../../state";
import { active, countsLine, stateTag } from "./model";

/** Stop a queued or running task, or try a failed or stopped one again. */
export function TaskActions({ task }: { task: BackgroundTask }) {
  const { mutate, pending } = useWorkspace();
  if (active(task.state))
    return (
      <Button
        size="sm"
        disabled={pending}
        onClick={() =>
          mutate(() => api(`/tasks/${task.id}/cancel`, "POST"), "Task stopped.")
        }
      >
        Stop task
      </Button>
    );
  if (task.state === "failed" || task.state === "cancelled")
    return (
      <Button
        size="sm"
        disabled={pending}
        onClick={() =>
          mutate(
            () => api(`/tasks/${task.id}/retry`, "POST"),
            "The task is queued again; it resumes where it stopped.",
          )
        }
      >
        Retry
      </Button>
    );
  return null;
}

const provider = (task: BackgroundTask) =>
  String(task.payload?.provider || "Collection");

/** What a task was asked and what it recorded, read when its details open. */
function TaskDetails({ id }: { id: string }) {
  const detail = useResource<BackgroundTask | null>(`/tasks/${id}`, null);
  return (
    <tr className="nested">
      <td colSpan={4} className="full">
        {detail.error ? (
          <ErrorBanner message={detail.error} retry={detail.reload} />
        ) : detail.data ? (
          <ValueTree
            value={{
              asked: detail.data.payload,
              recorded: detail.data.result,
            }}
          />
        ) : (
          <Loading label="Loading the task…" />
        )}
      </td>
    </tr>
  );
}

/**
 * One provider task: what it is collecting, its counts, why it waits or
 * failed and when it tries next. `nested` rows sit under their run; a task of
 * the task list opens its details below it.
 */
export function TaskRow({
  task,
  nested = false,
}: {
  task: BackgroundTask;
  nested?: boolean;
}) {
  const tag = stateTag(task);
  const waiting = task.state === "queued";
  const [open, setOpen] = useState(false);
  return (
    <Fragment>
      <tr className={nested ? "nested" : open ? "is-selected" : undefined}>
        <td className="primary">
          <span className="title">
            {nested
              ? `Task: ${provider(task)}`
              : `${task.source_name || task.job_title || task.kind} · ${provider(task)}`}
          </span>
          <div className="meta">
            {dayTime(task.created_at)}
            {task.attempts ? ` · ${plural(task.attempts, "attempt")}` : ""}
          </div>
        </td>
        <td data-label="Result">
          {countsLine(task.result, task.state)}
          {task.error && (
            <div className={waiting ? "meta" : "meta danger-text"}>
              {task.error}
            </div>
          )}
          {waiting && task.next_run_at && (
            <div className="meta">
              Next attempt {formatTime(task.next_run_at)}
            </div>
          )}
        </td>
        <td>
          <Tag tone={tag.tone}>{tag.text}</Tag>
        </td>
        <td className="actions">
          <TaskActions task={task} />
          {!nested && (
            <Button
              size="sm"
              variant="quiet"
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              {open ? "Hide details" : "Details"}
            </Button>
          )}
        </td>
      </tr>
      {open && <TaskDetails id={task.id} />}
    </Fragment>
  );
}
