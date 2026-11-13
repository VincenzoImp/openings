import { useEffect, useState } from "react";
import type {
  BackgroundTask,
  CollectionRun,
  Job,
  ListResult,
  Source,
} from "../../api";
import {
  EmptyState,
  ErrorBanner,
  Loading,
  SegmentedControl,
} from "../../design";
import { Pager } from "../../library/common";
import { useDebounce, useResource, useUrlFilters } from "../../state";
import { active } from "./model";
import { RunRow } from "./RunRow";
import { TaskRow } from "./TaskRow";

const PAGE = 30;
const STATES: [string, string][] = [
  ["", "All states"],
  ["queued", "Queued or waiting"],
  ["running", "In progress"],
  ["succeeded", "Finished"],
  ["failed", "Failed"],
  ["cancelled", "Stopped"],
];

/**
 * Collection runs with the provider tasks they created, or every task with
 * its own filters. A run in progress is read again every few seconds.
 */
export function Runs() {
  const [filters, setFilters] = useUrlFilters({
    view: "runs",
    state: "",
    source_id: "",
    kind: "",
    job_id: "",
    offset: "0",
  });
  const tasks = filters.view === "tasks";
  const [jobQuery, setJobQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const jobSearch = useDebounce(jobQuery);
  const sources = useResource<ListResult<Source>>(
    "/sources",
    { items: [], total: 0 },
    true,
  );
  const jobs = useResource<ListResult<Job>>(
    tasks ? `/jobs?limit=100&q=${encodeURIComponent(jobSearch)}` : null,
    { items: [], total: 0 },
  );
  const params = new URLSearchParams({
    limit: String(PAGE),
    offset: filters.offset,
  });
  for (const key of [
    "state",
    "source_id",
    ...(tasks ? ["kind", "job_id"] : []),
  ])
    if (filters[key]) params.set(key, filters[key]);
  const list = useResource<ListResult<CollectionRun | BackgroundTask>>(
    `${tasks ? "/tasks" : "/collection/runs"}?${params}`,
    { items: [], total: 0 },
  );
  const running = list.data.items.some((item) => active(item.state));
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(list.reload, 4000);
    return () => clearInterval(timer);
  }, [running]);
  const change = (patch: Record<string, string>) =>
    setFilters({ ...patch, offset: "0" });
  return (
    <section className="card" aria-label="Collection runs and tasks">
      <div className="filters">
        <SegmentedControl
          label="Show"
          value={tasks ? "tasks" : "runs"}
          onChange={(view) => {
            setOpen(null);
            setFilters({
              view,
              offset: "0",
              state: "",
              kind: "",
              job_id: "",
            });
          }}
          options={[
            { id: "runs", label: "Runs" },
            { id: "tasks", label: "All tasks" },
          ]}
        />
        <select
          className="input"
          aria-label="State"
          value={filters.state}
          onChange={(event) => change({ state: event.target.value })}
        >
          {STATES.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
        <select
          className="input"
          aria-label="Source"
          value={filters.source_id}
          onChange={(event) => change({ source_id: event.target.value })}
        >
          <option value="">All sources</option>
          {filters.source_id &&
            !sources.data.items.some((s) => s.id === filters.source_id) && (
              <option value={filters.source_id}>The chosen source</option>
            )}
          {sources.data.items.map((source) => (
            <option key={source.id} value={source.id}>
              {source.name}
            </option>
          ))}
        </select>
        {tasks && (
          <>
            <select
              className="input"
              aria-label="Kind of task"
              value={filters.kind}
              onChange={(event) => change({ kind: event.target.value })}
            >
              <option value="">All kinds</option>
              <option value="collect">Collection</option>
            </select>
            <input
              className="input"
              type="search"
              aria-label="Find a job for its tasks"
              placeholder="Find a job by title or company"
              value={jobQuery}
              onChange={(event) => setJobQuery(event.target.value)}
            />
            <select
              className="input"
              aria-label="Job"
              value={filters.job_id}
              onChange={(event) => change({ job_id: event.target.value })}
            >
              <option value="">All jobs</option>
              {filters.job_id &&
                !jobs.data.items.some((j) => j.id === filters.job_id) && (
                  <option value={filters.job_id}>The chosen job</option>
                )}
              {jobs.data.items.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title} · {job.company}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
      {list.error ? (
        <div className="body">
          <ErrorBanner message={list.error} retry={list.reload} />
        </div>
      ) : list.loading ? (
        <Loading label={tasks ? "Loading tasks…" : "Loading runs…"} />
      ) : list.data.items.length ? (
        <div className="datatable-wrap">
          <table
            className="datatable stack runs"
            aria-label={tasks ? "Collection tasks" : "Collection runs"}
          >
            <thead>
              <tr>
                <th>{tasks ? "Task" : "Run"}</th>
                <th>Result</th>
                <th>Status</th>
                <th>
                  <span className="sr">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {tasks
                ? (list.data.items as BackgroundTask[]).map((task) => (
                    <TaskRow key={task.id} task={task} />
                  ))
                : (list.data.items as CollectionRun[]).map((run) => (
                    <RunRow
                      key={run.id}
                      run={run}
                      open={open === run.id}
                      onToggle={() => setOpen(open === run.id ? null : run.id)}
                    />
                  ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title={tasks ? "No task in this view" : "No run in this view"}
        >
          Runs and their tasks appear here when collection starts: on a
          schedule, with Run once, or when your agent runs a source.
        </EmptyState>
      )}
      <Pager
        offset={Number(filters.offset) || 0}
        total={list.data.total}
        limit={PAGE}
        label={tasks ? "Task pages" : "Run pages"}
        onChange={(offset) => setFilters({ offset: String(offset) })}
      />
      <footer>
        <span className="caption grow">
          Finished runs and tasks are removed after the retention period, except
          the latest of each source. See Settings, Workspace.
        </span>
      </footer>
    </section>
  );
}
