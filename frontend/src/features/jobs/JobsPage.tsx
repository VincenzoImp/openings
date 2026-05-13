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

import {
  blacklistJobs,
  deleteJobs,
  exportJobs,
  getFacets,
  setApplied,
  setBookmarked
} from "../../api/client";
import type { JobListParams, JobRecord } from "../../api/types";
import { jobsQuery } from "./jobQueries";

type JobsPagePreset = "all" | "saved" | "applied";
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

function salaryLabel(job: JobRecord) {
  if (job.min_amount === null && job.max_amount === null) {
    return "unknown";
  }
  const currency = job.currency ?? "";
  const min = job.min_amount !== null ? `${currency} ${job.min_amount.toLocaleString()}` : "";
  const max = job.max_amount !== null ? `${currency} ${job.max_amount.toLocaleString()}` : "";
  return [min, max].filter(Boolean).join(" - ");
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-2">
      <span className="text-xs font-bold uppercase text-slate-500">{label}</span>
      <span className="truncate text-slate-800">{value}</span>
    </div>
  );
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function JobsPage({ preset = "all" }: { preset?: JobsPagePreset }) {
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [site, setSite] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [jobType, setJobType] = useState("");
  const [minSalary, setMinSalary] = useState("");
  const [maxSalary, setMaxSalary] = useState("");
  const [datePostedFrom, setDatePostedFrom] = useState("");
  const [datePostedTo, setDatePostedTo] = useState("");
  const [sort, setSort] = useState<JobListParams["sort"]>("score");
  const [status, setStatus] = useState<StatusFilter>(
    preset === "saved" ? "bookmarked" : preset === "applied" ? "applied" : "all"
  );
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const filterKey = useMemo(
    () =>
      JSON.stringify({
        company,
        datePostedFrom,
        datePostedTo,
        jobType,
        location,
        maxSalary,
        maxScore,
        minSalary,
        minScore,
        preset,
        remoteOnly,
        site,
        sort,
        status,
        text
      }),
    [
      company,
      datePostedFrom,
      datePostedTo,
      jobType,
      location,
      maxSalary,
      maxScore,
      minSalary,
      minScore,
      preset,
      remoteOnly,
      site,
      sort,
      status,
      text
    ]
  );

  useEffect(() => {
    setStatus(preset === "saved" ? "bookmarked" : preset === "applied" ? "applied" : "all");
  }, [preset]);

  useEffect(() => {
    setPage(0);
    setSelectedIds(new Set());
    setSelectedJob(null);
  }, [filterKey]);

  useEffect(() => {
    setSelectedIds(new Set());
    setSelectedJob(null);
  }, [page]);

  const params = useMemo<JobListParams>(
    () => ({
      applied: status === "applied" ? true : status === "open" ? false : undefined,
      bookmarked: status === "bookmarked" ? true : status === "open" ? false : undefined,
      company: company || undefined,
      date_posted_from: datePostedFrom || undefined,
      date_posted_to: datePostedTo || undefined,
      job_types: jobType ? [jobType] : undefined,
      limit: PAGE_SIZE,
      location: location || undefined,
      max_salary: maxSalary ? Number(maxSalary) : undefined,
      max_score: maxScore ? Number(maxScore) : undefined,
      min_salary: minSalary ? Number(minSalary) : undefined,
      min_score: minScore ? Number(minScore) : undefined,
      offset: page * PAGE_SIZE,
      remote: remoteOnly ? true : undefined,
      sites: site ? [site] : undefined,
      sort,
      text: text || undefined
    }),
    [
      company,
      datePostedFrom,
      datePostedTo,
      jobType,
      location,
      maxSalary,
      maxScore,
      minSalary,
      minScore,
      page,
      remoteOnly,
      site,
      sort,
      status,
      text
    ]
  );

  const { data, isLoading, isError } = useQuery(jobsQuery(params));
  const facets = useQuery({
    queryKey: ["job-facets"],
    queryFn: getFacets,
    staleTime: 60_000
  });
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
      queryClient.invalidateQueries({ queryKey: ["cleanup-preview"] }),
      queryClient.invalidateQueries({ queryKey: ["blacklist"] }),
      queryClient.invalidateQueries({ queryKey: ["job-facets"] })
    ]);
  const mutationFailure = (error: Error) => {
    setMutationError(error.message || "Dashboard command failed");
  };
  const bookmarkMutation = useMutation({
    mutationFn: (job: JobRecord) => setBookmarked([job.job_id], !job.bookmarked),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: invalidateDashboardData
  });
  const appliedMutation = useMutation({
    mutationFn: (job: JobRecord) => setApplied([job.job_id], !job.applied),
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
  const deleteMutation = useMutation({
    mutationFn: (jobIds: string[]) => deleteJobs(jobIds),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: () => {
      setSelectedIds(new Set());
      return invalidateDashboardData();
    }
  });
  const bulkBookmarkMutation = useMutation({
    mutationFn: ({ jobIds, value }: { jobIds: string[]; value: boolean }) =>
      setBookmarked(jobIds, value),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: invalidateDashboardData
  });
  const bulkAppliedMutation = useMutation({
    mutationFn: ({ jobIds, value }: { jobIds: string[]; value: boolean }) => setApplied(jobIds, value),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: invalidateDashboardData
  });
  const exportMutation = useMutation({
    mutationFn: (payload: { jobIds?: string[] }) =>
      exportJobs(
        payload.jobIds?.length
          ? { format: "csv", job_ids: payload.jobIds }
          : { filters: params, format: "csv" }
      ),
    onError: mutationFailure,
    onMutate: () => setMutationError(null),
    onSuccess: (blob) => saveBlob(blob, "jobs.csv")
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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-zinc-950">
            {preset === "saved" ? "Saved jobs" : preset === "applied" ? "Applied jobs" : "Jobs"}
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            {data?.total ?? 0} active records, {selectedIds.size} selected
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(facets.data?.sites ?? []).slice(0, 4).map((facet) => (
            <Chip key={String(facet.value)} color="default" size="sm" variant="soft">
              {String(facet.value)} {facet.count}
            </Chip>
          ))}
        </div>
      </div>

      <Card className="border border-zinc-200 shadow-sm" variant="default">
        <div className="grid gap-3 p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(240px,2fr)_repeat(4,minmax(120px,1fr))]">
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Search</span>
            <div className="relative">
              <Search
                aria-hidden="true"
                  className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-zinc-400"
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
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Company</span>
              <Input
                aria-label="Company"
                onChange={(event) => setCompany(event.target.value)}
                value={company}
                variant="secondary"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Location</span>
              <Input
                aria-label="Location"
                onChange={(event) => setLocation(event.target.value)}
                value={location}
                variant="secondary"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Site</span>
              <Input
                aria-label="Site"
                list="job-sites"
                onChange={(event) => setSite(event.target.value)}
                value={site}
                variant="secondary"
              />
              <datalist id="job-sites">
                {(facets.data?.sites ?? []).map((facet) => (
                  <option key={String(facet.value)} value={String(facet.value)} />
                ))}
              </datalist>
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Job type</span>
              <Input
                aria-label="Job type"
                list="job-types"
                onChange={(event) => setJobType(event.target.value)}
                value={jobType}
                variant="secondary"
              />
              <datalist id="job-types">
                {(facets.data?.job_types ?? []).map((facet) => (
                  <option key={String(facet.value)} value={String(facet.value)} />
                ))}
              </datalist>
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-8">
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Min score</span>
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
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Max score</span>
            <Input
                aria-label="Maximum score"
                max="100"
                min="0"
                onChange={(event) => setMaxScore(event.target.value)}
                type="number"
                value={maxScore}
              variant="secondary"
            />
          </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Min salary</span>
              <Input
                aria-label="Minimum salary"
                min="0"
                onChange={(event) => setMinSalary(event.target.value)}
                type="number"
                value={minSalary}
                variant="secondary"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Max salary</span>
              <Input
                aria-label="Maximum salary"
                min="0"
                onChange={(event) => setMaxSalary(event.target.value)}
                type="number"
                value={maxSalary}
                variant="secondary"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Posted from</span>
              <Input
                aria-label="Date posted from"
                onChange={(event) => setDatePostedFrom(event.target.value)}
                type="date"
                value={datePostedFrom}
                variant="secondary"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Posted to</span>
              <Input
                aria-label="Date posted to"
                onChange={(event) => setDatePostedTo(event.target.value)}
                type="date"
                value={datePostedTo}
                variant="secondary"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
            <span>Status</span>
            <select
              aria-label="Status"
                className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-zinc-100"
              onChange={(event) => setStatus(event.target.value as StatusFilter)}
              value={status}
            >
              <option value="all">All</option>
              <option value="open">Open</option>
              <option value="bookmarked">Saved</option>
              <option value="applied">Applied</option>
            </select>
          </label>
            <label className="grid gap-1 text-sm font-medium text-zinc-700">
              <span>Sort</span>
              <select
                aria-label="Sort"
                className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-zinc-100"
                onChange={(event) => setSort(event.target.value as JobListParams["sort"])}
                value={sort}
              >
                <option value="score">Score</option>
                <option value="date">Date</option>
                <option value="company">Company</option>
                <option value="title">Title</option>
                <option value="salary">Salary</option>
              </select>
            </label>
          </div>
          <label className="flex h-10 items-center gap-2 text-sm font-semibold text-zinc-700">
            <input
              checked={remoteOnly}
              className="size-4 accent-zinc-950"
              onChange={(event) => setRemoteOnly(event.target.checked)}
              type="checkbox"
            />
            Remote
          </label>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Button
            isDisabled={exportMutation.isPending || jobs.length === 0}
            onPress={() => exportMutation.mutate({})}
            variant="outline"
          >
            <Download aria-hidden="true" size={16} />
            Export filtered
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || exportMutation.isPending}
            onPress={() => exportMutation.mutate({ jobIds: [...selectedIds] })}
            variant="outline"
          >
            <Download aria-hidden="true" size={16} />
            Export selected
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || bulkBookmarkMutation.isPending}
            onPress={() => bulkBookmarkMutation.mutate({ jobIds: [...selectedIds], value: true })}
            variant="outline"
          >
            <Bookmark aria-hidden="true" size={16} />
            Save selected
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || bulkBookmarkMutation.isPending}
            onPress={() => bulkBookmarkMutation.mutate({ jobIds: [...selectedIds], value: false })}
            variant="outline"
          >
            <Bookmark aria-hidden="true" size={16} />
            Unsave selected
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || bulkAppliedMutation.isPending}
            onPress={() => bulkAppliedMutation.mutate({ jobIds: [...selectedIds], value: true })}
            variant="outline"
          >
            <Check aria-hidden="true" size={16} />
            Mark applied
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || bulkAppliedMutation.isPending}
            onPress={() => bulkAppliedMutation.mutate({ jobIds: [...selectedIds], value: false })}
            variant="outline"
          >
            <Check aria-hidden="true" size={16} />
            Mark not applied
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || blacklistMutation.isPending}
            onPress={() => blacklistMutation.mutate([...selectedIds])}
            variant="danger"
          >
            <Trash2 aria-hidden="true" size={16} />
            Blacklist selected
          </Button>
          <Button
            isDisabled={selectedIds.size === 0 || deleteMutation.isPending}
            onPress={() => deleteMutation.mutate([...selectedIds])}
            variant="danger"
          >
            <X aria-hidden="true" size={16} />
            Delete selected
          </Button>
        </div>
        <div className="flex items-center gap-2 text-sm text-zinc-600" aria-label="Pagination">
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
              <div className="grid gap-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <Meta label="Salary" value={salaryLabel(selectedJob)} />
                <Meta label="Type" value={selectedJob.job_type ?? "unknown"} />
                <Meta label="Remote" value={selectedJob.is_remote ? "Yes" : "No"} />
                <Meta label="Date posted" value={selectedJob.date_posted ?? "unknown"} />
                <Meta label="First seen" value={selectedJob.first_seen ?? "unknown"} />
                <Meta label="Last seen" value={selectedJob.last_seen ?? "unknown"} />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  isDisabled={bookmarkMutation.isPending}
                  onPress={() => bookmarkMutation.mutate(selectedJob)}
                  variant="outline"
                >
                  <Bookmark aria-hidden="true" size={16} />
                  {selectedJob.bookmarked ? "Unsave" : "Save"}
                </Button>
                <Button
                  isDisabled={appliedMutation.isPending}
                  onPress={() => appliedMutation.mutate(selectedJob)}
                  variant="outline"
                >
                  <Check aria-hidden="true" size={16} />
                  {selectedJob.applied ? "Mark not applied" : "Mark applied"}
                </Button>
                <Button
                  isDisabled={blacklistMutation.isPending}
                  onPress={() => blacklistMutation.mutate([selectedJob.job_id])}
                  variant="danger"
                >
                  <Trash2 aria-hidden="true" size={16} />
                  Blacklist
                </Button>
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
