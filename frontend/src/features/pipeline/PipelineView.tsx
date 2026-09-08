import { useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";
import { MoreHorizontal } from "lucide-react";

import { PIPELINE_STATUSES } from "../../api/types";
import type { JobStatus, JobSummary } from "../../api/types";
import { useHotkeys } from "../../app/hotkeys";
import { setParams, useRoute } from "../../app/router";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState, ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Checkbox, Input } from "../../components/Field";
import { Menu } from "../../components/Menu";
import { ScoreBar } from "../../components/ScoreBar";
import { useJobActions } from "../shared/actions";
import { STATUS_LABELS, STATUS_TONE } from "../shared/labels";
import { relativeDays } from "../shared/format";
import { rememberList } from "../shared/listContext";
import { useJobsInfinite } from "../shared/queries";
import { StatusNoteDialog } from "../shared/StatusNoteDialog";

const CLOSED: JobStatus[] = ["rejected", "withdrawn"];

const COLUMN_ACCENT: Record<JobStatus, string> = {
  new: "border-t-edge-strong",
  shortlisted: "border-t-info",
  applied: "border-t-accent",
  interviewing: "border-t-warning",
  offer: "border-t-positive",
  rejected: "border-t-negative",
  withdrawn: "border-t-fg-faint",
  blacklisted: "border-t-fg-faint",
};

export function PipelineView() {
  const route = useRoute();
  const actions = useJobActions();
  const showClosed = route.params.get("closed") === "1";
  const filter = (route.params.get("q") ?? "").trim().toLowerCase();
  const statuses = showClosed
    ? PIPELINE_STATUSES
    : PIPELINE_STATUSES.filter((status) => !CLOSED.includes(status));

  const query = useJobsInfinite({ statuses, sort: "updated" });
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const [column, setColumn] = useState(0);
  const [row, setRow] = useState(0);
  const [statusFor, setStatusFor] = useState<JobSummary | null>(null);

  const columns = useMemo(() => {
    const grouped = new Map<JobStatus, JobSummary[]>(statuses.map((status) => [status, []]));
    for (const job of query.items) {
      if (filter && !`${job.title} ${job.company} ${job.location}`.toLowerCase().includes(filter)) {
        continue;
      }
      grouped.get(job.status)?.push(job);
    }
    return statuses.map((status) => ({ status, jobs: grouped.get(status) ?? [] }));
  }, [query.items, statuses, filter]);

  const safeColumn = Math.min(column, Math.max(0, columns.length - 1));
  const currentColumn = columns[safeColumn];
  const currentRow = Math.min(row, Math.max(0, (currentColumn?.jobs.length ?? 1) - 1));
  const selected = currentColumn?.jobs[currentRow];

  const move = (job: JobSummary, status: JobStatus) => {
    if (job.status !== status) {
      actions.setStatus.mutate({ jobIds: [job.job_id], status });
    }
  };
  const shift = (direction: 1 | -1) => {
    if (!selected) {
      return;
    }
    const target = statuses[safeColumn + direction];
    if (target) {
      move(selected, target);
      setColumn(safeColumn + direction);
    }
  };
  const open = (job: JobSummary) => {
    rememberList(currentColumn?.jobs.map((item) => item.job_id) ?? []);
    actions.open(job);
  };

  useHotkeys("view", [
    {
      key: "j",
      run: () =>
        setRow(Math.min(currentRow + 1, Math.max(0, (currentColumn?.jobs.length ?? 1) - 1))),
      description: "Next / previous card",
      group: "Pipeline",
      label: "j / k",
    },
    { key: "k", run: () => setRow(Math.max(0, currentRow - 1)) },
    {
      key: "ArrowDown",
      run: () =>
        setRow(Math.min(currentRow + 1, Math.max(0, (currentColumn?.jobs.length ?? 1) - 1))),
    },
    { key: "ArrowUp", run: () => setRow(Math.max(0, currentRow - 1)) },
    {
      key: "ArrowRight",
      run: () => setColumn(Math.min(columns.length - 1, safeColumn + 1)),
      description: "Previous / next column",
      group: "Pipeline",
      label: "← / →",
    },
    { key: "ArrowLeft", run: () => setColumn(Math.max(0, safeColumn - 1)) },
    {
      key: "]",
      run: () => shift(1),
      description: "Move the card one status forward / back",
      group: "Pipeline",
      label: "] / [",
    },
    { key: "[", run: () => shift(-1) },
    { key: "Enter", run: () => selected && open(selected) },
    { key: "o", run: () => selected && actions.openPosting(selected) },
    { key: "s", run: () => selected && move(selected, "shortlisted") },
    { key: "a", run: () => selected && move(selected, "applied") },
    { key: "S", run: () => selected && setStatusFor(selected) },
    { key: "x", run: () => selected && void actions.blacklist([selected]) },
  ]);

  const onDrop = (status: JobStatus) => (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const jobId = event.dataTransfer.getData("text/plain");
    const job = query.items.find((item) => item.job_id === jobId);
    if (job) {
      move(job, status);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">Pipeline</h1>
        <span className="tabular text-sm text-fg-muted">
          {query.isPending ? "" : `${query.total} in progress`}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Input
            aria-label="Filter cards"
            placeholder="Filter…"
            className="!w-40"
            autoComplete="off"
            value={route.params.get("q") ?? ""}
            onChange={(event) => setParams({ q: event.target.value })}
          />
          <Checkbox
            label="Show closed"
            checked={showClosed}
            onChange={(event) => setParams({ closed: event.target.checked ? "1" : null })}
          />
        </div>
      </header>
      {query.error ? <ErrorNotice error={query.error} onRetry={() => query.refetch()} /> : null}
      {query.isPending ? (
        <div className="rounded-lg border border-edge bg-surface p-4">
          <Skeleton lines={5} />
        </div>
      ) : null}
      {!query.isPending && query.total === 0 ? (
        <EmptyState title="Nothing in progress">
          Shortlist a posting from the Inbox and it appears here.
        </EmptyState>
      ) : null}
      {query.total > 0 ? (
        <div
          className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0 xl:grid xl:snap-none xl:overflow-visible"
          tabIndex={0}
          style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}
        >
          {columns.map((entry, columnIndex) => (
            <div
              key={entry.status}
              data-testid={`column-${entry.status}`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={onDrop(entry.status)}
              className={`flex w-[82vw] min-w-[260px] shrink-0 snap-start flex-col gap-2 rounded-lg border border-edge border-t-4 bg-surface-2/50 p-2 sm:w-72 xl:w-auto ${COLUMN_ACCENT[entry.status]} ${
                columnIndex === safeColumn ? "ring-1 ring-accent/40" : ""
              }`}
            >
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
                  {STATUS_LABELS[entry.status]}
                </span>
                <Badge tone={STATUS_TONE[entry.status]}>{entry.jobs.length}</Badge>
              </div>
              {entry.jobs.length === 0 ? (
                <p className="px-1 py-3 text-center text-xs text-fg-faint">Empty</p>
              ) : null}
              <div
                role="list"
                aria-label={STATUS_LABELS[entry.status]}
                className="flex flex-col gap-2"
              >
                {entry.jobs.map((job, rowIndex) => {
                  const isSelected = columnIndex === safeColumn && rowIndex === currentRow;
                  return (
                    <div
                      key={job.job_id}
                      role="listitem"
                      aria-current={isSelected ? "true" : undefined}
                      tabIndex={0}
                      draggable
                      data-testid="pipeline-card"
                      onDragStart={(event) => event.dataTransfer.setData("text/plain", job.job_id)}
                      onClick={() => {
                        setColumn(columnIndex);
                        setRow(rowIndex);
                      }}
                      onDoubleClick={() => open(job)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          open(job);
                        }
                      }}
                      className={`rounded-md border bg-surface p-2 text-left shadow-sm ${
                        isSelected ? "border-accent ring-1 ring-accent/40" : "border-edge"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-1">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            open(job);
                          }}
                          className="min-w-0 truncate text-left text-sm font-medium text-fg hover:underline"
                        >
                          {job.title}
                        </button>
                        <Menu
                          trigger={({ toggle }) => (
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label="Card actions"
                              onClick={(event) => {
                                event.stopPropagation();
                                toggle();
                              }}
                            >
                              <MoreHorizontal size={14} aria-hidden="true" />
                            </Button>
                          )}
                          items={[
                            ...PIPELINE_STATUSES.filter((status) => status !== job.status).map(
                              (status) => ({
                                label: `Move to ${STATUS_LABELS[status]}`,
                                onSelect: () => move(job, status),
                              }),
                            ),
                            {
                              label: "Change status with a note…",
                              onSelect: () => setStatusFor(job),
                            },
                            {
                              label: "Open posting",
                              onSelect: () => actions.openPosting(job),
                              disabled: !job.job_url,
                            },
                            {
                              label: "Blacklist…",
                              onSelect: () => void actions.blacklist([job]),
                              danger: true,
                            },
                          ]}
                        />
                      </div>
                      <div className="truncate text-xs text-fg-muted">
                        {job.company}
                        {job.location ? ` · ${job.location}` : ""}
                      </div>
                      <div className="mt-1 flex items-center justify-between gap-2">
                        <ScoreBar score={job.relevance_score} />
                        <span className="text-[11px] text-fg-faint">
                          {relativeDays(job.status_changed_at ?? job.last_seen)}
                        </span>
                      </div>
                      {job.labels.length || job.attachments_count ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {job.labels.map((label) => (
                            <Badge key={label} tone="accent">
                              {label}
                            </Badge>
                          ))}
                          {job.attachments_count ? (
                            <Badge tone="positive">{job.attachments_count} files</Badge>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <StatusNoteDialog
        open={statusFor !== null}
        jobIds={statusFor ? [statusFor.job_id] : []}
        initialStatus={statusFor?.status ?? "shortlisted"}
        onClose={() => setStatusFor(null)}
      />
    </section>
  );
}
