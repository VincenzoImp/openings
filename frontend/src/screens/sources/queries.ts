// The reads and writes of the Sources screen, over the generated client.
import { useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../../api/client";
import { useApiMutation, useVersionedMutation } from "../../query/mutation";
import { POLL_MS } from "../../query/query";
import type { CheckView, SourceView } from "./model";

export const sourceKeys = {
  list: ["sources", "list"] as const,
  schemas: ["sources", "schemas"] as const,
  collection: ["collection", "state"] as const,
  checks: ["collection", "runs", "recent"] as const,
};

/** Every source, with its counts, last check and next check. */
export function useSources() {
  return useQuery({
    queryKey: sourceKeys.list,
    queryFn: async ({ signal }) =>
      (
        await call(
          api.GET("/api/v1/sources", {
            params: { query: { limit: 500 } },
            signal,
          }),
        )
      ).items as unknown as (SourceView & Schema<"Source">)[],
    refetchInterval: POLL_MS,
  });
}

/** The labels of the source kinds ("Greenhouse"), by kind. */
export function useKindLabels() {
  const query = useQuery({
    queryKey: sourceKeys.schemas,
    staleTime: Infinity,
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/sources/schemas", { signal })),
  });
  return Object.fromEntries(
    (query.data?.items ?? []).map((item) => [
      String(item.kind),
      String(item.label),
    ]),
  );
}

/** The switch of automatic checks and the next one. */
export function useCollection() {
  return useQuery({
    queryKey: sourceKeys.collection,
    queryFn: ({ signal }) => call(api.GET("/api/v1/collection", { signal })),
    refetchInterval: POLL_MS,
  });
}

/** The last 20 checks, newest first. */
export function useRecentChecks(enabled: boolean) {
  return useQuery({
    queryKey: sourceKeys.checks,
    enabled,
    queryFn: async ({ signal }) =>
      (
        await call(
          api.GET("/api/v1/collection/runs", {
            params: { query: { limit: 20 } },
            signal,
          }),
        )
      ).items as unknown as CheckView[],
    refetchInterval: POLL_MS,
  });
}

const TOUCHES = ["sources", "collection", "tasks"] as const;

/** Check one source now, outside its schedule. */
export function useCheckNow() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (source: Pick<SourceView, "id" | "version">) =>
      call(
        api.POST("/api/v1/sources/{source_id}/run", {
          params: { path: { source_id: source.id } },
          body: { expected_version: source.version },
        }),
      ),
  });
}

/** One action on several sources: check, pause, resume, set the schedule. */
export function useSourcesBulk() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (body: Schema<"SourceBulk">) =>
      call(api.POST("/api/v1/sources/bulk", { body })),
  });
}

/** Pause or resume one source. */
export function useSetEnabled() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: ({
      source,
      enabled,
    }: {
      source: Pick<SourceView, "id" | "version">;
      enabled: boolean;
    }) =>
      call(
        api.PATCH("/api/v1/sources/{source_id}", {
          params: { path: { source_id: source.id } },
          body: { expected_version: source.version, enabled },
        }),
      ),
  });
}

/** Delete a source for good; the jobs it found stay. */
export function useDeleteSource() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (source: Pick<SourceView, "id" | "version">) =>
      call(
        api.DELETE("/api/v1/sources/{source_id}", {
          params: {
            path: { source_id: source.id },
            query: { expected_version: source.version },
          },
        }),
      ),
  });
}

/** Add a source. */
export function useCreateSource() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (body: Schema<"SourceCreate">) =>
      call(api.POST("/api/v1/sources", { body })),
  });
}

/** Save a source's settings against the version the form was opened on. */
export function useUpdateSource(onReload?: () => void) {
  return useVersionedMutation({
    touches: TOUCHES,
    onReload,
    mutationFn: ({ id, ...body }: Schema<"SourcePatch"> & { id: string }) =>
      call(
        api.PATCH("/api/v1/sources/{source_id}", {
          params: { path: { source_id: id } },
          body,
        }),
      ),
  });
}

/** Ask the sites once, through the shared request gate; nothing is saved. */
export function usePreview() {
  return useApiMutation({
    touches: ["providers"],
    mutationFn: (body: Schema<"SourcePreview">) =>
      call(api.POST("/api/v1/sources/preview", { body })),
  });
}

/** Pause or resume every automatic check. */
export function useSetCollection() {
  return useApiMutation({
    touches: ["collection", "sources"],
    mutationFn: (body: Schema<"CollectionWrite">) =>
      call(api.PATCH("/api/v1/collection", { body })),
  });
}

/** Stop a check in progress; the jobs it already found stay. */
export function useStopCheck() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: (id: string) =>
      call(
        api.POST("/api/v1/collection/runs/{run_id}/cancel", {
          params: { path: { run_id: id } },
        }),
      ),
  });
}

/** Queue the failed parts of a check again. */
export function useRetryCheck() {
  return useApiMutation({
    touches: TOUCHES,
    mutationFn: async (taskIds: string[]) => {
      for (const task_id of taskIds)
        await call(
          api.POST("/api/v1/tasks/{task_id}/retry", {
            params: { path: { task_id } },
          }),
        );
    },
  });
}
