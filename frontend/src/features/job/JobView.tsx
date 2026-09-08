import { useMemo, useState } from "react";
import {
  ArrowLeft,
  Ban,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Link2,
  MoreHorizontal,
  Pencil,
  RotateCcw,
} from "lucide-react";

import { api } from "../../api/client";
import { JOB_STATUSES } from "../../api/types";
import type { JobStatus } from "../../api/types";
import { saveBlob } from "../../app/download";
import { useHotkeys } from "../../app/hotkeys";
import { navigate, routeHref, setParams, useRoute } from "../../app/router";
import { useToast } from "../../app/toastContext";
import { Badge, StatusBadge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Select } from "../../components/Field";
import { Menu } from "../../components/Menu";
import { ScoreBar } from "../../components/ScoreBar";
import { useJobActions } from "../shared/actions";
import { formatSalary, jobMeta } from "../shared/format";
import { STATUS_LABELS } from "../shared/labels";
import { LabelsEditor } from "../shared/LabelsEditor";
import { recallList } from "../shared/listContext";
import { useJob } from "../shared/queries";
import { StatusNoteDialog } from "../shared/StatusNoteDialog";
import { ActivityTab } from "./ActivityTab";
import { ApplicationTab } from "./ApplicationTab";
import { EditPostingDialog } from "./EditPostingDialog";
import { MergeDialog } from "./MergeDialog";
import { PostingTab } from "./PostingTab";

type Tab = "posting" | "application" | "activity";

const TABS: { id: Tab; label: string }[] = [
  { id: "posting", label: "Posting" },
  { id: "application", label: "Application" },
  { id: "activity", label: "Activity" },
];

function isTab(value: string | null): value is Tab {
  return TABS.some((tab) => tab.id === value);
}

export function JobView({ jobId }: { jobId: string }) {
  const route = useRoute();
  const query = useJob(jobId);
  const actions = useJobActions();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [merging, setMerging] = useState(false);
  const [statusNote, setStatusNote] = useState(false);

  const tabParam = route.params.get("tab");
  const tab: Tab = isTab(tabParam) ? tabParam : "posting";
  const job = query.data;

  const neighbours = useMemo(() => {
    const ids = recallList();
    const index = ids.indexOf(jobId);
    return {
      prev: index > 0 ? ids[index - 1] : null,
      next: index >= 0 && index < ids.length - 1 ? ids[index + 1] : null,
      position: index >= 0 ? `${index + 1} of ${ids.length}` : null,
    };
  }, [jobId]);

  const back = () => navigate({ jobId: null, params: null });
  const step = (target: string | null) => target && navigate({ jobId: target }, { replace: true });

  const copyLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}${routeHref({ jobId, params: null })}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.push("Link copied", "success");
    } catch {
      toast.push(url, "info");
    }
  };

  const downloadBundle = async () => {
    try {
      const download = await api.downloadBundle(jobId);
      saveBlob(download.blob, download.filename);
    } catch (error) {
      toast.push(error instanceof Error ? error.message : String(error), "error");
    }
  };

  useHotkeys("view", [
    { key: "Escape", run: back, description: "Back to the list", group: "Job page", label: "Esc" },
    {
      key: "[",
      run: () => step(neighbours.prev),
      description: "Previous / next job in the list",
      group: "Job page",
      label: "[ / ]",
    },
    { key: "]", run: () => step(neighbours.next) },
    {
      key: "o",
      run: () => job && actions.openPosting(job),
      description: "Open the posting in a new tab",
      group: "Job page",
    },
    {
      key: "s",
      run: () => job && actions.setStatus.mutate({ jobIds: [job.job_id], status: "shortlisted" }),
      description: "Shortlist",
      group: "Job page",
    },
    {
      key: "a",
      run: () => job && actions.setStatus.mutate({ jobIds: [job.job_id], status: "applied" }),
      description: "Mark applied",
      group: "Job page",
    },
    {
      key: "S",
      run: () => setStatusNote(true),
      description: "Change status with a note",
      group: "Job page",
      label: "Shift+S",
    },
    { key: "e", run: () => setEditing(true), description: "Edit the posting", group: "Job page" },
    {
      key: "x",
      run: () => job && void actions.blacklist([job]),
      description: "Blacklist (asks first)",
      group: "Job page",
    },
    {
      key: "b",
      run: () => void downloadBundle(),
      description: "Download the application bundle",
      group: "Job page",
    },
  ]);

  if (query.isPending) {
    return (
      <div className="rounded-lg border border-edge bg-surface p-4">
        <Skeleton lines={6} />
      </div>
    );
  }
  if (query.error || !job) {
    return (
      <div className="flex flex-col gap-3">
        <Button onClick={back} className="w-fit">
          <ArrowLeft size={14} aria-hidden="true" /> Back
        </Button>
        <ErrorNotice
          error={query.error ?? new Error("Job not found")}
          onRetry={() => query.refetch()}
        />
      </div>
    );
  }

  const salary = formatSalary(job);
  const blacklisted = job.status === "blacklisted";
  const materialCount = job.attachments.length + job.notes.length;

  return (
    <article className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" onClick={back} className="-ml-2">
          <ArrowLeft size={14} aria-hidden="true" /> Back
        </Button>
        {neighbours.position ? (
          <div className="flex items-center gap-1 text-xs text-fg-muted">
            <Button
              size="sm"
              variant="ghost"
              aria-label="Previous job"
              disabled={!neighbours.prev}
              onClick={() => step(neighbours.prev)}
            >
              <ChevronLeft size={14} aria-hidden="true" />
            </Button>
            <span className="tabular">{neighbours.position}</span>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Next job"
              disabled={!neighbours.next}
              onClick={() => step(neighbours.next)}
            >
              <ChevronRight size={14} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
      </div>

      {blacklisted ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm"
        >
          <span>
            <strong>Blacklisted.</strong> Hidden from every list and never ingested again; notes and
            files are kept.
          </span>
          <Button size="sm" onClick={() => actions.unblacklist.mutate([job.job_id])}>
            <RotateCcw size={14} aria-hidden="true" /> Restore
          </Button>
        </div>
      ) : null}

      <header className="flex flex-col gap-3">
        <div className="min-w-0">
          <h1 className="break-words text-xl font-semibold leading-tight text-fg">{job.title}</h1>
          <p className="text-sm text-fg-muted">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
            {salary ? ` · ${salary}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <ScoreBar score={job.relevance_score} />
            <StatusBadge status={job.status} />
            <Badge>{job.source}</Badge>
            {job.postings.length > 1 ? <Badge>{job.postings.length} postings</Badge> : null}
            {jobMeta(job).map((part) => (
              <Badge key={part}>{part}</Badge>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
          <Select
            aria-label="Status"
            className="sm:!w-44"
            value={job.status}
            disabled={blacklisted}
            onChange={(event) =>
              actions.setStatus.mutate({
                jobIds: [job.job_id],
                status: event.target.value as JobStatus,
              })
            }
          >
            {JOB_STATUSES.filter((status) => status !== "blacklisted" || blacklisted).map(
              (status) => (
                <option key={status} value={status}>
                  {STATUS_LABELS[status]}
                </option>
              ),
            )}
          </Select>
          <Button onClick={() => setStatusNote(true)} disabled={blacklisted}>
            Status with note…
          </Button>
          {job.job_url ? (
            <a
              href={job.job_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex h-8 items-center justify-center gap-1 rounded-md bg-accent px-3 text-sm font-medium text-on-accent hover:brightness-110"
            >
              Open posting <ExternalLink size={14} aria-hidden="true" />
            </a>
          ) : null}
          <Menu
            trigger={({ toggle }) => (
              <Button onClick={toggle} aria-label="More actions" className="justify-center">
                <MoreHorizontal size={14} aria-hidden="true" /> More
              </Button>
            )}
            items={[
              {
                label: (
                  <span className="inline-flex items-center gap-2">
                    <Pencil size={14} aria-hidden="true" /> Edit posting
                  </span>
                ),
                onSelect: () => setEditing(true),
              },
              {
                label: (
                  <span className="inline-flex items-center gap-2">
                    <Link2 size={14} aria-hidden="true" /> Copy link
                  </span>
                ),
                onSelect: () => void copyLink(),
              },
              { label: "Download bundle (.zip)", onSelect: () => void downloadBundle() },
              { label: "Merge another job into this one…", onSelect: () => setMerging(true) },
              {
                label: (
                  <span className="inline-flex items-center gap-2">
                    <Ban size={14} aria-hidden="true" /> Blacklist…
                  </span>
                ),
                onSelect: () => void actions.blacklist([job]),
                disabled: blacklisted,
              },
              {
                label: "Delete…",
                onSelect: () => void actions.remove([job]).then((ok) => ok && back()),
                danger: true,
              },
            ]}
          />
        </div>
        <LabelsEditor jobIds={[job.job_id]} labels={job.labels} />
      </header>

      <nav
        className="-mx-4 flex gap-1 overflow-x-auto border-b border-edge px-4 md:mx-0 md:px-0"
        role="tablist"
        aria-label="Job sections"
      >
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            onClick={() => setParams({ tab: entry.id === "posting" ? null : entry.id })}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-medium ${
              tab === entry.id
                ? "border-fg text-fg"
                : "border-transparent text-fg-muted hover:text-fg"
            }`}
          >
            {entry.label}
            {entry.id === "application" && materialCount > 0 ? (
              <span className="tabular ml-1 text-xs text-fg-faint">{materialCount}</span>
            ) : null}
            {entry.id === "activity" ? (
              <span className="tabular ml-1 text-xs text-fg-faint">{job.events.length}</span>
            ) : null}
          </button>
        ))}
      </nav>

      {tab === "posting" ? <PostingTab job={job} onEdit={() => setEditing(true)} /> : null}
      {tab === "application" ? <ApplicationTab job={job} onBundle={downloadBundle} /> : null}
      {tab === "activity" ? <ActivityTab job={job} /> : null}

      <EditPostingDialog open={editing} job={job} onClose={() => setEditing(false)} />
      <MergeDialog open={merging} job={job} onClose={() => setMerging(false)} />
      <StatusNoteDialog
        open={statusNote}
        jobIds={[job.job_id]}
        initialStatus={blacklisted ? "shortlisted" : job.status}
        onClose={() => setStatusNote(false)}
      />
    </article>
  );
}
