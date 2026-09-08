import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type {
  AddJobRequest,
  AttachmentKind,
  BlacklistListParams,
  JobListParams,
  JobStatus,
  NoteRequest,
} from "../../api/types";
import { useToast } from "../../app/toast";

export const keys = {
  auth: ["auth"] as const,
  jobs: (params: JobListParams) => ["jobs", params] as const,
  job: (jobId: string) => ["job", jobId] as const,
  stats: ["stats"] as const,
  facets: ["facets"] as const,
  sources: ["sources"] as const,
  runs: (limit: number) => ["runs", limit] as const,
  blacklist: (params: BlacklistListParams) => ["blacklist", params] as const,
  distribution: (binSize: number) => ["distribution", binSize] as const,
  cleanupPreview: ["cleanup-preview"] as const,
};

export function useJobs(params: JobListParams, enabled = true) {
  return useQuery({ queryKey: keys.jobs(params), queryFn: () => api.listJobs(params), enabled });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: keys.job(jobId ?? ""),
    queryFn: () => api.getJob(jobId as string),
    enabled: Boolean(jobId),
  });
}

export function useStats() {
  return useQuery({ queryKey: keys.stats, queryFn: api.stats });
}

export function useFacets() {
  return useQuery({ queryKey: keys.facets, queryFn: api.facets });
}

export function useSources() {
  return useQuery({ queryKey: keys.sources, queryFn: api.listSources });
}

export function useRuns(limit = 20) {
  return useQuery({ queryKey: keys.runs(limit), queryFn: () => api.listRuns(limit) });
}

export function useBlacklist(params: BlacklistListParams) {
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

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Every job-level write, each invalidating the lists it can change. */
export function useJobCommands() {
  const client = useQueryClient();
  const toast = useToast();

  const refresh = async (jobIds: string[] = []) => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["jobs"] }),
      client.invalidateQueries({ queryKey: keys.stats }),
      client.invalidateQueries({ queryKey: keys.facets }),
      client.invalidateQueries({ queryKey: keys.sources }),
      client.invalidateQueries({ queryKey: ["blacklist"] }),
      client.invalidateQueries({ queryKey: keys.cleanupPreview }),
      ...jobIds.map((jobId) => client.invalidateQueries({ queryKey: keys.job(jobId) })),
    ]);
  };

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
    onSuccess: async (result, variables) => {
      await refresh(variables.jobIds);
      toast.push(`${result.affected_count} moved to ${variables.status}`, "success");
    },
    onError,
  });

  const addLabels = useMutation({
    mutationFn: ({ jobIds, labels }: { jobIds: string[]; labels: string[] }) =>
      api.addLabels(jobIds, labels),
    onSuccess: (_result, variables) => refresh(variables.jobIds),
    onError,
  });

  const removeLabels = useMutation({
    mutationFn: ({ jobIds, labels }: { jobIds: string[]; labels: string[] }) =>
      api.removeLabels(jobIds, labels),
    onSuccess: (_result, variables) => refresh(variables.jobIds),
    onError,
  });

  const blacklist = useMutation({
    mutationFn: (jobIds: string[]) => api.blacklist(jobIds),
    onSuccess: async (result, jobIds) => {
      await refresh(jobIds);
      toast.push(`${result.affected_count} blacklisted`, "success");
    },
    onError,
  });

  const unblacklist = useMutation({
    mutationFn: (jobIds: string[]) => api.unblacklist(jobIds),
    onSuccess: async (result) => {
      await refresh();
      toast.push(`${result.affected_count} removed from blacklist`, "success");
    },
    onError,
  });

  const deleteJobs = useMutation({
    mutationFn: (jobIds: string[]) => api.deleteJobs(jobIds),
    onSuccess: async (result, jobIds) => {
      await refresh(jobIds);
      toast.push(`${result.affected_count} deleted`, "success");
    },
    onError,
  });

  const addJob = useMutation({
    mutationFn: (payload: AddJobRequest) => api.addJob(payload),
    onSuccess: async (result) => {
      await refresh(result.job_ids);
      toast.push(result.message === "created" ? "Job added" : "Job updated", "success");
    },
    onError,
  });

  return { setStatus, addLabels, removeLabels, blacklist, unblacklist, deleteJobs, addJob };
}

/** Writes scoped to one job's application material. */
export function useJobMaterial(jobId: string) {
  const client = useQueryClient();
  const toast = useToast();
  const refresh = () => client.invalidateQueries({ queryKey: keys.job(jobId) });
  const onError = (error: unknown) => toast.push(describe(error), "error");

  const addNote = useMutation({
    mutationFn: (payload: NoteRequest) => api.addNote(jobId, payload),
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
  const deleteAttachment = useMutation({
    mutationFn: (attachmentId: number) => api.deleteAttachment(jobId, attachmentId),
    onSuccess: refresh,
    onError,
  });

  return { addNote, deleteNote, upload, deleteAttachment };
}
