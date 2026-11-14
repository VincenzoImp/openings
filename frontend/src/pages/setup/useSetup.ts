import { useEffect } from "react";
import type { ListResult, Preferences, Profile } from "../../api";
import { useFresh } from "../../library/useFresh";
import type { SetupFacts, SetupToken } from "./model";

const NONE: ListResult<never> = { items: [], total: 0 };
const BLANK = {
  name: "",
  headline: "",
  location: "",
  email: "",
  version: 0,
} as Profile;
const NO_PREFERENCES: Preferences = {
  sections: [],
  settings: {
    no_reply_days: 30,
    spoken_languages: [],
    version: 0,
    updated_at: null,
  },
};
// The agent works while the guide is open: read everything again this often.
const POLL = 10_000;

/** What the guide reads, kept current while it is open. */
export function useSetup() {
  const profile = useFresh<Profile>("/career/profile", BLANK, ["career"]);
  const preferences = useFresh<Preferences>("/preferences", NO_PREFERENCES, [
    "preferences",
    "settings",
  ]);
  const sources = useFresh("/sources?limit=1", NONE, ["sources"]);
  const tokens = useFresh<ListResult<SetupToken>>("/tokens", NONE, ["tokens"]);
  const entries = useFresh("/career/knowledge?limit=1", NONE, ["career"]);
  const claims = useFresh("/career/claims?limit=1", NONE, ["career"]);
  const templates = useFresh("/templates?limit=1", NONE, ["templates"]);
  const applications = useFresh("/applications?limit=1", NONE, [
    "applications",
    "settings",
  ]);
  const all = [
    profile,
    preferences,
    sources,
    tokens,
    entries,
    claims,
    templates,
    applications,
  ];
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible")
        for (const read of all) read.reload();
    }, POLL);
    return () => clearInterval(timer);
  }, []);
  const facts: SetupFacts = {
    profile: profile.data,
    sections: preferences.data.sections,
    noReply: applications.data.no_reply ?? null,
    sources: sources.data.total,
    tokens: tokens.data.items,
    entries: entries.data.total,
    claims: claims.data.total,
    templates: templates.data.total,
    applications: applications.data.total,
  };
  return {
    facts,
    profile: profile.data,
    preferences: preferences.data,
    loading: all.some((read) => read.loading),
    error: all.find((read) => read.error)?.error ?? null,
    reload: () => all.forEach((read) => read.reload()),
  };
}
