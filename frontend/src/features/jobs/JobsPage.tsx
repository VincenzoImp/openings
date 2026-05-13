import { Button, Card, CardContent, Chip, Input } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  blacklistJobs,
  deleteJobs,
  exportJobs,
  getFacets,
  searchSimilarJobs,
  setApplied,
  setBookmarked
} from "../../api/client";
import type { ExportFormat, JobRecord, SemanticJobResult } from "../../api/types";
import { AlertBanner } from "../../components/AlertBanner";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { PageHeader } from "../../components/PageHeader";
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
  | { action: "blacklist"; jobIds: string[]; jobTitle?: string }
  | { action: "delete"; jobIds: string[]; jobTitle?: string };

const DEFAULT_PAGE_SIZE = 100;

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
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const [pendingCommand, setPendingCommand] = useState<PendingCommand | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("csv");
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState<SemanticJobResult[]>([]);

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

  const params = useMemo(() => buildJobListParams(filters, page, pageSize), [filters, page, pageSize]);

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

    const lastPage = Math.max(0, Math.ceil(data.total / pageSize) - 1);
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [data?.total, page, pageSize]);

  useEffect(() => {
    setSelectedJob((current) => {
      if (!current) {
        return null;
      }
      return jobs.find((job) => job.job_id === current.job_id) ?? null;
    });
  }, [jobs]);

  const pageCount = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));
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
          ? { format: exportFormat, job_ids: payload.jobIds }
          : { filters: params, format: exportFormat }
      ),
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: (blob) => {
      saveBlob(blob, `jobs.${exportFormat}`);
      commandSuccess("Export generated.");
    }
  });
  const semanticMutation = useMutation({
    mutationFn: searchSimilarJobs,
    onError: mutationFailure,
    onMutate: () => {
      setMutationError(null);
      setMutationMessage(null);
    },
    onSuccess: (results) => {
      setSemanticResults(results);
      commandSuccess("Semantic search completed.");
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

  const updatePageSize = (nextPageSize: number) => {
    setPageSize(nextPageSize);
    setPage(0);
    setSelectedIds(new Set());
    setSelectedJob(null);
  };

  const requestCommand = (action: PendingCommand["action"], jobIds: string[], jobTitle?: string) => {
    setPendingCommand({ action, jobIds, jobTitle });
  };

  const runSemanticSearch = () => {
    const q = semanticQuery.trim();
    if (!q) {
      return;
    }
    semanticMutation.mutate({
      min_score: filters.minScore ? Number(filters.minScore) : undefined,
      n_results: 10,
      q,
      site: filters.site || undefined
    });
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
      ? pendingCommand.jobTitle
        ? `Blacklist ${pendingCommand.jobTitle}?`
        : "Blacklist selected jobs?"
      : pendingCommand?.jobTitle
        ? `Delete ${pendingCommand.jobTitle} permanently?`
        : "Delete selected jobs permanently?";
  const pendingDescription =
    pendingCommand?.action === "blacklist"
      ? "Blacklisting removes these active jobs and blocks matching jobs from being imported again."
      : "Permanent delete removes these active jobs without adding them to the blacklist. They can be rediscovered in a future search.";

  return (
    <section className="mx-auto grid max-w-[1500px] gap-4" aria-label="Jobs">
      <PageHeader
        chips={(facets.data?.sites ?? []).slice(0, 4).map((facet) => (
          <Chip key={String(facet.value)} color="default" size="sm" variant="soft">
            {String(facet.value)} {facet.count}
          </Chip>
        ))}
        description={`${data?.total ?? 0} active records, ${selectedIds.size} selected`}
        title="Jobs"
      />

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

      <Card className="border border-zinc-200 bg-white shadow-sm" variant="default">
        <CardContent className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <label className="grid gap-1.5 text-sm font-medium text-zinc-700">
            <span>Semantic search</span>
            <Input
              aria-label="Semantic search"
              onChange={(event) => setSemanticQuery(event.target.value)}
              placeholder="Find jobs similar to a role, stack, or responsibility"
              value={semanticQuery}
              variant="secondary"
            />
          </label>
          <Button
            isDisabled={!semanticQuery.trim() || semanticMutation.isPending}
            onPress={runSemanticSearch}
            variant="primary"
          >
            Search similar jobs
          </Button>
          {semanticResults.length > 0 ? (
            <div className="grid gap-2 md:col-span-2">
              {semanticResults.slice(0, 5).map((result) => (
                <button
                  className="grid gap-1 rounded-md border border-zinc-200 px-3 py-2 text-left text-sm hover:bg-zinc-50"
                  key={result.job_id}
                  onClick={() => {
                    const match = jobs.find((job) => job.job_id === result.job_id);
                    if (match) {
                      setSelectedJob(match);
                    }
                  }}
                  type="button"
                >
                  <span className="font-semibold text-zinc-950">{result.title ?? result.job_id}</span>
                  <span className="text-xs text-zinc-500">
                    {Math.round(result.similarity * 100)}% match
                    {result.company ? ` / ${result.company}` : ""}
                    {result.site ? ` / ${result.site}` : ""}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <JobActionsBar
        canGoBack={canGoBack}
        canGoForward={canGoForward}
        exportFormat={exportFormat}
        isAppliedPending={bulkAppliedMutation.isPending}
        isBlacklistPending={blacklistMutation.isPending}
        isBookmarkPending={bulkBookmarkMutation.isPending}
        isDeletePending={deleteMutation.isPending}
        isExportPending={exportMutation.isPending}
        isLoading={isLoading}
        jobsCount={jobs.length}
        onBlacklistSelected={() => requestCommand("blacklist", [...selectedIds])}
        onDeleteSelected={() => requestCommand("delete", [...selectedIds])}
        onExportFiltered={() => exportMutation.mutate({})}
        onExportFormatChange={setExportFormat}
        onExportSelected={() => exportMutation.mutate({ jobIds: [...selectedIds] })}
        onMarkAppliedSelected={() => bulkAppliedMutation.mutate({ jobIds: [...selectedIds], value: true })}
        onMarkNotAppliedSelected={() => bulkAppliedMutation.mutate({ jobIds: [...selectedIds], value: false })}
        onNextPage={() => setPage((value) => value + 1)}
        onPageSizeChange={updatePageSize}
        onPreviousPage={() => setPage((value) => value - 1)}
        onSaveSelected={() => bulkBookmarkMutation.mutate({ jobIds: [...selectedIds], value: true })}
        onUnsaveSelected={() => bulkBookmarkMutation.mutate({ jobIds: [...selectedIds], value: false })}
        page={page}
        pageCount={pageCount}
        pageSize={pageSize}
        selectedCount={selectedIds.size}
      />

      {mutationError ? (
        <AlertBanner kind="danger">{mutationError}</AlertBanner>
      ) : null}
      {mutationMessage ? (
        <AlertBanner kind="success">{mutationMessage}</AlertBanner>
      ) : null}

      <div className={selectedJob ? "grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]" : "grid gap-4"}>
        <JobTable
          isAppliedPending={appliedMutation.isPending}
          isBlacklistPending={blacklistMutation.isPending}
          isBookmarkPending={bookmarkMutation.isPending}
          isDeletePending={deleteMutation.isPending}
          isError={isError}
          isLoading={isLoading}
          jobs={jobs}
          onBlacklistJob={(job) => requestCommand("blacklist", [job.job_id], job.title)}
          onDeleteJob={(job) => requestCommand("delete", [job.job_id], job.title)}
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
            onBlacklist={(job) => requestCommand("blacklist", [job.job_id], job.title)}
            onClose={() => setSelectedJob(null)}
            onDelete={(job) => requestCommand("delete", [job.job_id], job.title)}
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
