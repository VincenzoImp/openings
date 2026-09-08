import { useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink, Paperclip, StickyNote } from "lucide-react";

import type { JobSummary } from "../../api/types";
import { Badge, StatusBadge } from "../../components/Badge";
import { ScoreBar } from "../../components/ScoreBar";
import { jobMeta, relativeDays } from "./format";

const ESTIMATED_ROW = 72;

export function JobList({
  jobs,
  selectedIndex,
  checked,
  onSelect,
  onToggle,
  onOpen,
  onEndReached,
  showStatus = false,
  selectable = true,
  isFresh,
  footer,
  className = "",
}: {
  jobs: JobSummary[];
  selectedIndex: number;
  checked?: Set<string>;
  onSelect: (index: number) => void;
  onToggle?: (jobId: string) => void;
  onOpen: (job: JobSummary) => void;
  onEndReached?: () => void;
  showStatus?: boolean;
  selectable?: boolean;
  isFresh?: (job: JobSummary) => boolean;
  footer?: React.ReactNode;
  className?: string;
}) {
  const parent = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: jobs.length,
    getScrollElement: () => parent.current,
    estimateSize: () => ESTIMATED_ROW,
    overscan: 8,
  });
  const virtualItems = virtualizer.getVirtualItems();

  useEffect(() => {
    if (selectedIndex >= 0 && selectedIndex < jobs.length) {
      virtualizer.scrollToIndex(selectedIndex, { align: "auto" });
    }
    // Only when the cursor moves, not on every render of the list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndex]);

  useEffect(() => {
    if (!onEndReached || virtualItems.length === 0) {
      return;
    }
    const last = virtualItems[virtualItems.length - 1];
    if (last.index >= jobs.length - 10) {
      onEndReached();
    }
  }, [virtualItems, jobs.length, onEndReached]);

  return (
    <div
      ref={parent}
      role="list"
      aria-label="Jobs"
      tabIndex={0}
      data-testid="job-list"
      className={`min-h-0 overflow-auto rounded-lg border border-edge bg-surface focus-visible:outline-2 focus-visible:outline-accent ${className}`}
    >
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualItems.map((item) => {
          const job = jobs[item.index];
          const selected = item.index === selectedIndex;
          const isChecked = checked?.has(job.job_id) ?? false;
          const fresh = isFresh?.(job) ?? false;
          const meta = jobMeta(job);
          return (
            <div
              key={job.job_id}
              ref={virtualizer.measureElement}
              data-index={item.index}
              role="listitem"
              aria-current={selected ? "true" : undefined}
              data-testid="job-row"
              onClick={() => onSelect(item.index)}
              onDoubleClick={() => onOpen(job)}
              className={`absolute left-0 top-0 flex w-full cursor-default gap-3 border-b border-edge px-3 py-2 ${
                selected ? "bg-accent/8" : "hover:bg-surface-2/60"
              } ${isChecked ? "bg-accent/12" : ""}`}
              style={{ transform: `translateY(${item.start}px)` }}
            >
              {selectable ? (
                <input
                  type="checkbox"
                  aria-label={`Select ${job.title}`}
                  checked={isChecked}
                  onChange={() => onToggle?.(job.job_id)}
                  onClick={(event) => event.stopPropagation()}
                  className="mt-1 h-4 w-4 shrink-0 accent-accent"
                />
              ) : null}
              <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-center gap-2">
                    {fresh ? (
                      <span
                        className="h-2 w-2 shrink-0 rounded-full bg-accent"
                        title="New since your last visit"
                        aria-label="New since your last visit"
                      />
                    ) : null}
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onOpen(job);
                      }}
                      className="min-w-0 truncate text-left text-sm font-semibold text-fg hover:underline"
                    >
                      {job.title}
                    </button>
                    {job.job_url ? (
                      <a
                        href={job.job_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        onClick={(event) => event.stopPropagation()}
                        className="shrink-0 text-fg-faint hover:text-fg"
                        aria-label="Open posting in a new tab"
                      >
                        <ExternalLink size={14} aria-hidden="true" />
                      </a>
                    ) : null}
                  </div>
                  <div className="truncate text-xs text-fg-muted">
                    {job.company}
                    {job.location ? ` · ${job.location}` : ""}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    <Badge>{job.source}</Badge>
                    {job.postings_count > 1 ? <Badge>+{job.postings_count - 1} more</Badge> : null}
                    {meta.map((part) => (
                      <Badge key={part}>{part}</Badge>
                    ))}
                    {job.labels.map((label) => (
                      <Badge key={label} tone="accent">
                        {label}
                      </Badge>
                    ))}
                    {job.attachments_count > 0 ? (
                      <Badge tone="positive" title={`${job.attachments_count} attachment(s)`}>
                        <Paperclip size={11} aria-hidden="true" /> {job.attachments_count}
                      </Badge>
                    ) : null}
                    {job.notes_count > 0 ? (
                      <Badge tone="warning" title={`${job.notes_count} note(s)`}>
                        <StickyNote size={11} aria-hidden="true" /> {job.notes_count}
                      </Badge>
                    ) : null}
                    <span className="text-[11px] text-fg-faint">
                      {job.date_posted ? "posted" : "seen"}{" "}
                      {relativeDays(job.date_posted ?? job.first_seen)}
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-end sm:gap-1">
                  <ScoreBar score={job.relevance_score} />
                  {showStatus ? <StatusBadge status={job.status} /> : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {footer ? (
        <div className="border-t border-edge px-3 py-2 text-xs text-fg-muted">{footer}</div>
      ) : null}
    </div>
  );
}
