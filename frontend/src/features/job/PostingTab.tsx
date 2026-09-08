import type { JobDetail } from "../../api/types";
import { Badge } from "../../components/Badge";
import { MarkdownBody } from "../../components/MarkdownBody";
import { formatDate, formatDateTime, formatSalary } from "../shared/format";

function Meta({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) {
    return null;
  }
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-800">{value}</dd>
    </div>
  );
}

export function PostingTab({ job }: { job: JobDetail }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        {job.description ? (
          <MarkdownBody text={job.description} />
        ) : (
          <p className="text-sm text-slate-500">
            No description stored. Open the posting for the full text.
          </p>
        )}
        {job.raw_json ? (
          <details className="mt-4">
            <summary className="cursor-pointer text-xs text-slate-500">Raw source payload</summary>
            <pre className="mt-2 max-h-80 overflow-auto rounded bg-slate-50 p-2 text-[11px]">
              {job.raw_json}
            </pre>
          </details>
        ) : null}
      </div>
      <aside className="flex flex-col gap-4">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Score breakdown
          </h2>
          {job.explain.matched.length === 0 ? (
            <p className="text-sm text-slate-500">No scoring category matched.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {job.explain.matched.map((item) => (
                <li key={item.category} className="flex items-center justify-between text-sm">
                  <span>{item.category}</span>
                  <Badge tone={item.weight >= 0 ? "green" : "rose"}>
                    {item.weight >= 0 ? `+${item.weight}` : item.weight}
                  </Badge>
                </li>
              ))}
              <li className="mt-1 flex items-center justify-between border-t border-slate-100 pt-1 text-sm font-semibold">
                <span>Total</span>
                <span>{job.explain.score}</span>
              </li>
            </ul>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-white p-3">
          <Meta label="Source" value={job.source} />
          <Meta label="External id" value={job.external_id} />
          <Meta label="Posted" value={formatDate(job.date_posted)} />
          <Meta label="First seen" value={formatDate(job.first_seen)} />
          <Meta label="Last seen" value={formatDate(job.last_seen)} />
          <Meta label="Status since" value={formatDateTime(job.status_changed_at)} />
          <Meta label="Type" value={job.job_type} />
          <Meta label="Level" value={job.job_level} />
          <Meta
            label="Remote"
            value={job.is_remote === null ? null : job.is_remote ? "yes" : "no"}
          />
          <Meta
            label="Salary"
            value={
              formatSalary(job)
                ? `${formatSalary(job)}${job.salary_interval ? ` / ${job.salary_interval}` : ""}`
                : null
            }
          />
          {job.company_url ? (
            <div className="col-span-2">
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Company</dt>
              <dd className="truncate text-sm">
                <a
                  href={job.company_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-sky-700 underline"
                >
                  {job.company_url}
                </a>
              </dd>
            </div>
          ) : null}
          <div className="col-span-2">
            <dt className="text-[11px] uppercase tracking-wide text-slate-500">Job id</dt>
            <dd className="truncate font-mono text-[11px] text-slate-600" title={job.job_id}>
              {job.job_id}
            </dd>
          </div>
        </dl>
      </aside>
    </div>
  );
}
