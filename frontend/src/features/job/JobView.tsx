import { useState } from "react";
import { ArrowLeft, ExternalLink, Trash2, Ban } from "lucide-react";

import { JOB_STATUSES } from "../../api/types";
import type { JobStatus } from "../../api/types";
import { useHotkeys } from "../../app/hotkeys";
import { navigate } from "../../app/router";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/Dialog";
import { ErrorNotice, Spinner } from "../../components/EmptyState";
import { Select } from "../../components/Field";
import { ScoreBar } from "../../components/ScoreBar";
import { STATUS_LABELS, formatSalary } from "../shared/format";
import { LabelsEditor } from "../shared/LabelsEditor";
import { useJob, useJobCommands } from "../shared/queries";
import { ActivityTab } from "./ActivityTab";
import { ApplicationTab } from "./ApplicationTab";
import { PostingTab } from "./PostingTab";

type Tab = "posting" | "application" | "activity";

const TABS: { id: Tab; label: string }[] = [
  { id: "posting", label: "Posting" },
  { id: "application", label: "Application" },
  { id: "activity", label: "Activity" },
];

export function JobView({ jobId }: { jobId: string }) {
  const query = useJob(jobId);
  const commands = useJobCommands();
  const [tab, setTab] = useState<Tab>("posting");
  const [confirm, setConfirm] = useState<"blacklist" | "delete" | null>(null);

  const back = () => navigate({ jobId: null });
  const job = query.data;

  useHotkeys({
    Escape: back,
    o: () => job?.job_url && window.open(job.job_url, "_blank", "noopener"),
    s: () => job && commands.setStatus.mutate({ jobIds: [job.job_id], status: "shortlisted" }),
    a: () => job && commands.setStatus.mutate({ jobIds: [job.job_id], status: "applied" }),
    x: () => job && setConfirm("blacklist"),
  });

  if (query.isPending) {
    return <Spinner />;
  }
  if (query.error || !job) {
    return (
      <div className="flex flex-col gap-3">
        <Button onClick={back} className="w-fit">
          <ArrowLeft size={14} /> Back
        </Button>
        <ErrorNotice error={query.error ?? new Error("Job not found")} />
      </div>
    );
  }

  const salary = formatSalary(job);

  return (
    <article className="flex flex-col gap-4">
      <div>
        <Button variant="ghost" size="sm" onClick={back} className="-ml-2 mb-2">
          <ArrowLeft size={14} /> Back
        </Button>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-slate-900">{job.title}</h1>
            <p className="text-sm text-slate-600">
              {job.company}
              {job.location ? ` · ${job.location}` : ""}
              {salary ? ` · ${salary}` : ""}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <ScoreBar score={job.relevance_score} />
              <Badge>{job.source}</Badge>
              {job.job_type ? <Badge>{job.job_type}</Badge> : null}
              {job.is_remote ? <Badge>remote</Badge> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label="Status"
              className="!w-40"
              value={job.status}
              onChange={(event) =>
                commands.setStatus.mutate({
                  jobIds: [job.job_id],
                  status: event.target.value as JobStatus,
                })
              }
            >
              {JOB_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABELS[status]}
                </option>
              ))}
            </Select>
            {job.job_url ? (
              <a
                href={job.job_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
              >
                Open posting <ExternalLink size={14} />
              </a>
            ) : null}
            <Button variant="ghost" size="sm" onClick={() => setConfirm("blacklist")}>
              <Ban size={14} /> Blacklist
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirm("delete")}>
              <Trash2 size={14} /> Delete
            </Button>
          </div>
        </div>
        <div className="mt-3">
          <LabelsEditor jobId={job.job_id} labels={job.labels} />
        </div>
      </div>

      <nav className="flex gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            onClick={() => setTab(entry.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === entry.id
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {entry.label}
            {entry.id === "application" && job.attachments.length + job.notes.length > 0 ? (
              <span className="ml-1 text-xs text-slate-400">
                {job.attachments.length + job.notes.length}
              </span>
            ) : null}
          </button>
        ))}
      </nav>

      {tab === "posting" ? <PostingTab job={job} /> : null}
      {tab === "application" ? <ApplicationTab job={job} /> : null}
      {tab === "activity" ? <ActivityTab job={job} /> : null}

      <ConfirmDialog
        open={confirm === "blacklist"}
        title="Blacklist this posting?"
        message="The job, its notes and attachments are deleted and the posting is never ingested again."
        confirmLabel="Blacklist"
        danger
        onConfirm={() => commands.blacklist.mutate([job.job_id], { onSuccess: back })}
        onClose={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === "delete"}
        title="Delete this job?"
        message="The job, its notes and attachments are deleted. It can be ingested again by a later run."
        confirmLabel="Delete"
        danger
        onConfirm={() => commands.deleteJobs.mutate([job.job_id], { onSuccess: back })}
        onClose={() => setConfirm(null)}
      />
    </article>
  );
}
