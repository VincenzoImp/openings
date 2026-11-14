// Preferences: the five sections of statements and the two settings beside
// them (spoken languages, no-reply period), read and written through the
// generated client.
import { useQuery } from "@tanstack/react-query";
import { api, call, type Schema } from "../api/client";
import { useApiMutation } from "./mutation";
import { POLL_MS } from "./query";

export type SectionName =
  "looking_for" | "ruled_out" | "facts" | "writing" | "working_with_me";
export type Scope = "all" | "cv" | "letter";
export type Statement = Schema<"PreferenceItem">;
export type Section = Schema<"PreferenceSection">;
export type Settings = Schema<"Settings">;

export const preferenceKeys = {
  all: ["preferences"] as const,
  /** New jobs, and how many require a language the owner does not speak. */
  unspoken: ["jobs", "count", { triage: "new", unspoken: true }] as const,
};

export function usePreferences() {
  return useQuery({
    queryKey: preferenceKeys.all,
    queryFn: ({ signal }) => call(api.GET("/api/v1/preferences", { signal })),
    refetchInterval: POLL_MS,
  });
}

/** "would hide n of the m new jobs": the Jobs filter's effect, read live. */
export function useUnspokenNewJobs(enabled: boolean) {
  const query = useQuery({
    queryKey: preferenceKeys.unspoken,
    enabled,
    queryFn: ({ signal }) =>
      call(
        api.GET("/api/v1/jobs", {
          params: {
            query: { triage: "new", limit: 1, hide_unspoken_required: false },
          },
          signal,
        }),
      ),
    refetchInterval: POLL_MS,
  });
  const report = query.data?.unspoken_required as
    { count?: number } | null | undefined;
  return query.data
    ? { hidden: report?.count ?? 0, total: query.data.total }
    : null;
}

export interface SectionWrite {
  section: SectionName;
  /** The version the change was made on. */
  version: number;
  /** Every statement of the section, in order. */
  items: Statement[];
}

/** Save a whole section with its version (preferences_update). */
export function useSectionWrite() {
  return useApiMutation({
    touches: ["preferences"],
    mutationFn: ({ section, version, items }: SectionWrite) =>
      call(
        api.PUT("/api/v1/preferences/{section}", {
          params: { path: { section } },
          body: { expected_version: version, items },
        }),
      ),
  });
}

/** Change the spoken languages or the no-reply period. */
export function useSaveSettings() {
  return useApiMutation({
    touches: ["preferences", "settings", "jobs"],
    mutationFn: (patch: Schema<"SettingsUpdate">) =>
      call(api.PATCH("/api/v1/settings", { body: patch })),
  });
}
