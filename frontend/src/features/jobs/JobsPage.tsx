import { Button, Card, Chip, Input } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Bookmark,
  Check,
  Download,
  ExternalLink,
  PanelRightOpen,
  Search,
  Trash2,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { blacklistJobs, setApplied, setBookmarked } from "../../api/client";
import type { JobRecord } from "../../api/types";
import { jobsQuery } from "./jobQueries";

type StatusFilter = "all" | "bookmarked" | "applied" | "open";

const PAGE_SIZE = 100;
const JOB_GRID_CLASS =
  "grid grid-cols-[36px_72px_minmax(220px,2fr)_minmax(160px,1fr)_110px_110px_160px] items-center gap-3 px-4";

const columnHelper = createColumnHelper<JobRecord>();
const columns = [
  columnHelper.accessor("relevance_score", { header: "Score" }),
  columnHelper.accessor("title", { header: "Role" }),
  columnHelper.accessor("company", { header: "Company" }),
  columnHelper.accessor("site", { header: "Site" }),
  columnHelper.display({ id: "status", header: "Status" }),
  columnHelper.display({ id: "actions", header: "Actions" })
];

function scoreColor(score: number): "default" | "success" | "warning" {
  if (score >= 40) {
    return "success";
  }
  if (score >= 25) {
    return "warning";
  }
  return "default";
}

function statusChip(job: JobRecord) {
  if (job.applied) {
    return (
      <Chip color="success" size="sm" variant="soft">
        Applied
      </Chip>
    );
  }
  if (job.bookmarked) {
    return (
      <Chip color="warning" size="sm" variant="soft">
        Saved
      </Chip>
    );
  }
  return (
    <Chip color="default" size="sm" variant="soft">
      Open
    </Chip>
  );
}

function csvCell(value: string | number | boolean | null) {
  return `"${String(value ?? "").replaceAll("\"", "\"\"")}"`;
}

function exportJobsCsv(jobs: JobRecord[]) {
  const columns = ["title", "company", "location", "site", "relevance_score", "applied", "bookmarked"];
  const lines = [
    columns.join(","),
    ...jobs.map((job) =>
      [
        job.title,
        job.company,
        job.location,
        job.site,
        job.relevance_score,
        job.applied,
        job.bookmarked
      ]
        .map(csvCell)
        .join(",")
    )
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "jobs.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function JobsPage() {
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [minScore, setMinScore] = useState("");
  const [site, setSite] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const filterKey = useMemo(
    () => JSON.stringify({ minScore, remoteOnly, site, status, text }),
    [minScore, remoteOnly, site, status, text]
  );

  useEffect(() => {
    setPage(0);
    setSelectedIds(new Set());
    setSelectedJob(null);
  }, [filterKey]);

  useEffect(() => {
    setSelectedIds(new Set());
    setSelectedJob(null);
  }, [page]);

  const params = useMemo(
    () => ({
      applied: status === "applied" ? true : status === "open" ? false : undefined,
      bookmarked: status === "bookmarked" ? true : status === "open" ? false : undefined,
      limit: PAGE_SIZE,
      min_score: minScore ? Number(minScore) : undefined,
      offset: page * PAGE_SIZE,
      remote: remoteOnly ? true : undefined,
      site: site || undefined,
      sort: "score" as const,
      text: text || undefined
    }),
    [minScore, page, remoteOnly, site, status, text]
  );

  const { data, isLoading, isError } = useQuery(jobsQuery(params));
  const jobs = data?.items ?? [];

  useEffect(() => {
    if (data?.total === undefined) {
      return;
    }

    const lastPage = Math.max(0, Math.ceil(data.total / PAGE_SIZE) - 1);
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [data?.total, page]);

  useEffect(() => {
    setSelectedJob((current) => {
      if (!current) {
        return null;
      }
      return jobs.find((job) => job.job_id === current.job_id) ?? null;
    });
  }, [jobs]);

  const table = useReactTable({
    columns,
    data: jobs,
    getCoreRowModel: getCoreRowModel()
  });
  const rows = table.getRowModel().rows;
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    estimateSize: () => 58,
    getScrollElement: () => scrollRef.current,
    overscan: 8
  });
  const virtualItems = rowVirtualizer.getVirtualItems();
  const visibleRows = virtualItems.length
    ? virtualItems.map((item) => ({ fallbackIndex: item.index, item, row: rows[item.index] }))
    : rows.map((row, index) => ({ item: null, row, fallbackIndex: index }));

  const pageCount = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  const canGoBack = page > 0;
  const canGoForward = page + 1 < pageCount;

  const invalidateDashboardData = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["stats"] }),
      queryClient.invalidateQueries({ queryKey: ["distribution"] }),
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] })
    ]);
  const mutationFailure = (error: Error) => {
    setMutationError(error.message || "Dashboard command failed");
  };
  const bookmarkMutation = useMutation({
    mutationFn: (job: JobRecord) => setBookmarked(job.job_id, !job.bookmarked),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: invalidateDashboardData
  });
  const appliedMutation = useMutation({
    mutationFn: (job: JobRecord) => setApplied(job.job_id, !job.applied),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: invalidateDashboardData
  });
  const blacklistMutation = useMutation({
    mutationFn: (jobIds: string[]) => blacklistJobs(jobIds),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: () => {
      setSelectedIds(new Set());
      return invalidateDashboardData();
    }
  });

  const toggleSelected = (jobId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  };

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Jobs">
      <Card className="border border-slate-200 shadow-sm" variant="default">
        <div className="flex flex-wrap items-end gap-3 p-4">
          <label className="grid min-w-72 flex-1 gap-1 text-sm font-medium text-slate-700">
            <span>Search</span>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-slate-400"
                size={16}
              />
              <Input
                aria-label="Search jobs"
                className="pl-9"
                fullWidth
                onChange={(event) => setText(event.target.value)}
                placeholder="Search title, company, location"
                value={text}
                variant="secondary"
              />
            </div>
          </label>
          <label className="grid min-w-36 gap-1 text-sm font-medium text-slate-700">
            <span>Minimum score</span>
            <Input
              aria-label="Minimum score"
              max="100"
              min="0"
              onChange={(event) => setMinScore(event.target.value)}
              type="number"
              value={minScore}
              variant="secondary"
            />
          </label>
          <label className="grid min-w-36 gap-1 text-sm font-medium text-slate-700">
            <span>Site</span>
            <Input
              aria-label="Site"
              onChange={(event) => setSite(event.target.value)}
              value={site}
              variant="secondary"
            />
          </label>
          <label className="grid min-w-36 gap-1 text-sm font-medium text-slate-700">
            <span>Status</span>
            <select
              aria-label="Status"
              className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 shadow-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
              onChange={(event) => setStatus(event.target.value as StatusFilter)}
              value={status}
            >
              <option value="all">All</option>
              <option value="open">Open</option>
              <option value="bookmarked">Saved</option>
              <option value="applied">Applied</option>
            </select>
          </label>
          <label className="flex h-10 items-center gap-2 text-sm font-semibold text-slate-700">
            <input
              checked={remoteOnly}
              className="size-4 accent-emerald-700"
              onChange={(event) => setRemoteOnly(event.target.checked)}
              type="checkbox"
            />
            Remote
          </label>
          <Chip color="default" size="sm" variant="soft">
            {data?.total ?? 0} jobs
          </Chip>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Button isDisabled={jobs.length === 0} onPress={() => exportJobsCsv(jobs)} variant="outline">
            <Download aria-hidden="true" size={16} />
            Export CSV
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || blacklistMutation.isPending}
            onPress={() => blacklistMutation.mutate([...selectedIds])}
            variant="danger"
          >
            <Trash2 aria-hidden="true" size={16} />
            Blacklist selected
          </Button>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-600" aria-label="Pagination">
          <Button isDisabled={!canGoBack || isLoading} onPress={() => setPage((value) => value - 1)} variant="outline">
            Previous page
          </Button>
          <span className="min-w-24 text-center">
            Page {page + 1} of {pageCount}
          </span>
          <Button
            isDisabled={!canGoForward || isLoading}
            onPress={() => setPage((value) => value + 1)}
            variant="outline"
          >
            Next page
          </Button>
        </div>
      </div>

      {mutationError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          {mutationError}
        </div>
      ) : null}

      <div className={selectedJob ? "grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]" : "grid gap-4"}>
        <Card className="overflow-hidden border border-slate-200 shadow-sm" variant="default">
          <div className="overflow-x-auto">
            <div
              className={`${JOB_GRID_CLASS} min-w-[980px] border-b border-slate-200 bg-slate-100 py-3 text-xs font-bold uppercase text-slate-500`}
              role="row"
            >
              <span />
              <span>Score</span>
              <span>Role</span>
              <span>Company</span>
              <span>Site</span>
              <span>Status</span>
              <span>Actions</span>
            </div>

            {isLoading ? <div className="px-4 py-5 text-sm text-slate-500">Loading jobs</div> : null}
            {isError ? <div className="px-4 py-5 text-sm text-red-700">Unable to load jobs</div> : null}

            <div className="max-h-[min(62vh,720px)] overflow-auto" ref={scrollRef}>
              <div
                className="relative min-w-[980px]"
                style={{ height: virtualItems.length ? rowVirtualizer.getTotalSize() : "auto" }}
              >
                {visibleRows.map(({ item, row, fallbackIndex }) => {
                  const job = row.original;
                  const top = item?.start ?? (fallbackIndex ?? 0) * 58;
                  return (
                    <div
                      className={`${JOB_GRID_CLASS} min-h-[58px] w-full border-b border-slate-100 bg-white text-sm text-slate-900 hover:bg-slate-50`}
                      key={job.job_id}
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
                      <label className="flex items-center">
                        <input
                          aria-label={`Select ${job.title}`}
                          checked={selectedIds.has(job.job_id)}
                          className="size-4 accent-emerald-700"
                          onChange={() => toggleSelected(job.job_id)}
                          type="checkbox"
                        />
                      </label>
                      <Chip color={scoreColor(job.relevance_score)} size="sm" variant="soft">
                        {job.relevance_score}
                      </Chip>
                      <button
                        aria-label={`View ${job.title} details`}
                        className="grid gap-0.5 text-left"
                        onClick={() => setSelectedJob(job)}
                        type="button"
                      >
                        <span className="font-semibold text-slate-950">{job.title}</span>
                        <small className="text-xs text-slate-500">{job.location}</small>
                      </button>
                      <span className="truncate">{job.company}</span>
                      <span className="truncate">{job.site ?? "unknown"}</span>
                      <span className="flex items-center gap-2">{statusChip(job)}</span>
                      <span className="flex items-center gap-1.5">
                        <Button
                          aria-label={`${job.bookmarked ? "Unsave" : "Save"} ${job.title}`}
                          isDisabled={bookmarkMutation.isPending}
                          isIconOnly
                          onPress={() => bookmarkMutation.mutate(job)}
                          variant="outline"
                        >
                          <Bookmark aria-hidden="true" size={16} />
                        </Button>
                        <Button
                          aria-label={`Mark ${job.title} ${job.applied ? "not applied" : "applied"}`}
                          isDisabled={appliedMutation.isPending}
                          isIconOnly
                          onPress={() => appliedMutation.mutate(job)}
                          variant="outline"
                        >
                          <Check aria-hidden="true" size={16} />
                        </Button>
                        <Button
                          aria-label={`Open ${job.title} details`}
                          isIconOnly
                          onPress={() => setSelectedJob(job)}
                          variant="outline"
                        >
                          <PanelRightOpen aria-hidden="true" size={16} />
                        </Button>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </Card>

        {selectedJob ? (
          <Card aria-label="Job detail" className="self-start border border-slate-200 shadow-sm" variant="default">
            <div className="grid gap-4 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold leading-snug text-slate-950">{selectedJob.title}</h2>
                  <p className="mt-1 text-sm text-slate-500">{selectedJob.company}</p>
                </div>
                <Button aria-label="Close details" isIconOnly onPress={() => setSelectedJob(null)} variant="outline">
                  <X aria-hidden="true" size={16} />
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                <Chip color={scoreColor(selectedJob.relevance_score)} size="sm" variant="soft">
                  {selectedJob.relevance_score}
                </Chip>
                <span>{selectedJob.location}</span>
                <span>{selectedJob.site ?? "unknown"}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {selectedJob.description ?? "No description available."}
              </p>
              {selectedJob.job_url ? (
                <a
                  className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
                  href={selectedJob.job_url}
                >
                  <ExternalLink aria-hidden="true" size={16} />
                  Open job
                </a>
              ) : null}
            </div>
          </Card>
        ) : null}
      </div>
    </section>
  );
}
