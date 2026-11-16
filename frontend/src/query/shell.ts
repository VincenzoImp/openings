// The shell's reads and its one write: the "needs you" counts, the account
// name, the command palette's search and Add job.
import { useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../api/client";
import { useApiMutation } from "./mutation";
import { POLL_MS } from "./query";

export const shellKeys = {
  newJobs: ["jobs", "count", { triage: "new" }] as const,
  readyApplications: ["applications", "count", { stage: "ready" }] as const,
  profile: ["career", "profile"] as const,
  searchJobs: (q: string) => ["jobs", "search", q] as const,
  searchApplications: (q: string) => ["applications", "search", q] as const,
  resolve: (url: string) => ["jobs", "resolve", url] as const,
};

/** New jobs and Ready applications: the navigation's accent counts. */
export function useNeedsCounts() {
  const jobs = useQuery({
    queryKey: shellKeys.newJobs,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/jobs", {
          params: { query: { triage: "new", limit: 1 } },
          signal,
        }),
      ),
    refetchInterval: POLL_MS,
  });
  const applications = useQuery({
    queryKey: shellKeys.readyApplications,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/applications", {
          params: { query: { limit: 1 } },
          signal,
        }),
      ),
    refetchInterval: POLL_MS,
  });
  return {
    newJobs: jobs.data?.total ?? 0,
    readyApplications: applications.data?.stage_counts?.ready ?? 0,
    loaded: jobs.isFetched && applications.isFetched,
  };
}

/** The account row's name: the Profile's name, or "You" until there is one. */
export function useAccountName() {
  const profile = useQuery({
    queryKey: shellKeys.profile,
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/career/profile", { signal })),
  });
  return profile.data?.name?.trim() || "You";
}

export type JobHit = Pick<
  Schema<"JobSummary">,
  "id" | "title" | "company" | "location" | "triage"
> & { unlisted: boolean };
export interface ApplicationHit {
  id: string;
  title: string;
  company: string;
  /** The stage, or "ready" for a Shortlisted application that is Ready. */
  stage: string;
}

/** How many of each kind ⌘K shows; "Show all" opens the rest in their list. */
export const PALETTE_LIMIT = 8;

/**
 * Jobs and applications for ⌘K, in the server's relevance order (the same as
 * jobs_list and applications_list): the exact title first, then title,
 * company, location and state matches, then words found only in a posting.
 */
export function usePaletteSearch(q: string) {
  const enabled = q.trim().length >= 2;
  const jobs = useQuery({
    queryKey: shellKeys.searchJobs(q),
    enabled,
    staleTime: 30_000,
    queryFn: async ({ signal }) => {
      const page = await call(
        api.GET("/api/v1/jobs", {
          params: { query: { q, limit: PALETTE_LIMIT } },
          signal,
        }),
      );
      return {
        total: page.total,
        items: page.items.map((row): JobHit => ({
          id: row.id,
          title: row.title,
          company: row.company,
          location: row.location,
          triage: row.triage,
          unlisted: row.signals.no_longer_listed,
        })),
      };
    },
  });
  const applications = useQuery({
    queryKey: shellKeys.searchApplications(q),
    enabled,
    staleTime: 30_000,
    queryFn: async ({ signal }) => {
      const page = await call(
        api.GET("/api/v1/applications", {
          params: { query: { q, limit: PALETTE_LIMIT } },
          signal,
        }),
      );
      return {
        total: page.total,
        items: page.items.map((row): ApplicationHit => ({
          id: row.id,
          title: String(row.job.title ?? "Untitled role"),
          company: String(row.job.company ?? ""),
          stage: row.stage === "shortlisted" && row.ready ? "ready" : row.stage,
        })),
      };
    },
  });
  return {
    enabled,
    loading: enabled && (jobs.isFetching || applications.isFetching),
    jobs: enabled ? (jobs.data?.items ?? []) : [],
    applications: enabled ? (applications.data?.items ?? []) : [],
    totals: {
      jobs: enabled ? (jobs.data?.total ?? 0) : 0,
      applications: enabled ? (applications.data?.total ?? 0) : 0,
    },
  };
}

/** A job already in the workspace at this address, if any. */
export function useKnownJob(url: string) {
  const valid = /^https?:\/\/\S+\.\S+/.test(url);
  const query = useQuery({
    queryKey: shellKeys.resolve(url),
    enabled: valid,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/jobs/resolve", {
          params: { query: { url } },
          signal,
        }),
      ),
  });
  return valid ? (query.data?.items?.[0] ?? null) : null;
}

export type NewJob = Pick<
  Schema<"JobInput">,
  "url" | "posting" | "title" | "company" | "location"
>;

/** Add a job by its address or its pasted text. */
export function useAddJob() {
  return useApiMutation({
    touches: ["jobs", "stats"],
    mutationFn: (job: NewJob) =>
      call(api.POST("/api/v1/jobs", { body: job as Schema<"JobInput"> })),
  });
}
