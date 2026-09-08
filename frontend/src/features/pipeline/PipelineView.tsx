import { useMemo, useState } from "react";
import type { DragEvent } from "react";

import { PIPELINE_STATUSES } from "../../api/types";
import type { JobStatus, JobSummary } from "../../api/types";
import { useHotkeys } from "../../app/hotkeys";
import { navigate } from "../../app/router";
import { Badge, STATUS_TONE } from "../../components/Badge";
import { ConfirmDialog } from "../../components/Dialog";
import { ErrorNotice, Spinner } from "../../components/EmptyState";
import { ScoreBar } from "../../components/ScoreBar";
import { STATUS_LABELS, relativeDays } from "../shared/format";
import { useJobCommands, useJobs } from "../shared/queries";

const COLUMN_TONE: Record<JobStatus, string> = {
  new: "border-slate-300",
  shortlisted: "border-sky-300",
  applied: "border-violet-300",
  interviewing: "border-amber-300",
  offer: "border-emerald-300",
  rejected: "border-rose-300",
  withdrawn: "border-slate-400",
};

export function PipelineView() {
  const query = useJobs({ status: PIPELINE_STATUSES, limit: 1000, sort: "updated" });
  const commands = useJobCommands();
  const [column, setColumn] = useState(0);
  const [row, setRow] = useState(0);
  const [blacklistFor, setBlacklistFor] = useState<JobSummary | null>(null);

  const columns = useMemo(() => {
    const grouped = new Map<JobStatus, JobSummary[]>(
      PIPELINE_STATUSES.map((status) => [status, []]),
    );
    for (const job of query.data?.items ?? []) {
      grouped.get(job.status)?.push(job);
    }
    return PIPELINE_STATUSES.map((status) => ({ status, jobs: grouped.get(status) ?? [] }));
  }, [query.data]);

  const currentColumn = columns[column];
  const currentRow = Math.min(row, Math.max(0, currentColumn.jobs.length - 1));
  const selected = currentColumn.jobs[currentRow];

  const move = (job: JobSummary, status: JobStatus) => {
    if (job.status !== status) {
      commands.setStatus.mutate({ jobIds: [job.job_id], status });
    }
  };

  const shift = (direction: 1 | -1) => {
    if (!selected) {
      return;
    }
    const target = PIPELINE_STATUSES[column + direction];
    if (target) {
      move(selected, target);
      setColumn(column + direction);
    }
  };

  useHotkeys({
    j: () => setRow(Math.min(currentRow + 1, Math.max(0, currentColumn.jobs.length - 1))),
    ArrowDown: () => setRow(Math.min(currentRow + 1, Math.max(0, currentColumn.jobs.length - 1))),
    k: () => setRow(Math.max(0, currentRow - 1)),
    ArrowUp: () => setRow(Math.max(0, currentRow - 1)),
    ArrowRight: () => setColumn(Math.min(columns.length - 1, column + 1)),
    ArrowLeft: () => setColumn(Math.max(0, column - 1)),
    "]": () => shift(1),
    "[": () => shift(-1),
    Enter: () => selected && navigate({ jobId: selected.job_id }),
    o: () => selected?.job_url && window.open(selected.job_url, "_blank", "noopener"),
    s: () => selected && move(selected, "shortlisted"),
    a: () => selected && move(selected, "applied"),
    x: () => selected && setBlacklistFor(selected),
  });

  const onDrop = (status: JobStatus) => (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const jobId = event.dataTransfer.getData("text/plain");
    const job = query.data?.items.find((item) => item.job_id === jobId);
    if (job) {
      move(job, status);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-center gap-2">
        <h1 className="text-lg font-semibold">Pipeline</h1>
        <span className="text-sm text-slate-500">
          {query.data ? `${query.data.total} in progress` : ""}
        </span>
      </header>
      {query.isPending ? <Spinner /> : null}
      {query.error ? <ErrorNotice error={query.error} /> : null}
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {columns.map((entry, columnIndex) => (
          <div
            key={entry.status}
            data-testid={`column-${entry.status}`}
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDrop(entry.status)}
            className={`flex min-h-40 flex-col gap-2 rounded-lg border-t-4 bg-slate-100/70 p-2 ${COLUMN_TONE[entry.status]} ${
              columnIndex === column ? "ring-1 ring-slate-400" : ""
            }`}
          >
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {STATUS_LABELS[entry.status]}
              </span>
              <Badge tone={STATUS_TONE[entry.status]}>{entry.jobs.length}</Badge>
            </div>
            {entry.jobs.map((job, rowIndex) => {
              const isSelected = columnIndex === column && rowIndex === currentRow;
              return (
                <div
                  key={job.job_id}
                  role="button"
                  tabIndex={0}
                  draggable
                  aria-selected={isSelected}
                  data-testid="pipeline-card"
                  onDragStart={(event) => event.dataTransfer.setData("text/plain", job.job_id)}
                  onClick={() => {
                    setColumn(columnIndex);
                    setRow(rowIndex);
                    navigate({ jobId: job.job_id });
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      navigate({ jobId: job.job_id });
                    }
                  }}
                  className={`cursor-pointer rounded-md border bg-white p-2 text-left shadow-sm ${
                    isSelected ? "border-sky-400 ring-1 ring-sky-300" : "border-slate-200"
                  }`}
                >
                  <div className="truncate text-sm font-medium text-slate-900">{job.title}</div>
                  <div className="truncate text-xs text-slate-600">
                    {job.company}
                    {job.location ? ` · ${job.location}` : ""}
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <ScoreBar score={job.relevance_score} />
                    <span className="text-[11px] text-slate-500">
                      {relativeDays(job.status_changed_at ?? job.last_seen)}
                    </span>
                  </div>
                  {job.labels.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {job.labels.map((label) => (
                        <Badge key={label} tone="violet">
                          {label}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={blacklistFor !== null}
        title="Blacklist this posting?"
        message={
          blacklistFor ? (
            <>
              <strong>{blacklistFor.title}</strong> at {blacklistFor.company} will be deleted
              together with its notes and attachments.
            </>
          ) : null
        }
        confirmLabel="Blacklist"
        danger
        onConfirm={() => blacklistFor && commands.blacklist.mutate([blacklistFor.job_id])}
        onClose={() => setBlacklistFor(null)}
      />
    </section>
  );
}
