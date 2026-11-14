// Today's reads and writes, through the generated client and Query.
import { useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../../api/client";
import type { operations } from "../../api/schema";
import { useApiMutation } from "../../query/mutation";
import { POLL_MS } from "../../query/query";
import { isoDay } from "../../ui/format";
import { type Row } from "./model";

type Query = NonNullable<
  operations["applications_list"]["parameters"]["query"]
>;

export type Application = Schema<"ApplicationRow"> & Row;

/** A page of applications; keys start with the resource. */
function useApplications(query: Query) {
  return useQuery({
    queryKey: ["applications", "list", query],
    refetchInterval: POLL_MS,
    queryFn: async ({ signal }) => {
      const page = await call(
        api.GET("/api/v1/applications", { params: { query }, signal }),
      );
      return { ...page, items: page.items as Application[] };
    },
  });
}

/** Everything Today shows. */
export function useToday() {
  const ready = useApplications({ stage: "ready", sort: "deadline", limit: 5 });
  const shortlisted = useApplications({
    stage: "shortlisted",
    sort: "deadline",
    limit: 200,
  });
  const waiting = useApplications({
    needs: "reply_overdue",
    sort: "applied",
    limit: 200,
  });
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const since = isoDay(yesterday);
  const newJobs = useQuery({
    queryKey: ["jobs", "list", { triage: "new", limit: 3, sort: "newest" }],
    refetchInterval: POLL_MS,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/jobs", {
          params: { query: { triage: "new", limit: 3, sort: "newest" } },
          signal,
        }),
      ),
  });
  const recent = useQuery({
    queryKey: ["jobs", "count", { triage: "new", created_since: since }],
    refetchInterval: POLL_MS,
    queryFn: async ({ signal }) =>
      (
        await call(
          api.GET("/api/v1/jobs", {
            params: {
              query: { triage: "new", created_since: since, limit: 1 },
            },
            signal,
          }),
        )
      ).total,
  });
  const all = [ready, shortlisted, waiting, newJobs, recent];
  return {
    ready,
    shortlisted,
    waiting,
    newJobs,
    recent,
    loading: all.some((read) => read.isPending),
    error: all.find((read) => read.error)?.error ?? null,
    retry: () => all.forEach((read) => void read.refetch()),
  };
}

/**
 * The open requirements of a few applications, by requirement id, so a row
 * can name the one that is missing ("Reference letter not done").
 */
export function useRequirementTexts(ids: string[]) {
  const read = useQuery({
    queryKey: ["applications", "requirements", ids],
    enabled: ids.length > 0,
    staleTime: 30_000,
    queryFn: ({ signal }) =>
      Promise.all(
        ids.map((id) =>
          call(
            api.GET("/api/v1/applications/{application_id}", {
              params: { path: { application_id: id } },
              signal,
            }),
          ),
        ),
      ),
  });
  const texts: Record<string, string> = {};
  for (const application of read.data ?? [])
    for (const requirement of application.requirements ?? [])
      if (requirement.id && !requirement.resolved)
        texts[requirement.id] = requirement.text;
  return texts;
}

type Bulk = Schema<"ApplicationBulk">;

/** Close or reopen applications; one call, each item on its own. */
export function useBulkApplications() {
  return useApiMutation({
    touches: ["applications", "stats"],
    mutationFn: (body: Bulk) =>
      call(api.POST("/api/v1/applications/bulk", { body })),
  });
}

export type ReplyKind = "interview" | "rejection" | "offer" | "other";

/** Record the employer's reply; the server moves the stage. */
export function useRecordReply() {
  return useApiMutation({
    touches: ["applications", "stats"],
    mutationFn: ({
      id,
      version,
      kind,
      date,
      note,
    }: {
      id: string;
      version: number;
      kind: ReplyKind;
      date: string;
      note: string;
    }) =>
      call(
        api.PATCH("/api/v1/applications/{application_id}", {
          params: { path: { application_id: id } },
          body: {
            expected_version: version,
            reply: { kind, date, note, remove: false },
          },
        }),
      ),
  });
}
