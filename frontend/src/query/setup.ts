// The facts setup depends on, read from the workspace: the Profile's name,
// the Preferences, sources and jobs, and anything that makes a CV (a career
// entry, a highlight or a template). The shell's "Finish setup" link, Today's
// checklist and the first-run guide all read them here, so two browsers
// always agree. Once `workspace_context` (#218) carries these counts, this
// hook reads them from there instead.
import { useQuery } from "@tanstack/react-query";
import { api, call } from "../api/client";
import { progress, type SetupFacts } from "../screens/setup/checklist";
import { shellKeys } from "./shell";

export const setupKeys = {
  preferences: ["preferences"] as const,
  sources: ["sources", "count"] as const,
  jobs: ["jobs", "count", { triage: "any" }] as const,
  entries: ["career", "knowledge", "count"] as const,
  highlights: ["career", "claims", "count"] as const,
  templates: ["templates", "count"] as const,
};

const STALE = 60_000;

/** The Profile, shared with the shell's account name. */
export function useProfile() {
  return useQuery({
    queryKey: shellKeys.profile,
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/career/profile", { signal })),
  });
}

/** The Preferences sections and the settings (no-reply period, languages). */
export function usePreferences() {
  return useQuery({
    queryKey: setupKeys.preferences,
    staleTime: STALE,
    queryFn: ({ signal }) => call(api.GET("/api/v1/preferences", { signal })),
  });
}

function useTotal(
  key: readonly unknown[],
  read: (signal: AbortSignal) => Promise<{ total: number }>,
) {
  return useQuery({
    queryKey: key,
    staleTime: STALE,
    queryFn: async ({ signal }) => (await read(signal)).total,
  });
}

/** The setup facts, the checklist and whether it is finished. */
export function useSetup() {
  const profile = useProfile();
  const preferences = usePreferences();
  const one = { limit: 1 } as const;
  const sources = useTotal(setupKeys.sources, (signal) =>
    call(api.GET("/api/v1/sources", { params: { query: one }, signal })),
  );
  const jobs = useTotal(setupKeys.jobs, (signal) =>
    call(api.GET("/api/v1/jobs", { params: { query: one }, signal })),
  );
  const entries = useTotal(setupKeys.entries, (signal) =>
    call(
      api.GET("/api/v1/career/knowledge", { params: { query: one }, signal }),
    ),
  );
  const highlights = useTotal(setupKeys.highlights, (signal) =>
    call(api.GET("/api/v1/career/claims", { params: { query: one }, signal })),
  );
  const templates = useTotal(setupKeys.templates, (signal) =>
    call(api.GET("/api/v1/templates", { params: { query: one }, signal })),
  );
  const all = [
    profile,
    preferences,
    sources,
    jobs,
    entries,
    highlights,
    templates,
  ];
  const facts: SetupFacts = {
    name: profile.data?.name?.trim() ?? "",
    preferences:
      preferences.data?.sections.reduce(
        (sum, section) => sum + section.items.length,
        0,
      ) ?? 0,
    sources: sources.data ?? 0,
    jobs: jobs.data ?? 0,
    cv: (entries.data ?? 0) + (highlights.data ?? 0) + (templates.data ?? 0),
  };
  return {
    facts,
    ...progress(facts),
    loaded: all.every((read) => read.isSuccess),
    error: all.find((read) => read.error)?.error ?? null,
    retry: () => all.forEach((read) => void read.refetch()),
  };
}
