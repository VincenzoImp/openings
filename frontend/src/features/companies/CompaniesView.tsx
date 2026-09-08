import { useMemo, useState } from "react";

import type { JobSummary } from "../../api/types";
import { navigate } from "../../app/router";
import { Badge } from "../../components/Badge";
import { ErrorNotice, Spinner } from "../../components/EmptyState";
import { Input } from "../../components/Field";
import { JobList } from "../shared/JobList";
import { useFacets, useJobs, useSources } from "../shared/queries";
import { useSelection } from "../shared/useSelection";

export function CompaniesView() {
  const sources = useSources();
  const facets = useFacets();
  const [filter, setFilter] = useState("");
  const [company, setCompany] = useState<string | null>(null);

  const companies = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return (facets.data?.companies ?? []).filter((entry) =>
      needle ? entry.value.toLowerCase().includes(needle) : true,
    );
  }, [facets.data, filter]);

  const jobsQuery = useJobs(
    { company: company ?? undefined, limit: 200, sort: "updated" },
    company !== null,
  );
  const jobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data]);
  const selection = useSelection(jobs.length);
  const open = (job: JobSummary) => navigate({ jobId: job.job_id });

  return (
    <section className="flex flex-col gap-4">
      <header>
        <h1 className="text-lg font-semibold">Companies</h1>
        <p className="text-sm text-slate-500">
          Configured sources and every employer with a stored posting.
        </p>
      </header>

      <div className="rounded-lg border border-slate-200 bg-white">
        <h2 className="border-b border-slate-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Sources
        </h2>
        {sources.isPending ? (
          <div className="p-3">
            <Spinner />
          </div>
        ) : null}
        {sources.error ? (
          <div className="p-3">
            <ErrorNotice error={sources.error} />
          </div>
        ) : null}
        {sources.data ? (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Kind</th>
                <th className="px-3 py-2 font-medium">Detail</th>
                <th className="px-3 py-2 text-right font-medium">Active jobs</th>
              </tr>
            </thead>
            <tbody>
              {sources.data.map((source) => (
                <tr key={`${source.kind}:${source.name}`} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">
                    {source.name}
                    {!source.enabled ? (
                      <Badge className="ml-2" tone="amber">
                        disabled
                      </Badge>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    <Badge>{source.kind}</Badge>
                  </td>
                  <td className="px-3 py-2 text-slate-600">{source.detail}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{source.active_jobs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-200 p-2">
            <Input
              aria-label="Filter companies"
              placeholder="Filter companies…"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          <ul className="max-h-[60vh] overflow-auto">
            {companies.map((entry) => (
              <li key={entry.value}>
                <button
                  type="button"
                  onClick={() => setCompany(entry.value)}
                  className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-slate-50 ${
                    company === entry.value ? "bg-sky-50 font-medium" : ""
                  }`}
                >
                  <span className="truncate">{entry.value}</span>
                  <span className="text-xs tabular-nums text-slate-500">{entry.count}</span>
                </button>
              </li>
            ))}
            {facets.data && companies.length === 0 ? (
              <li className="px-3 py-2 text-sm text-slate-500">No company matches.</li>
            ) : null}
          </ul>
        </div>
        <div>
          {company === null ? (
            <p className="text-sm text-slate-500">Pick a company to see its postings.</p>
          ) : null}
          {jobsQuery.isFetching && jobs.length === 0 ? <Spinner /> : null}
          {jobsQuery.error ? <ErrorNotice error={jobsQuery.error} /> : null}
          {company !== null && jobs.length > 0 ? (
            <JobList
              jobs={jobs}
              selectedIndex={selection.index}
              onSelect={selection.setIndex}
              onOpen={open}
              showStatus
              height="60vh"
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}
