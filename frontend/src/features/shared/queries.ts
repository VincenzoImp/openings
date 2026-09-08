import { useMemo } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type {
  AddJobRequest,
  AttachmentKind,
  JobListParams,
  JobListResponse,
  JobStatus,
  JobSummary,
  NoteKind,
  NoteRequest,
  PostingFields,
} from "../../api/types";
import { useToast } from "../../app/toastContext";
import { STATUS_LABELS } from "./labels";

/** Drop undefined/empty entries so equal filters share one cache entry. */
export function normalizeParams(params: JobListParams): JobListParams {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (Array.isArray(value) && value.length === 0) {
      continue;
    }
    out[key] = value;
  }
  return out as JobListParams;
}

export const keys = {
  auth: ["auth"] as const,
  jobs: (params: JobListParams) => ["jobs", "page", normalizeParams(params)] as const,
  jobsInfinite: (params: JobListParams) => ["jobs", "infinite", normalizeParams(params)] as const,
  job: (jobId: string) => ["job", jobId] as const,
  similar: (jobId: string) => ["similar", jobId] as const,
  stats: ["stats"] as const,
  facets: (params: { limit?: number; q?: string } = {}) => ["facets", params] as const,
  sources: ["sources"] as const,
  runs: (limit: number) => ["runs", limit] as const,
  runStatus: ["runs", "status"] as const,
  blacklist: (params: object) => ["blacklist", params] as const,
  distribution: (binSize: number) => ["distribution", binSize] as const,
  cleanupPreview: ["cleanup-preview"] as const,
  settings: ["settings"] as const,
  settingsReference: ["settings", "reference"] as const,
  labels: ["labels"] as const,
  attachments: (params: object) => ["attachments", params] as const,
  companyStatuses: (company: string) => ["company-statuses", company] as const,
};

export const PAGE_SIZE = 100;

export function useJobs(params: JobListParams, enabled = true) {
  return useQuery({ queryKey: keys.jobs(params), queryFn: () => api.listJobs(params), enabled });
}

/** Pages of jobs loaded on demand; `items` flattens every loaded page. */
export function useJobsInfinite(params: JobListParams, enabled = true) {
  const query = useInfiniteQuery({
    queryKey: keys.jobsInfinite(params),
    queryFn: ({ pageParam, signal }) =>
      api.listJobs({ ...params, limit: PAGE_SIZE, offset: pageParam }, signal),
    initialPageParam: 0,
    getNextPageParam: (last) => {
      const loaded = last.offset + last.items.length;
      return loaded < last.total && last.items.length > 0 ? loaded : undefined;
    },
    enabled,
  });
  const pages = query.data?.pages;
  const items = useMemo(() => pages?.flatMap((page) => page.items) ?? [], [pages]);
  const total = pages?.[0]?.total ?? 0;
  return { ...query, items, total };
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: keys.job(jobId ?? ""),
    queryFn: () => api.getJob(jobId as string),
    enabled: Boolean(jobId),
  });
}

export function useSimilar(jobId: string | null, enabled = true) {
  return useQuery({
    queryKey: keys.similar(jobId ?? ""),
    queryFn: () => api.similarJobs(jobId as string),
    enabled: Boolean(jobId) && enabled,
    retry: false,
  });
}

export function useStats() {
  return useQuery({ queryKey: keys.stats, queryFn: api.stats });
}

export function useFacets(params: { limit?: number; q?: string } = {}, enabled = true) {
  return useQuery({ queryKey: keys.facets(params), queryFn: () => api.facets(params), enabled });
}

export function useSources() {
  return useQuery({ queryKey: keys.sources, queryFn: api.listSources });
}

export function useRuns(limit = 30, refetchInterval: number | false = false) {
  return useQuery({
    queryKey: keys.runs(limit),
    queryFn: () => api.listRuns(limit),
    refetchInterval,
  });
}

export function useRunStatus(refetchInterval: number | false = false) {
  return useQuery({ queryKey: keys.runStatus, queryFn: api.runStatus, refetchInterval });
}

export function useBlacklist(params: { limit?: number; offset?: number; text?: string }) {
  return useQuery({
    queryKey: keys.blacklist(params),
    queryFn: () => api.listBlacklist(params),
  });
}

export function useDistribution(binSize: number) {
  return useQuery({
    queryKey: keys.distribution(binSize),
    queryFn: () => api.distribution(binSize),
  });
}

export function useCleanupPreview() {
  return useQuery({ queryKey: keys.cleanupPreview, queryFn: api.cleanupPreview });
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: api.settings });
}

export function useSettingsReference(enabled: boolean) {
  return useQuery({
    queryKey: keys.settingsReference,
    queryFn: api.settingsReference,
    enabled,
  });
}

export function useLabels() {
  return useQuery({ queryKey: keys.labels, queryFn: api.listLabels });
}

export function useCompanyStatuses(company: string | null) {
  return useQuery({
    queryKey: keys.companyStatuses(company ?? ""),
    queryFn: () => api.companyStatuses(company as string),
    enabled: Boolean(company),
  });
}

// ---------------------------------------------------------------------------
// Cache surgery for optimistic updates
// ---------------------------------------------------------------------------

type Lists = JobListResponse | InfiniteData<JobListResponse>;

function patchLists(
  client: QueryClient,
  jobIds: string[],
  patch: (job: JobSummary) => JobSummary | null,
): void {
  const wanted = new Set(jobIds);
  const apply = (page: JobListResponse): JobListResponse => {
    let removed = 0;
    const items = page.items.flatMap((job) => {
      if (!wanted.has(job.job_id)) {
        return [job];
      }
      const next = patch(job);
      if (next === null) {
        removed += 1;
        return [];
      }
      return [next];
    });
    return { ...page, items, total: Math.max(0, page.total - removed) };
  };
  client.setQueriesData<Lists>({ queryKey: ["jobs"] }, (data) => {
    if (!data) {
      return data;
    }
    if ("pages" in data) {
      return { ...data, pages: data.pages.map(apply) };
    }
    return apply(data);
  });
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Every job-level write, invalidating only what it can change. */
export function useJobCommands() {
  const client = useQueryClient();
  const toast = useToast();

  const invalidateLists = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ["jobs"] }),
      client.invalidateQueries({ queryKey: keys.stats }),
      client.invalidateQueries({ queryKey: ["blacklist"] }),
    ]);
  const invalidateJobs = (jobIds: string[]) =>
    Promise.all(jobIds.map((jobId) => client.invalidateQueries({ queryKey: keys.job(jobId) })));
  const invalidateFacets = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ["facets"] }),
      client.invalidateQueries({ queryKey: keys.labels }),
      client.invalidateQueries({ queryKey: keys.sources }),
      client.invalidateQueries({ queryKey: ["company-statuses"] }),
    ]);
  const onError = (error: unknown) => toast.push(describe(error), "error");

  const setStatus = useMutation({
    mutationFn: ({
      jobIds,
      status,
      note,
    }: {
      jobIds: string[];
      status: JobStatus;
      note?: string;
    }) => api.setStatus(jobIds, status, note),
    onMutate: async ({ jobIds, status }) => {
      await client.cancelQueries({ queryKey: ["jobs"] });
      const stamp = new Date().toISOString();
      patchLists(client, jobIds, (job) => ({ ...job, status, status_changed_at: stamp }));
    },
    onSuccess: (result, { jobIds, status }) => {
      toast.push(
        `${result.affected_count} moved to ${STATUS_LABELS[status]}`,
        result.affected_count ? "success" : "info",
      );
      return Promise.all([invalidateLists(), invalidateJobs(jobIds), invalidateFacets()]);
    },
    onError: (error) => {
      onError(error);
      return invalidateLists();
    },
  });

  const addLabels = useMutation({
    mutationFn: ({ jobIds, labels }: { jobIds: string[]; labels: string[] }) =>
      api.addLabels(jobIds, labels),
    onMutate: ({ jobIds, labels }) =>
      patchLists(client, jobIds, (job) => ({
        ...job,
        labels: Array.from(new Set([...job.labels, ...labels])).sort(),
      })),
    onSuccess: (_result, { jobIds }) =>
      Promise.all([invalidateLists(), invalidateJobs(jobIds), invalidateFacets()]),
    onError: (error) => {
      onError(error);
      return invalidateLists();
    },
  });

  const removeLabels = useMutation({
    mutationFn: ({ jobIds, labels }: { jobIds: string[]; labels: string[] }) =>
      api.removeLabels(jobIds, labels),
    onMutate: ({ jobIds, labels }) =>
      patchLists(client, jobIds, (job) => ({
        ...job,
        labels: job.labels.filter((label) => !labels.includes(label)),
      })),
    onSuccess: (_result, { jobIds }) =>
      Promise.all([invalidateLists(), invalidateJobs(jobIds), invalidateFacets()]),
    onError: (error) => {
      onError(error);
      return invalidateLists();
    },
  });

  const blacklist = useMutation({
    mutationFn: ({ jobIds, note }: { jobIds: string[]; note?: string }) =>
      api.blacklist(jobIds, note),
    onMutate: async ({ jobIds }) => {
      await client.cancelQueries({ queryKey: ["jobs"] });
      patchLists(client, jobIds, () => null);
    },
    onSuccess: (result, { jobIds }) => {
      toast.push(`${result.affected_count} blacklisted`, "success");
      return Promise.all([invalidateLists(), invalidateJobs(jobIds), invalidateFacets()]);
    },
    onError: (error) => {
      onError(error);
      return invalidateLists();
    },
  });

  const unblacklist = useMutation({
    mutationFn: (jobIds: string[]) => api.unblacklist(jobIds),
    onSuccess: (result, jobIds) => {
      toast.push(`${result.affected_count} restored`, "success");
      return Promise.all([invalidateLists(), invalidateJobs(jobIds), invalidateFacets()]);
    },
    onError,
  });

  const deleteJobs = useMutation({
    mutationFn: (jobIds: string[]) => api.deleteJobs(jobIds),
    onMutate: async (jobIds) => {
      await client.cancelQueries({ queryKey: ["jobs"] });
      patchLists(client, jobIds, () => null);
    },
    onSuccess: (result, jobIds) => {
      toast.push(`${result.affected_count} deleted`, "success");
      return Promise.all([invalidateLists(), invalidateJobs(jobIds), invalidateFacets()]);
    },
    onError: (error) => {
      onError(error);
      return invalidateLists();
    },
  });

  const addJob = useMutation({
    mutationFn: (payload: AddJobRequest) => api.addJob(payload),
    onSuccess: (result) => {
      toast.push(result.message === "created" ? "Posting added" : "Posting updated", "success");
      return Promise.all([invalidateLists(), invalidateJobs(result.job_ids), invalidateFacets()]);
    },
    onError,
  });

  const updateJob = useMutation({
    mutationFn: ({ jobId, fields }: { jobId: string; fields: PostingFields }) =>
      api.updateJob(jobId, fields),
    onSuccess: (detail) => {
      client.setQueryData(keys.job(detail.job_id), detail);
      toast.push("Posting saved", "success");
      return Promise.all([invalidateLists(), invalidateFacets()]);
    },
    onError,
  });

  const mergeJobs = useMutation({
    mutationFn: ({ primaryId, otherIds }: { primaryId: string; otherIds: string[] }) =>
      api.mergeJobs(primaryId, otherIds),
    onSuccess: (result, { primaryId, otherIds }) => {
      toast.push(`${result.affected_count} merged`, "success");
      return Promise.all([invalidateLists(), invalidateJobs([primaryId, ...otherIds])]);
    },
    onError,
  });

  const requestRun = useMutation({
    mutationFn: api.requestRun,
    onSuccess: () => {
      toast.push("Run requested; the scheduler starts within 30 seconds", "success");
      return client.invalidateQueries({ queryKey: ["runs"] });
    },
    onError,
  });

  return {
    setStatus,
    addLabels,
    removeLabels,
    blacklist,
    unblacklist,
    deleteJobs,
    addJob,
    updateJob,
    mergeJobs,
    requestRun,
  };
}

/** Writes scoped to one job's application material. */
export function useJobMaterial(jobId: string) {
  const client = useQueryClient();
  const toast = useToast();
  const refresh = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: keys.job(jobId) }),
      client.invalidateQueries({ queryKey: keys.stats }),
      client.invalidateQueries({ queryKey: ["attachments"] }),
      client.invalidateQueries({ queryKey: ["jobs"] }),
    ]);
  const onError = (error: unknown) => toast.push(describe(error), "error");

  const addNote = useMutation({
    mutationFn: (payload: NoteRequest) => api.addNote(jobId, payload),
    onSuccess: refresh,
    onError,
  });
  const updateNote = useMutation({
    mutationFn: ({
      noteId,
      ...payload
    }: {
      noteId: number;
      kind?: NoteKind;
      title?: string | null;
      body?: string;
    }) => api.updateNote(jobId, noteId, payload),
    onSuccess: refresh,
    onError,
  });
  const deleteNote = useMutation({
    mutationFn: (noteId: number) => api.deleteNote(jobId, noteId),
    onSuccess: refresh,
    onError,
  });
  const upload = useMutation({
    mutationFn: ({ file, kind, note }: { file: File; kind: AttachmentKind; note?: string }) =>
      api.uploadAttachment(jobId, file, kind, note),
    onSuccess: async (attachment) => {
      await refresh();
      toast.push(`Attached ${attachment.filename}`, "success");
    },
    onError,
  });
  const updateAttachment = useMutation({
    mutationFn: ({
      attachmentId,
      ...payload
    }: {
      attachmentId: number;
      kind?: AttachmentKind;
      note?: string | null;
      filename?: string;
    }) => api.updateAttachment(jobId, attachmentId, payload),
    onSuccess: refresh,
    onError,
  });
  const deleteAttachment = useMutation({
    mutationFn: (attachmentId: number) => api.deleteAttachment(jobId, attachmentId),
    onSuccess: refresh,
    onError,
  });

  return { addNote, updateNote, deleteNote, upload, updateAttachment, deleteAttachment };
}
