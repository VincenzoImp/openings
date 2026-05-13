import { Chip } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  blacklistJobs,
  deleteJobs,
  exportJobs,
  getFacets,
  setApplied,
  setBookmarked
} from "../../api/client";
import type { JobRecord } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { JobActionsBar } from "./JobActionsBar";
import { JobDetailPanel } from "./JobDetailPanel";
import { JobFiltersPanel } from "./JobFiltersPanel";
import { JobTable } from "./JobTable";
import {
  buildJobListParams,
  DEFAULT_JOB_FILTERS,
  jobFilterKey,
  type JobFilterValues
} from "./jobFilters";
import { jobsQuery } from "./jobQueries";

type PendingCommand =
  | { action: "blacklist"; jobIds: string[] }
  | { action: "delete"; jobIds: string[] };

const PAGE_SIZE = 100;

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function JobsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<JobFilterValues>(DEFAULT_JOB_FILTERS);
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const [pendingCommand, setPendingCommand] = useState<PendingCommand | null>(null);

  const filterKey = useMemo(() => jobFilterKey(filters), [filters]);

  useEffect(() => {
    setPage(0);
    setSelectedIds(new Set());
    setSelectedJob(null);
  }, [filterKey]);

  useEffect(() => {
    setSelectedIds(new Set());
    setSelectedJob(null);
  }, [page]);

  const params = useMemo(() => buildJobListParams(filters, page, PAGE_SIZE), [filters, page]);

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
    setMutationMessage(null);
    setMutationError(error.message || "Dashboard command failed");
  };
  const commandSuccess = (message: string) => {
    setMutationError(null);
    setMutationMessage(message);
  };
  const bookmarkMutation = useMutation({
    mutationFn: (job: JobRecord) => setBookmarked([job.job_id], !job.bookmarked),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: () => {
      commandSuccess("Job state updated.");
      return invalidateDashboardData();
    }
  });
  const appliedMutation = useMutation({
    mutationFn: (job: JobRecord) => setApplied([job.job_id], !job.applied),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: () => {
      commandSuccess("Job state updated.");
      return invalidateDashboardData();
    }
  });
  const blacklistMutation = useMutation({
    mutationFn: (jobIds: string[]) => blacklistJobs(jobIds),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: () => {
      commandSuccess("Selected jobs were blacklisted.");
      setPendingCommand(null);
      setSelectedIds(new Set());
      setSelectedJob(null);
      return invalidateDashboardData();
    }
  });
  const deleteMutation = useMutation({
    mutationFn: (jobIds: string[]) => deleteJobs(jobIds),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: () => {
      commandSuccess("Selected jobs were permanently deleted.");
      setPendingCommand(null);
      setSelectedIds(new Set());
      setSelectedJob(null);
      return invalidateDashboardData();
    }
  });
  const bulkBookmarkMutation = useMutation({
    mutationFn: ({ jobIds, value }: { jobIds: string[]; value: boolean }) =>
      setBookmarked(jobIds, value),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: () => {
      commandSuccess("Selected jobs were updated.");
      return invalidateDashboardData();
    }
  });
  const bulkAppliedMutation = useMutation({
    mutationFn: ({ jobIds, value }: { jobIds: string[]; value: boolean }) => setApplied(jobIds, value),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: () => {
      commandSuccess("Selected jobs were updated.");
      return invalidateDashboardData();
    }
  });
  const exportMutation = useMutation({
    mutationFn: (payload: { jobIds?: string[] }) =>
      exportJobs(
        payload.jobIds?.length
          ? { format: "csv", job_ids: payload.jobIds }
          : { filters: params, format: "csv" }
      ),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: (blob) => {
      saveBlob(blob, "jobs.csv");
      commandSuccess("Export generated.");
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

  const updateFilters = (patch: Partial<JobFilterValues>) => {
    setFilters((current) => ({ ...current, ...patch }));
  };

  const resetFilters = () => {
    setFilters(DEFAULT_JOB_FILTERS);
    setPage(0);
    setSelectedIds(new Set());
    setSelectedJob(null);
    setMutationError(null);
    setMutationMessage(null);
  };

  const confirmPendingCommand = () => {
    if (!pendingCommand) {
      return;
    }
    if (pendingCommand.action === "blacklist") {
      blacklistMutation.mutate(pendingCommand.jobIds);
    } else {
      deleteMutation.mutate(pendingCommand.jobIds);
    }
  };

  const pendingTitle =
    pendingCommand?.action === "blacklist"
      ? "Blacklist selected jobs?"
      : "Delete selected jobs permanently?";
  const pendingDescription =
    pendingCommand?.action === "blacklist"
      ? "Blacklisting removes these active jobs and blocks matching jobs from being imported again."
      : "Permanent delete removes these active jobs without adding them to the blacklist. They can be rediscovered in a future search.";

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Jobs">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-zinc-950">Jobs</h2>
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

      <JobFiltersPanel
        facets={facets.data}
        filters={filters}
        onChange={updateFilters}
        onClearSelection={() => setSelectedIds(new Set())}
        onReset={resetFilters}
        onSelectVisible={() => setSelectedIds(new Set(jobs.map((job) => job.job_id)))}
        selectedCount={selectedIds.size}
        visibleJobs={jobs}
      />

      <JobActionsBar
        canGoBack={canGoBack}
        canGoForward={canGoForward}
        isAppliedPending={bulkAppliedMutation.isPending}
        isBlacklistPending={blacklistMutation.isPending}
        isBookmarkPending={bulkBookmarkMutation.isPending}
        isDeletePending={deleteMutation.isPending}
        isExportPending={exportMutation.isPending}
        isLoading={isLoading}
        jobsCount={jobs.length}
        onBlacklistSelected={() => setPendingCommand({ action: "blacklist", jobIds: [...selectedIds] })}
        onDeleteSelected={() => setPendingCommand({ action: "delete", jobIds: [...selectedIds] })}
        onExportFiltered={() => exportMutation.mutate({})}
        onExportSelected={() => exportMutation.mutate({ jobIds: [...selectedIds] })}
        onMarkAppliedSelected={() => bulkAppliedMutation.mutate({ jobIds: [...selectedIds], value: true })}
        onMarkNotAppliedSelected={() => bulkAppliedMutation.mutate({ jobIds: [...selectedIds], value: false })}
        onNextPage={() => setPage((value) => value + 1)}
        onPreviousPage={() => setPage((value) => value - 1)}
        onSaveSelected={() => bulkBookmarkMutation.mutate({ jobIds: [...selectedIds], value: true })}
        onUnsaveSelected={() => bulkBookmarkMutation.mutate({ jobIds: [...selectedIds], value: false })}
        page={page}
        pageCount={pageCount}
        selectedCount={selectedIds.size}
      />

      {mutationError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          {mutationError}
        </div>
      ) : null}
      {mutationMessage ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">
          {mutationMessage}
        </div>
      ) : null}

      <div className={selectedJob ? "grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]" : "grid gap-4"}>
        <JobTable
          isAppliedPending={appliedMutation.isPending}
          isBookmarkPending={bookmarkMutation.isPending}
          isError={isError}
          isLoading={isLoading}
          jobs={jobs}
          onSelectJob={setSelectedJob}
          onToggleApplied={(job) => appliedMutation.mutate(job)}
          onToggleBookmarked={(job) => bookmarkMutation.mutate(job)}
          onToggleSelected={toggleSelected}
          selectedIds={selectedIds}
        />

        {selectedJob ? (
          <JobDetailPanel
            isAppliedPending={appliedMutation.isPending}
            isBlacklistPending={blacklistMutation.isPending}
            isBookmarkPending={bookmarkMutation.isPending}
            job={selectedJob}
            onBlacklist={(job) => setPendingCommand({ action: "blacklist", jobIds: [job.job_id] })}
            onClose={() => setSelectedJob(null)}
            onToggleApplied={(job) => appliedMutation.mutate(job)}
            onToggleBookmarked={(job) => bookmarkMutation.mutate(job)}
          />
        ) : null}
      </div>
      <ConfirmDialog
        confirmLabel={pendingCommand?.action === "blacklist" ? "Confirm blacklist" : "Confirm delete"}
        description={pendingDescription}
        isOpen={pendingCommand !== null}
        isPending={blacklistMutation.isPending || deleteMutation.isPending}
        onCancel={() => setPendingCommand(null)}
        onConfirm={confirmPendingCommand}
        title={pendingTitle}
      />
    </section>
  );
}
