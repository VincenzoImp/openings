import { useEffect, useState } from "react";
import { Play, RefreshCw } from "lucide-react";

import type { RunRecord } from "../../api/types";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState, ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Table } from "../../components/Table";
import { formatDateTime, formatDuration, formatNumber } from "../shared/format";
import { useJobCommands, useRunStatus, useRuns } from "../shared/queries";

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) {
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
}

function elapsed(run: RunRecord, now: number): string {
  if (run.finished_at) {
    return formatDuration(run.duration_seconds);
  }
  const started = new Date(run.started_at).getTime();
  return Number.isNaN(started) ? "running" : `${formatDuration((now - started) / 1000)} so far`;
}

function RunCard({ run, now }: { run: RunRecord; now: number }) {
  const errorsBySource = run.sources.filter((source) => source.errors.length > 0);
  const errorCount =
    run.errors.length + errorsBySource.reduce((sum, source) => sum + source.errors.length, 0);
  return (
    <li data-testid="run">
      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            {run.running ? (
              <Badge tone="info">running</Badge>
            ) : (
              <Badge tone={run.success ? "positive" : "negative"}>
                {run.success ? "ok" : "failed"}
              </Badge>
            )}
            <span className="text-sm font-medium">{formatDateTime(run.started_at)}</span>
            <span className="tabular text-xs text-fg-muted">{elapsed(run, now)}</span>
          </div>
          <dl className="tabular flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
            {(
              [
                ["found", run.total_found],
                ["unique", run.unique_found],
                ["saved", run.saved],
                ["new", run.new_jobs],
                ["notified", run.notified],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="inline">{label} </dt>
                <dd className="inline font-medium text-fg">{formatNumber(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
        {run.sources.length ? (
          <div className="border-t border-edge">
            <Table
              rows={run.sources}
              rowKey={(source) => source.name}
              minWidth={420}
              columns={[
                { key: "source", header: "Source", render: (source) => source.name },
                { key: "tasks", header: "Tasks", align: "right", render: (source) => source.tasks },
                { key: "ok", header: "OK", align: "right", render: (source) => source.succeeded },
                {
                  key: "failed",
                  header: "Failed",
                  align: "right",
                  render: (source) => (
                    <span className={source.failed ? "text-negative" : ""}>{source.failed}</span>
                  ),
                },
                { key: "rows", header: "Rows", align: "right", render: (source) => source.rows },
              ]}
            />
          </div>
        ) : null}
        {errorCount > 0 ? (
          <details className="border-t border-edge px-3 py-2">
            <summary className="cursor-pointer text-xs text-negative">{errorCount} errors</summary>
            <div
              tabIndex={0}
              className="mt-1 max-h-72 overflow-auto rounded bg-negative/8 p-2 text-[11px] text-fg"
            >
              {run.errors.length ? (
                <ul className="mb-2">
                  {run.errors.map((error, index) => (
                    <li key={index} className="break-words">
                      {error}
                    </li>
                  ))}
                </ul>
              ) : null}
              {errorsBySource.map((source) => (
                <div key={source.name} className="mb-2">
                  <div className="font-semibold">{source.name}</div>
                  <ul>
                    {source.errors.map((error, index) => (
                      <li key={index} className="break-words">
                        {error}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </Card>
    </li>
  );
}

export function RunsView() {
  const status = useRunStatus(15_000);
  const active = Boolean(status.data?.running || status.data?.requested);
  const runs = useRuns(30, active ? 15_000 : false);
  const { requestRun } = useJobCommands();
  const now = useNow(active);

  return (
    <section className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold">Runs</h1>
          <p className="text-sm text-fg-muted">
            {status.data?.running && status.data.run
              ? `Running since ${formatDateTime(status.data.run.started_at)}.`
              : status.data?.requested
                ? "Run requested; the scheduler starts within 30 seconds."
                : "Every collection run, newest first."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => runs.refetch()}
            disabled={runs.isFetching}
            aria-label="Refresh"
          >
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={() => requestRun.mutate()}
            disabled={active || requestRun.isPending}
          >
            <Play size={14} aria-hidden="true" /> Run now
          </Button>
        </div>
      </header>
      {runs.isPending ? (
        <div className="rounded-lg border border-edge bg-surface p-4">
          <Skeleton lines={3} />
        </div>
      ) : null}
      {runs.error ? <ErrorNotice error={runs.error} onRetry={() => runs.refetch()} /> : null}
      {runs.data && runs.data.length === 0 ? (
        <EmptyState title="No runs yet">
          Press Run now, or start the scheduler with <code>openings scheduler</code>.
        </EmptyState>
      ) : null}
      <ol className="flex flex-col gap-3">
        {runs.data?.map((run) => (
          <RunCard key={run.id ?? run.started_at} run={run} now={now} />
        ))}
      </ol>
    </section>
  );
}
