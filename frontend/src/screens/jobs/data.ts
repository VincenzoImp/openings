// The Jobs screen's reads and writes over the generated client. Keys start
// with the resource: ["jobs", "list", query], ["jobs", "one", id]. Every
// write touches jobs and applications (shortlisting starts one) and stats.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../../api/client";
import { useApiMutation, useVersionedMutation } from "../../query/mutation";
import { POLL_MS, queryClient, type Resource } from "../../query/query";
import type { Job, JobSummary, ListQuery } from "./model";

export const TOUCHES: Resource[] = ["jobs", "applications", "stats"];

export const jobKeys = {
  list: (query: ListQuery) => ["jobs", "list", query] as const,
  one: (id: string) => ["jobs", "one", id] as const,
  facets: (query: ListQuery) => ["jobs", "facets", query] as const,
  duplicate: (id: string) => ["jobs", "duplicates", id] as const,
  timeline: (id: string) => ["jobs", "timeline", id] as const,
  search: (q: string) => ["jobs", "search", "merge", q] as const,
};

/** One page of a tab, with the counts of every tab for the same filters. */
export function useJobList(query: ListQuery) {
  return useQuery({
    queryKey: jobKeys.list(query),
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/jobs", { params: { query }, signal })),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  });
}

const readJob = (id: string, signal?: AbortSignal) =>
  call(
    api.GET("/api/v1/jobs/{job_id}", {
      params: { path: { job_id: id } },
      signal,
    }),
  );

/**
 * A job in full. While it loads, the row it was chosen from stands in, so
 * moving to the next job shows its title at once.
 */
export function useJob(id: string, row?: JobSummary) {
  return useQuery({
    queryKey: jobKeys.one(id),
    enabled: !!id,
    queryFn: ({ signal }) => readJob(id, signal),
    placeholderData: row
      ? ({ ...row, posting: "", overrides: {}, postings: [] } as Job)
      : undefined,
  });
}

/** A job in full, from the cache when it is fresh. */
export const fetchJob = (id: string, staleTime = 10_000) =>
  queryClient.fetchQuery({
    queryKey: jobKeys.one(id),
    queryFn: ({ signal }) => readJob(id, signal),
    staleTime,
  });

/** Read a job before it is shown (the next row of the queue). */
export function prefetchJob(id: string) {
  if (!id) return;
  void queryClient.prefetchQuery({
    queryKey: jobKeys.one(id),
    queryFn: ({ signal }) => readJob(id, signal),
    staleTime: 30_000,
  });
}

/** The values the filters can take: companies, places, sources. */
export function useFacets(query: ListQuery, enabled: boolean) {
  const facets = {
    triage: query.triage,
    limit: 1,
    include_facets: true,
  } satisfies ListQuery;
  return useQuery({
    queryKey: jobKeys.facets(facets),
    enabled,
    staleTime: 60_000,
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/jobs", { params: { query: facets }, signal })),
    select: (page) => page.facets ?? {},
  });
}

/** The candidate group a possible duplicate belongs to, with its reasons. */
export function useDuplicate(jobId: string, otherId: string | null) {
  const other = useQuery({
    queryKey: jobKeys.one(otherId ?? ""),
    enabled: !!otherId,
    queryFn: ({ signal }) => readJob(otherId!, signal),
    retry: false,
  });
  const group = useQuery({
    queryKey: jobKeys.duplicate(jobId),
    enabled: !!otherId,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/jobs/duplicates", {
          params: { query: { job_id: jobId, min_confidence: 0, limit: 1 } },
          signal,
        }),
      ),
  });
  const members = group.data?.items[0];
  const item = members?.items.find((entry) => entry.id === otherId) as
    { reasons?: unknown } | undefined;
  return { other: other.data, reasons: item?.reasons ?? members?.reasons };
}

/** Notes and recorded changes of a job, pinned note first. */
export function useTimeline(jobId: string, enabled: boolean) {
  return useQuery({
    queryKey: jobKeys.timeline(jobId),
    enabled,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/jobs/{job_id}/timeline", {
          params: { path: { job_id: jobId }, query: { limit: 50 } },
          signal,
        }),
      ),
  });
}

/** When the sources are next checked, and whether any exists. */
export function useCollection() {
  return useQuery({
    queryKey: ["collection", "status"],
    staleTime: 60_000,
    queryFn: ({ signal }) => call(api.GET("/api/v1/collection", { signal })),
  });
}

/** Jobs whose title or company matches, to merge with. */
export function useJobSearch(q: string, enabled: boolean) {
  return useQuery({
    queryKey: jobKeys.search(q),
    enabled,
    staleTime: 30_000,
    queryFn: async ({ signal }) =>
      (
        await call(
          api.GET("/api/v1/jobs", {
            params: { query: { q, limit: 8 } },
            signal,
          }),
        )
      ).items,
  });
}

export type BulkAction = Schema<"JobBulk">["action"];
export interface BulkVars {
  action: BulkAction;
  items: { id: string; version: number }[];
  reason?: string;
}

/** The same change for many jobs, 200 at a time; one result per job. */
export function useBulk() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: async ({ action, items, reason }: BulkVars) => {
      const results: Schema<"BatchItem">[] = [];
      for (let start = 0; start < items.length; start += 200) {
        const page = await call(
          api.POST("/api/v1/jobs/bulk", {
            body: {
              action,
              items: items.slice(start, start + 200).map((item) => ({
                id: item.id,
                expected_version: item.version,
              })),
              ...(reason ? { reason } : {}),
            },
          }),
        );
        results.push(...page.items);
      }
      return results;
    },
  });
}

/** Merge a job into another record of the same vacancy. */
export function useMerge() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (vars: { job: Job; target: JobSummary }) =>
      call(
        api.POST("/api/v1/jobs/{job_id}/merge", {
          params: { path: { job_id: vars.job.id } },
          body: {
            target_id: vars.target.id,
            expected_version: vars.job.version,
            target_version: vars.target.version,
          },
        }),
      ),
  });
}

/** Keep a possible duplicate apart: it is a different vacancy. */
export function useDistinct() {
  return useApiMutation({
    touches: ["jobs"],
    mutationFn: (vars: { id: string; otherId: string }) =>
      call(
        api.POST("/api/v1/jobs/{job_id}/distinct", {
          params: { path: { job_id: vars.id } },
          body: { other_id: vars.otherId },
        }),
      ),
  });
}

export type JobPatch = Schema<"JobPatch">;
/** Correct a job's details, with the version that was read. */
export function useCorrect(id: string, onReload?: () => void) {
  return useVersionedMutation({
    touches: ["jobs"],
    onReload,
    mutationFn: (patch: JobPatch) =>
      call(
        api.PATCH("/api/v1/jobs/{job_id}", {
          params: { path: { job_id: id } },
          body: patch,
        }),
      ),
  });
}

/** Add a note to a job. */
export function useAddNote(jobId: string) {
  return useApiMutation({
    touches: ["jobs", "notes"],
    mutationFn: (note: { body: string; pinned: boolean }) =>
      call(
        api.POST("/api/v1/jobs/{job_id}/notes", {
          params: { path: { job_id: jobId } },
          body: note,
        }),
      ),
  });
}
