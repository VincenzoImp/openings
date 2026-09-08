import { RefreshCw } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState, ErrorNotice, Spinner } from "../../components/EmptyState";
import { formatDateTime, formatDuration } from "../shared/format";
import { useRuns } from "../shared/queries";

export function RunsView() {
  const runs = useRuns(30);

  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Runs</h1>
          <p className="text-sm text-slate-500">Every collection run, newest first.</p>
        </div>
        <Button size="sm" onClick={() => runs.refetch()} disabled={runs.isFetching}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </header>
      {runs.isPending ? <Spinner /> : null}
      {runs.error ? <ErrorNotice error={runs.error} /> : null}
      {runs.data && runs.data.length === 0 ? (
        <EmptyState title="No runs yet">
          Start the scheduler or run <code>openings run</code> once.
        </EmptyState>
      ) : null}
      <ol className="flex flex-col gap-3">
        {runs.data?.map((run) => (
          <li
            key={run.id ?? run.started_at}
            data-testid="run"
            className="rounded-lg border border-slate-200 bg-white p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge tone={run.success ? "green" : "rose"}>{run.success ? "ok" : "failed"}</Badge>
                <span className="text-sm font-medium">{formatDateTime(run.started_at)}</span>
                <span className="text-xs text-slate-500">
                  {run.finished_at ? formatDuration(run.duration_seconds) : "running"}
                </span>
              </div>
              <dl className="flex flex-wrap gap-4 text-xs text-slate-600">
                <div>
                  <dt className="inline">found </dt>
                  <dd className="inline font-medium tabular-nums">{run.total_found}</dd>
                </div>
                <div>
                  <dt className="inline">unique </dt>
                  <dd className="inline font-medium tabular-nums">{run.unique_found}</dd>
                </div>
                <div>
                  <dt className="inline">saved </dt>
                  <dd className="inline font-medium tabular-nums">{run.saved}</dd>
                </div>
                <div>
                  <dt className="inline">new </dt>
                  <dd className="inline font-medium tabular-nums">{run.new_jobs}</dd>
                </div>
                <div>
                  <dt className="inline">notified </dt>
                  <dd className="inline font-medium tabular-nums">{run.notified}</dd>
                </div>
              </dl>
            </div>
            {run.sources.length ? (
              <table className="mt-2 w-full text-xs">
                <thead className="text-left text-slate-500">
                  <tr>
                    <th className="py-1 pr-2 font-medium">Source</th>
                    <th className="py-1 pr-2 text-right font-medium">Tasks</th>
                    <th className="py-1 pr-2 text-right font-medium">OK</th>
                    <th className="py-1 pr-2 text-right font-medium">Failed</th>
                    <th className="py-1 pr-2 text-right font-medium">Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {run.sources.map((source) => (
                    <tr key={source.name} className="border-t border-slate-100">
                      <td className="py-1 pr-2">{source.name}</td>
                      <td className="py-1 pr-2 text-right tabular-nums">{source.tasks}</td>
                      <td className="py-1 pr-2 text-right tabular-nums">{source.succeeded}</td>
                      <td
                        className={`py-1 pr-2 text-right tabular-nums ${source.failed ? "text-rose-700" : ""}`}
                      >
                        {source.failed}
                      </td>
                      <td className="py-1 pr-2 text-right tabular-nums">{source.rows}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {run.errors.length || run.sources.some((source) => source.errors.length) ? (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-rose-700">
                  {run.errors.length + run.sources.reduce((n, s) => n + s.errors.length, 0)} errors
                </summary>
                <ul className="mt-1 max-h-60 overflow-auto rounded bg-rose-50 p-2 text-[11px] text-rose-900">
                  {[...run.errors, ...run.sources.flatMap((source) => source.errors)].map(
                    (error, index) => (
                      <li key={index}>{error}</li>
                    ),
                  )}
                </ul>
              </details>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
