// First run: a workspace nobody has set up opens on the setup guide (#setup)
// instead of Today. Whether the guide was opened, finished or skipped is
// remembered in this browser only; what is done is always read from the
// workspace itself, so no setting is stored on the server.
import { api, type ListResult } from "../api.ts";

export const SETUP_KEY = "openings-setup";
/**
 * `started`: the guide opened by itself and is not finished; Today offers to
 * continue. `skipped` and `done`: it never opens by itself again. `seen`: the
 * workspace already had data when this browser first opened it.
 */
export type SetupMark = "started" | "skipped" | "done" | "seen";

export function setupMark(): SetupMark | null {
  try {
    return (localStorage.getItem(SETUP_KEY) as SetupMark | null) ?? null;
  } catch {
    return null;
  }
}
export function markSetup(value: SetupMark) {
  try {
    localStorage.setItem(SETUP_KEY, value);
  } catch {
    // Without storage the guide simply opens again on an empty workspace.
  }
  window.dispatchEvent(new Event("openings:setup"));
}

/** What a new workspace lacks; each number is a total. */
export interface FirstRunFacts {
  name: string;
  entries: number;
  sources: number;
  tokens: number;
  jobs: number;
}
/** No Profile name, no Career entry, no source, no API token and no job. */
export const isNewWorkspace = (facts: FirstRunFacts) =>
  !facts.name.trim() &&
  facts.entries === 0 &&
  facts.sources === 0 &&
  facts.tokens === 0 &&
  facts.jobs === 0;

/** Read the facts of a first run; any failure counts as "not new". */
export async function readNewWorkspace() {
  const total = (path: string) =>
    api<ListResult<unknown>>(path).then((list) => list.total);
  try {
    const [profile, entries, sources, tokens, jobs] = await Promise.all([
      api<{ name: string }>("/career/profile"),
      total("/career/knowledge?limit=1"),
      total("/sources?limit=1"),
      total("/tokens"),
      total("/jobs?limit=1"),
    ]);
    return isNewWorkspace({
      name: profile.name || "",
      entries,
      sources,
      tokens,
      jobs,
    });
  } catch {
    return false;
  }
}
