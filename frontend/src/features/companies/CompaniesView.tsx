import { useCallback, useMemo } from "react";
import { ExternalLink } from "lucide-react";

import type { JobStatus, JobSummary, SourceStatus } from "../../api/types";
import { setParams, useRoute } from "../../app/router";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { EmptyState, ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Input, Select } from "../../components/Field";
import { Table } from "../../components/Table";
import { useJobActions } from "../shared/actions";
import { formatNumber, relativeDays } from "../shared/format";
import { JobList } from "../shared/JobList";
import { STATUS_LABELS, STATUS_TONE } from "../shared/labels";
import { rememberList } from "../shared/listContext";
import { useCompanyStatuses, useFacets, useJobsInfinite, useSources } from "../shared/queries";
import { useSelection } from "../shared/useSelection";

function health(source: SourceStatus): {
  label: string;
  tone: "positive" | "warning" | "negative" | "muted";
} {
  if (!source.enabled) {
    return { label: "disabled", tone: "muted" };
  }
  const run = source.last_run;
  if (!run) {
    return { label: "never ran", tone: "muted" };
  }
  if (run.failed > 0 && run.succeeded === 0) {
    return { label: "failing", tone: "negative" };
  }
  if (run.failed > 0) {
    return { label: "partial", tone: "warning" };
  }
  return { label: "ok", tone: "positive" };
}

export function CompaniesView() {
  const route = useRoute();
  const actions = useJobActions();
  const filter = route.params.get("q") ?? "";
  const company = route.params.get("company");
  const sources = useSources();
  const facets = useFacets({ limit: 300, q: filter.trim() || undefined });
  const statuses = useCompanyStatuses(company);
  const jobsQuery = useJobsInfinite(
    { company: company ?? undefined, sort: "updated" },
    company !== null,
  );
  const jobs = jobsQuery.items;
  const ids = useMemo(() => jobs.map((job) => job.job_id), [jobs]);
  const selection = useSelection(ids);

  const open = useCallback(
    (job: JobSummary) => {
      rememberList(ids);
      actions.open(job);
    },
    [actions, ids],
  );
  const loadMore = useCallback(() => {
    if (jobsQuery.hasNextPage && !jobsQuery.isFetchingNextPage) {
      void jobsQuery.fetchNextPage();
    }
  }, [jobsQuery]);

  const companies = facets.data?.companies ?? [];
  const companyUrl = jobs.find((job) => job.company_url)?.company_url ?? null;

  return (
    <section className="flex flex-col gap-4">
      <header>
        <h1 className="text-lg font-semibold">Companies</h1>
        <p className="text-sm text-fg-muted">
          Configured sources and every employer with a stored posting.
        </p>
      </header>

      <Card title="Sources" padded={false}>
        {sources.isPending ? (
          <div className="p-3">
            <Skeleton lines={3} />
          </div>
        ) : null}
        {sources.error ? (
          <div className="p-3">
            <ErrorNotice error={sources.error} onRetry={() => sources.refetch()} />
          </div>
        ) : null}
        {sources.data ? (
          <Table
            rows={sources.data}
            rowKey={(source) => `${source.kind}:${source.name}`}
            minWidth={640}
            empty="No sources configured."
            columns={[
              {
                key: "name",
                header: "Name",
                render: (source) => <span className="font-medium">{source.name}</span>,
              },
              {
                key: "kind",
                header: "Source",
                render: (source) => (
                  <span className="inline-flex items-center gap-1">
                    <Badge>{source.kind}</Badge>
                    <span className="hidden text-xs text-fg-muted sm:inline">{source.detail}</span>
                  </span>
                ),
              },
              {
                key: "health",
                header: "Last run",
                render: (source) => {
                  const state = health(source);
                  const run = source.last_run;
                  return (
                    <span className="inline-flex flex-wrap items-center gap-1">
                      <Badge tone={state.tone}>{state.label}</Badge>
                      {run ? (
                        <span className="text-xs text-fg-muted">
                          {run.rows} rows from {run.tasks}{" "}
                          {run.tasks === 1 ? "request" : "requests"}
                          {run.failed ? (
                            <span className="text-negative">, {run.failed} failed</span>
                          ) : null}
                          {run.started_at ? ` · ${relativeDays(run.started_at)}` : ""}
                        </span>
                      ) : null}
                    </span>
                  );
                },
              },
              {
                key: "active",
                header: "Active jobs",
                align: "right",
                render: (source) => formatNumber(source.active_jobs),
              },
            ]}
          />
        ) : null}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card title="Employers" padded={false} className="lg:self-start">
          <div className="border-b border-edge p-2">
            <Input
              aria-label="Filter companies"
              placeholder="Filter companies…"
              autoComplete="off"
              value={filter}
              onChange={(event) => setParams({ q: event.target.value })}
            />
          </div>
          <div className="p-2 lg:hidden">
            <Select
              aria-label="Company"
              value={company ?? ""}
              onChange={(event) => setParams({ company: event.target.value || null })}
            >
              <option value="">Pick a company…</option>
              {companies.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.value} ({entry.count})
                </option>
              ))}
            </Select>
          </div>
          <ul
            className="hidden max-h-[60dvh] overflow-auto lg:block"
            aria-label="Companies"
            tabIndex={0}
          >
            {companies.map((entry) => (
              <li key={entry.value}>
                <button
                  type="button"
                  aria-current={company === entry.value ? "true" : undefined}
                  onClick={() => setParams({ company: entry.value })}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm hover:bg-surface-2 ${
                    company === entry.value ? "bg-accent/10 font-medium" : ""
                  }`}
                >
                  <span className="min-w-0 truncate">{entry.value}</span>
                  <span className="tabular text-xs text-fg-muted">{entry.count}</span>
                </button>
              </li>
            ))}
            {facets.data && companies.length === 0 ? (
              <li className="px-3 py-2 text-sm text-fg-muted">No company matches.</li>
            ) : null}
          </ul>
        </Card>
        <div className="flex min-w-0 flex-col gap-3">
          {company === null ? (
            <EmptyState title="Pick a company">
              Its postings, whatever their status, are listed here.
            </EmptyState>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold">{company}</h2>
                {companyUrl ? (
                  <a
                    href={companyUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                  >
                    site <ExternalLink size={12} aria-hidden="true" />
                  </a>
                ) : null}
                {statuses.data
                  ? Object.entries(statuses.data)
                      .filter(([, count]) => count > 0)
                      .map(([status, count]) => (
                        <Badge key={status} tone={STATUS_TONE[status as JobStatus] ?? "neutral"}>
                          {STATUS_LABELS[status as JobStatus] ?? status} {count}
                        </Badge>
                      ))
                  : null}
              </div>
              {jobsQuery.error ? (
                <ErrorNotice error={jobsQuery.error} onRetry={() => jobsQuery.refetch()} />
              ) : null}
              {jobsQuery.isPending ? (
                <div className="rounded-lg border border-edge bg-surface p-4">
                  <Skeleton lines={4} />
                </div>
              ) : null}
              {!jobsQuery.isPending && jobs.length === 0 ? (
                <EmptyState title="No active postings">
                  Every posting from this company is blacklisted or was deleted.
                </EmptyState>
              ) : null}
              {jobs.length > 0 ? (
                <JobList
                  jobs={jobs}
                  selectedIndex={selection.index}
                  onSelect={selection.setIndex}
                  onOpen={open}
                  onEndReached={loadMore}
                  showStatus
                  selectable={false}
                  className="h-[60dvh]"
                  footer={`${jobs.length} of ${jobsQuery.total}`}
                />
              ) : null}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
