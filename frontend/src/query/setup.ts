// The facts setup depends on, from the one start read `workspace_context`
// (GET /workspace/context): the Profile's name, the Preferences, how many
// jobs and sources exist, and anything that makes a CV (a career entry, its
// highlights or a template). The shell's "Finish setup" link, Today's
// checklist and the first-run guide all read them here, so two browsers
// always agree; nothing is kept in the browser.
import { useQuery } from "@tanstack/react-query";
import { api, call } from "../api/client";
import { progress, type SetupFacts } from "../screens/setup/checklist";
import { shellKeys } from "./shell";

export const setupKeys = {
  context: ["workspace", "context"] as const,
  preferences: ["preferences"] as const,
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

/** The Preferences sections, with their versions, and the settings. */
export function usePreferences() {
  return useQuery({
    queryKey: setupKeys.preferences,
    staleTime: STALE,
    queryFn: ({ signal }) => call(api.GET("/api/v1/preferences", { signal })),
  });
}

/** The setup facts, the checklist and whether it is finished. */
export function useSetup() {
  const context = useQuery({
    queryKey: setupKeys.context,
    staleTime: STALE,
    queryFn: ({ signal }) =>
      call(api.GET("/api/v1/workspace/context", { signal })),
  });
  const data = context.data;
  const preferences = Object.values(
    (data?.preferences ?? {}) as Record<string, { items?: unknown[] }>,
  );
  const facts: SetupFacts = {
    name: String(data?.profile.name ?? "").trim(),
    preferences: preferences.reduce(
      (sum, section) => sum + (section.items?.length ?? 0),
      0,
    ),
    sources: data?.counts.sources ?? 0,
    jobs: data?.counts.jobs ?? 0,
    cv: (data?.career.length ?? 0) + (data?.templates.length ?? 0),
  };
  return {
    facts,
    ...progress(facts),
    loaded: context.isSuccess,
    error: context.error,
    retry: () => void context.refetch(),
  };
}
