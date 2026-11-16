// The reads and writes of the Sources screen, over the generated client.
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../../api/client";
import { useApiMutation, useVersionedMutation } from "../../query/mutation";
import { POLL_MS } from "../../query/query";
import type { SourceView } from "./model";

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
      ).items,
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
      ).items,
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
    mutationFn: (body: Schema<"SourceTest">) =>
      call(api.POST("/api/v1/sources/preview", { body })),
  });
}

export type TestResult = Schema<"SourcePreviewResult"> & {
  kind?: string;
  url?: string;
  automatic_collection?: boolean;
};
export type TestPhase = "idle" | "listing" | "details" | "done";

const hasText = (item: Record<string, unknown>) =>
  typeof item.posting === "string" && item.posting.trim() !== "";

/**
 * Test a source in two steps: the board's listing first (its titles show at
 * once), then the posting text of the first few. A search, a feed or HN answers
 * in one step. Both go through the shared request gate; nothing is saved.
 */
export function useSourceTest() {
  const preview = usePreview();
  const asked = useRef(0);
  const [state, setState] = useState<{
    phase: TestPhase;
    result: TestResult | null;
    error: string;
  }>({ phase: "idle", result: null, error: "" });

  async function run(body: Omit<Schema<"SourceTest">, "details">) {
    const question = ++asked.current;
    const current = () => asked.current === question;
    const twoSteps = !["jobspy", "rss", "hnhiring"].includes(body.kind ?? "");
    setState({ phase: "listing", result: null, error: "" });
    try {
      let result = (await preview.mutateAsync({
        ...body,
        details: !twoSteps,
      })) as TestResult;
      if (!current()) return;
      const waiting = result.items.some((item) => !hasText(item));
      if (twoSteps && result.items.length && waiting) {
        setState({ phase: "details", result, error: "" });
        const listed = result;
        result = (await preview.mutateAsync({
          ...body,
          details: true,
        })) as TestResult;
        if (!current()) return;
        // A later refusal keeps the titles the listing gave.
        if (!result.items.length) result = { ...result, items: listed.items };
      }
      setState({ phase: "done", result, error: "" });
    } catch (error) {
      if (current())
        setState((before) => ({
          phase: "done",
          result: before.result,
          error: error instanceof Error ? error.message : "The test failed.",
        }));
    }
  }

  return {
    ...state,
    pending: state.phase === "listing" || state.phase === "details",
    run,
    reset: () => {
      asked.current += 1;
      setState({ phase: "idle", result: null, error: "" });
    },
  };
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
