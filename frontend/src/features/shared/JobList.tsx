import { useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink } from "lucide-react";

import type { JobSummary } from "../../api/types";
import { Badge, StatusBadge } from "../../components/Badge";
import { ScoreBar } from "../../components/ScoreBar";
import { jobMeta, relativeDays } from "./format";

const ROW_HEIGHT = 68;

export function JobList({
  jobs,
  selectedIndex,
  onSelect,
  onOpen,
  showStatus = false,
  isFresh,
  height = "calc(100vh - 220px)",
}: {
  jobs: JobSummary[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onOpen: (job: JobSummary) => void;
  showStatus?: boolean;
  isFresh?: (job: JobSummary) => boolean;
  height?: string;
}) {
  const parent = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: jobs.length,
    getScrollElement: () => parent.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
    initialRect: { width: 900, height: 600 },
  });

  useEffect(() => {
    if (selectedIndex >= 0 && selectedIndex < jobs.length) {
      virtualizer.scrollToIndex(selectedIndex, { align: "auto" });
    }
  }, [selectedIndex, jobs.length, virtualizer]);

  return (
    <div
      ref={parent}
      role="listbox"
      aria-label="Jobs"
      className="overflow-auto rounded-lg border border-slate-200 bg-white"
      style={{ height }}
    >
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((item) => {
          const job = jobs[item.index];
          const selected = item.index === selectedIndex;
          const fresh = isFresh?.(job) ?? false;
          const meta = jobMeta(job);
          return (
            <div
              key={job.job_id}
              role="option"
              aria-selected={selected}
              data-testid="job-row"
              onClick={() => {
                onSelect(item.index);
                onOpen(job);
              }}
              className={`absolute left-0 top-0 flex w-full cursor-pointer items-center gap-3 border-b border-slate-100 px-3 ${
                selected ? "bg-sky-50 ring-1 ring-inset ring-sky-300" : "hover:bg-slate-50"
              }`}
              style={{ height: item.size, transform: `translateY(${item.start}px)` }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  {fresh ? (
                    <span
                      className="h-2 w-2 shrink-0 rounded-full bg-sky-500"
                      title="New since your last visit"
                    />
                  ) : null}
                  <span className="truncate text-sm font-semibold text-slate-900">{job.title}</span>
                  {job.job_url ? (
                    <a
                      href={job.job_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      onClick={(event) => event.stopPropagation()}
                      className="text-slate-400 hover:text-slate-700"
                      aria-label="Open posting"
                    >
                      <ExternalLink size={14} />
                    </a>
                  ) : null}
                </div>
                <div className="truncate text-xs text-slate-600">
                  {job.company}
                  {job.location ? ` · ${job.location}` : ""}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  <Badge>{job.source}</Badge>
                  {meta.map((part) => (
                    <Badge key={part}>{part}</Badge>
                  ))}
                  {job.labels.map((label) => (
                    <Badge key={label} tone="violet">
                      {label}
                    </Badge>
                  ))}
                  <span className="text-[11px] text-slate-500">
                    posted {relativeDays(job.date_posted ?? job.first_seen)}
                  </span>
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <ScoreBar score={job.relevance_score} />
                {showStatus ? <StatusBadge status={job.status} /> : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
