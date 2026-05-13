import { Button, Card } from "@heroui/react";
import { Bookmark, Check, ExternalLink, Trash2, X } from "lucide-react";

import type { JobRecord } from "../../api/types";
import { Meta, salaryLabel, ScoreBadge } from "./jobDisplay";

interface JobDetailPanelProps {
  isAppliedPending: boolean;
  isBlacklistPending: boolean;
  isBookmarkPending: boolean;
  job: JobRecord;
  onBlacklist: (job: JobRecord) => void;
  onClose: () => void;
  onDelete: (job: JobRecord) => void;
  onToggleApplied: (job: JobRecord) => void;
  onToggleBookmarked: (job: JobRecord) => void;
}

export function JobDetailPanel({
  isAppliedPending,
  isBlacklistPending,
  isBookmarkPending,
  job,
  onBlacklist,
  onClose,
  onDelete,
  onToggleApplied,
  onToggleBookmarked
}: JobDetailPanelProps) {
  return (
    <Card aria-label="Job detail" className="self-start border border-slate-200 shadow-sm" variant="default">
      <div className="grid gap-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold leading-snug text-slate-950">{job.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{job.company}</p>
          </div>
          <Button aria-label="Close details" isIconOnly onPress={onClose} variant="outline">
            <X aria-hidden="true" size={16} />
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <ScoreBadge score={job.relevance_score} />
          <span>{job.location}</span>
          <span>{job.site ?? "unknown"}</span>
        </div>
        <div className="grid gap-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          <Meta label="Salary" value={salaryLabel(job)} />
          <Meta label="Type" value={job.job_type ?? "unknown"} />
          <Meta label="Remote" value={job.is_remote ? "Yes" : "No"} />
          <Meta label="Date posted" value={job.date_posted ?? "unknown"} />
          <Meta label="First seen" value={job.first_seen ?? "unknown"} />
          <Meta label="Last seen" value={job.last_seen ?? "unknown"} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button isDisabled={isBookmarkPending} onPress={() => onToggleBookmarked(job)} variant="outline">
            <Bookmark aria-hidden="true" size={16} />
            {job.bookmarked ? "Unsave" : "Save"}
          </Button>
          <Button isDisabled={isAppliedPending} onPress={() => onToggleApplied(job)} variant="outline">
            <Check aria-hidden="true" size={16} />
            {job.applied ? "Mark not applied" : "Mark applied"}
          </Button>
          <Button isDisabled={isBlacklistPending} onPress={() => onBlacklist(job)} variant="danger">
            <Trash2 aria-hidden="true" size={16} />
            Blacklist
          </Button>
          <Button onPress={() => onDelete(job)} variant="danger">
            <X aria-hidden="true" size={16} />
            Delete job
          </Button>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {job.description ?? "No description available."}
        </p>
        {job.job_url ? (
          <a
            className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
            href={job.job_url}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink aria-hidden="true" size={16} />
            Open job
          </a>
        ) : null}
      </div>
    </Card>
  );
}
