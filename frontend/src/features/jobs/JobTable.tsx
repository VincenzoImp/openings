import { Button, Card, Tooltip } from "@heroui/react";
import { createColumnHelper, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Ban, Bookmark, Check, PanelRightOpen, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useRef } from "react";

import type { JobRecord } from "../../api/types";
import { ScoreBadge, statusChip } from "./jobDisplay";

const JOB_GRID_CLASS =
  "grid grid-cols-[32px_44px_minmax(0,1fr)] items-center gap-2 px-3 md:grid-cols-[36px_52px_minmax(220px,2fr)_minmax(160px,1fr)_100px_100px_220px] md:gap-3 md:px-4";

const columnHelper = createColumnHelper<JobRecord>();
const columns = [
  columnHelper.accessor("relevance_score", { header: "Score" }),
  columnHelper.accessor("title", { header: "Role" }),
  columnHelper.accessor("company", { header: "Company" }),
  columnHelper.accessor("site", { header: "Site" }),
  columnHelper.display({ id: "status", header: "Status" }),
  columnHelper.display({ id: "actions", header: "Actions" })
];

interface JobTableProps {
  isAppliedPending: boolean;
  isBlacklistPending: boolean;
  isBookmarkPending: boolean;
  isDeletePending: boolean;
  isError: boolean;
  isLoading: boolean;
  jobs: JobRecord[];
  onBlacklistJob: (job: JobRecord) => void;
  onDeleteJob: (job: JobRecord) => void;
  onSelectJob: (job: JobRecord) => void;
  onToggleApplied: (job: JobRecord) => void;
  onToggleBookmarked: (job: JobRecord) => void;
  selectedIds: Set<string>;
  onToggleSelected: (jobId: string) => void;
}

export function JobTable({
  isAppliedPending,
  isBlacklistPending,
  isBookmarkPending,
  isDeletePending,
  isError,
  isLoading,
  jobs,
  onBlacklistJob,
  onDeleteJob,
  onSelectJob,
  onToggleApplied,
  onToggleBookmarked,
  onToggleSelected,
  selectedIds
}: JobTableProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const table = useReactTable({
    columns,
    data: jobs,
    getCoreRowModel: getCoreRowModel()
  });
  const rows = table.getRowModel().rows;
  const rowHeight = globalThis.innerWidth < 768 ? 124 : 58;
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    estimateSize: () => rowHeight,
    getScrollElement: () => scrollRef.current,
    overscan: 8
  });
  const virtualItems = rowVirtualizer.getVirtualItems();
  const visibleRows = virtualItems.length
    ? virtualItems.map((item) => ({ fallbackIndex: item.index, item, row: rows[item.index] }))
    : rows.map((row, index) => ({ item: null, row, fallbackIndex: index }));

  return (
    <Card className="w-full min-w-0 overflow-hidden border border-slate-200 shadow-sm" variant="default">
      <div aria-colcount={7} aria-rowcount={jobs.length} className="min-w-0 overflow-x-auto" role="table">
        <div
          className={`${JOB_GRID_CLASS} border-b border-slate-200 bg-slate-100 py-3 text-xs font-bold uppercase text-slate-500 md:min-w-[980px]`}
          role="row"
        >
          <span role="columnheader" />
          <span role="columnheader">Score</span>
          <span role="columnheader">Role</span>
          <span className="hidden md:inline" role="columnheader">
            Company
          </span>
          <span className="hidden md:inline" role="columnheader">
            Site
          </span>
          <span className="hidden md:inline" role="columnheader">
            Status
          </span>
          <span className="hidden md:inline" role="columnheader">
            Actions
          </span>
        </div>

        {isLoading ? <div className="px-4 py-5 text-sm text-slate-500">Loading jobs</div> : null}
        {isError ? <div className="px-4 py-5 text-sm text-red-700">Unable to load jobs</div> : null}
        {!isLoading && !isError && jobs.length === 0 ? (
          <div className="px-4 py-8 text-sm text-slate-500">No jobs match the current filters</div>
        ) : null}

        <div className="min-w-0 max-h-[min(62vh,720px)] overflow-auto" ref={scrollRef}>
          <div
            className="relative md:min-w-[980px]"
            style={{ height: virtualItems.length ? rowVirtualizer.getTotalSize() : "auto" }}
          >
            {visibleRows.map(({ item, row, fallbackIndex }) => {
              const job = row.original;
              const top = item?.start ?? fallbackIndex * rowHeight;
              return (
                <div
                  className={`${JOB_GRID_CLASS} min-h-[124px] w-full border-b border-slate-100 bg-white py-2 text-sm text-slate-900 hover:bg-slate-50 md:min-h-[58px] md:py-0`}
                  key={job.job_id}
                  aria-rowindex={fallbackIndex + 2}
                  role="row"
                  style={
                    item
                      ? {
                          left: 0,
                          position: "absolute",
                          top: 0,
                          transform: `translateY(${top}px)`
                        }
                      : undefined
                  }
                >
                  <label className="flex items-center" role="cell">
                    <input
                      aria-label={`Select ${job.title}`}
                      checked={selectedIds.has(job.job_id)}
                      className="size-4 accent-emerald-700"
                      onChange={() => onToggleSelected(job.job_id)}
                      type="checkbox"
                    />
                  </label>
                  <span role="cell">
                    <ScoreBadge score={job.relevance_score} />
                  </span>
                  <span className="min-w-0" role="cell">
                    <button
                      aria-label={`View ${job.title} details`}
                      className="grid min-w-0 gap-0.5 text-left"
                      onClick={() => onSelectJob(job)}
                      type="button"
                    >
                      <span className="truncate font-semibold text-slate-950">{job.title}</span>
                      <small className="truncate text-xs text-slate-500">{job.company}</small>
                      <small className="truncate text-xs text-slate-500 md:hidden">
                        {job.location} / {job.site ?? "unknown"} /{" "}
                        {job.applied ? "Applied" : job.bookmarked ? "Saved" : "Open"}
                      </small>
                    </button>
                  </span>
                  <span className="hidden truncate md:inline" role="cell">
                    {job.company}
                  </span>
                  <span className="hidden truncate md:inline" role="cell">
                    {job.site ?? "unknown"}
                  </span>
                  <span className="hidden items-center gap-2 md:flex" role="cell">
                    {statusChip(job)}
                  </span>
                  <span
                    className="col-start-3 row-start-2 mt-1 flex items-center gap-1.5 md:col-auto md:row-auto md:mt-0"
                    role="cell"
                  >
                    <RowAction
                      aria-label={`${job.bookmarked ? "Unsave" : "Save"} ${job.title}`}
                      isDisabled={isBookmarkPending}
                      label={job.bookmarked ? "Unsave" : "Save"}
                      onPress={() => onToggleBookmarked(job)}
                    >
                      <Bookmark aria-hidden="true" size={16} />
                    </RowAction>
                    <RowAction
                      aria-label={`Mark ${job.title} ${job.applied ? "not applied" : "applied"}`}
                      isDisabled={isAppliedPending}
                      label={job.applied ? "Mark not applied" : "Mark applied"}
                      onPress={() => onToggleApplied(job)}
                    >
                      <Check aria-hidden="true" size={16} />
                    </RowAction>
                    <RowAction
                      aria-label={`Open ${job.title} details`}
                      label="Open details"
                      onPress={() => onSelectJob(job)}
                    >
                      <PanelRightOpen aria-hidden="true" size={16} />
                    </RowAction>
                    <RowAction
                      aria-label={`Blacklist ${job.title}`}
                      isDisabled={isBlacklistPending}
                      label="Blacklist"
                      onPress={() => onBlacklistJob(job)}
                    >
                      <Ban aria-hidden="true" size={16} />
                    </RowAction>
                    <RowAction
                      aria-label={`Delete ${job.title}`}
                      isDisabled={isDeletePending}
                      label="Delete"
                      onPress={() => onDeleteJob(job)}
                    >
                      <Trash2 aria-hidden="true" size={16} />
                    </RowAction>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Card>
  );
}

function RowAction({
  children,
  isDisabled,
  label,
  onPress,
  ...buttonProps
}: {
  "aria-label": string;
  children: ReactNode;
  isDisabled?: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Tooltip>
      <Tooltip.Trigger>
        <Button
          {...buttonProps}
          className="size-8 min-w-8 md:size-9 md:min-w-9"
          isDisabled={isDisabled}
          isIconOnly
          onPress={onPress}
          variant="outline"
        >
          {children}
        </Button>
      </Tooltip.Trigger>
      <Tooltip.Content>{label}</Tooltip.Content>
    </Tooltip>
  );
}
