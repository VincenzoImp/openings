import { ExternalLink, Pencil } from "lucide-react";

import type { JobDetail } from "../../api/types";
import { navigate } from "../../app/router";
import { Badge, StatusBadge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { MarkdownBody } from "../../components/MarkdownBody";
import { formatDate, formatDateTime, formatSalary } from "../shared/format";
import { useSettings, useSimilar } from "../shared/queries";

function Meta({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) {
    return null;
  }
  return (
    <div className="min-w-0">
      <dt className="text-[11px] uppercase tracking-wide text-fg-muted">{label}</dt>
      <dd className="truncate text-sm text-fg" title={value}>
        {value}
      </dd>
    </div>
  );
}

function SimilarPostings({ job }: { job: JobDetail }) {
  const settings = useSettings();
  const enabled = settings.data?.embeddings.enabled ?? true;
  const similar = useSimilar(job.job_id, enabled);

  if (!enabled) {
    return (
      <p className="text-sm text-fg-muted">
        Embeddings are disabled in settings, so similar postings are not available.
      </p>
    );
  }
  if (similar.isPending) {
    return <p className="text-sm text-fg-muted">Looking for similar postings…</p>;
  }
  if (similar.error) {
    return (
      <p className="text-sm text-fg-muted">
        {similar.error instanceof Error ? similar.error.message : "Similarity search failed."}
      </p>
    );
  }
  const items = (similar.data ?? []).filter((item) => item.job_id !== job.job_id);
  if (items.length === 0) {
    return <p className="text-sm text-fg-muted">No similar postings stored yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li key={item.job_id} className="flex items-start gap-2">
          <span
            className="tabular w-10 shrink-0 text-right text-xs text-fg-muted"
            title="Similarity"
          >
            {Math.round(item.similarity * 100)}%
          </span>
          <div className="min-w-0 flex-1">
            <button
              type="button"
              onClick={() => navigate({ jobId: item.job_id })}
              className="block max-w-full truncate text-left text-sm font-medium text-fg hover:underline"
            >
              {item.title}
            </button>
            <div className="truncate text-xs text-fg-muted">
              {item.company}
              {item.location ? ` · ${item.location}` : ""}
            </div>
          </div>
          <StatusBadge status={item.status} />
        </li>
      ))}
    </ul>
  );
}

export function PostingTab({ job, onEdit }: { job: JobDetail; onEdit: () => void }) {
  const salary = formatSalary(job);
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-w-0 flex-col gap-4">
        <Card
          title="Description"
          actions={
            <Button size="sm" variant="ghost" onClick={onEdit}>
              <Pencil size={14} aria-hidden="true" /> Edit
            </Button>
          }
        >
          {job.description ? (
            <MarkdownBody text={job.description} />
          ) : (
            <p className="text-sm text-fg-muted">
              No description stored. Open the posting for the full text, or paste it with Edit.
            </p>
          )}
          {job.raw_json ? (
            <details className="mt-4">
              <summary className="cursor-pointer text-xs text-fg-muted">Raw source payload</summary>
              <pre className="mt-2 max-h-80 overflow-auto rounded bg-surface-2 p-2 text-[11px] text-fg-muted">
                {job.raw_json}
              </pre>
            </details>
          ) : null}
        </Card>
        <Card title="Similar postings">
          <SimilarPostings job={job} />
        </Card>
      </div>
      <aside className="flex min-w-0 flex-col gap-4">
        <Card title="Postings">
          <ul className="flex flex-col gap-2">
            {job.postings.map((posting) => (
              <li key={posting.id} className="flex items-start gap-2">
                <Badge>{posting.source}</Badge>
                <div className="min-w-0 flex-1 text-xs text-fg-muted">
                  {posting.url ? (
                    <a
                      href={posting.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex max-w-full items-center gap-1 truncate text-fg hover:underline"
                    >
                      <span className="truncate">{posting.external_id ?? posting.url}</span>
                      <ExternalLink size={12} aria-hidden="true" className="shrink-0" />
                    </a>
                  ) : (
                    <span className="text-fg">{posting.external_id ?? "no url"}</span>
                  )}
                  <div>
                    seen {formatDate(posting.first_seen)}
                    {posting.last_seen !== posting.first_seen
                      ? ` – ${formatDate(posting.last_seen)}`
                      : ""}
                  </div>
                </div>
              </li>
            ))}
            {job.postings.length === 0 ? (
              <li className="text-sm text-fg-muted">Added by hand, without a posting URL.</li>
            ) : null}
          </ul>
        </Card>
        <Card title="Score breakdown">
          {job.explain.matched.length === 0 ? (
            <p className="text-sm text-fg-muted">No scoring category matched.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {job.explain.matched.map((item) => (
                <li key={item.category} className="flex items-center justify-between gap-2 text-sm">
                  <span className="truncate">{item.category}</span>
                  <Badge tone={item.weight >= 0 ? "positive" : "negative"}>
                    {item.weight >= 0 ? `+${item.weight}` : item.weight}
                  </Badge>
                </li>
              ))}
              <li className="mt-1 flex items-center justify-between border-t border-edge pt-1 text-sm font-semibold">
                <span>Total</span>
                <span className="tabular">{job.explain.score}</span>
              </li>
            </ul>
          )}
        </Card>
        <Card title="Details">
          <dl className="grid grid-cols-2 gap-3">
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
                salary ? `${salary}${job.salary_interval ? ` / ${job.salary_interval}` : ""}` : null
              }
            />
            {job.company_url ? (
              <div className="col-span-2 min-w-0">
                <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Company</dt>
                <dd className="truncate text-sm">
                  <a
                    href={job.company_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-accent hover:underline"
                  >
                    {job.company_url}
                  </a>
                </dd>
              </div>
            ) : null}
            <div className="col-span-2 min-w-0">
              <dt className="text-[11px] uppercase tracking-wide text-fg-muted">Job id</dt>
              <dd className="truncate font-mono text-[11px] text-fg-muted" title={job.job_id}>
                {job.job_id}
              </dd>
            </div>
          </dl>
        </Card>
      </aside>
    </div>
  );
}
