// What the Settings screen reads, and the pure helpers it uses.
import type { Actor, TokenKind } from "../../api";

export interface Token {
  id: string;
  name: string;
  kind: TokenKind;
  created_at: string;
  last_used_at?: string;
}

export interface Storage {
  database_bytes: number;
  free_bytes: number;
  restore_limit_bytes: number;
  restore_limit_configured_bytes: number | null;
  retention_days: number;
  kept_runs_per_source: number;
}
export interface WorkspaceInfo {
  origin?: string;
  name?: string;
  version?: string;
  schema_version?: number;
  api_base?: string;
  mcp_endpoint?: string;
  storage?: Storage;
}

/** Two cards side by side while each has room for its form, else one above the other. */
export const TWO_UP = "repeat(auto-fit, minmax(min(100%, 380px), 1fr))";

/** Bytes as MiB or GiB, the units of the restore limit. */
export function megabytes(bytes: number) {
  const value = bytes / 1024 ** 2;
  return value >= 1024
    ? `${(value / 1024).toFixed(1)} GiB`
    : `${value.toFixed(value < 10 ? 1 : 0)} MiB`;
}

export const tokenAccess: Record<TokenKind, string> = {
  agent:
    "Runs the job search. Cannot change your password, manage tokens, restore a backup, confirm policy items, answer its own questions or write requests for itself.",
  owner: "Full access, the same as your dashboard session.",
};

/** A served skill, as listed. */
export interface SkillItem {
  name: string;
  description: string;
  files: string[];
  file_details?: { path: string; bytes: number; title: string }[];
  local_notes: NotesSummary | null;
}
export interface NotesSummary {
  version: number;
  updated_at: string;
  updated_by: Actor;
  length: number;
}
export interface SkillText {
  name: string;
  path: string;
  content: string;
  local_notes: NotesSummary | null;
}
export interface NoteVersion {
  version: number;
  text: string;
  created_at: string;
  created_by: Actor;
}
export interface SkillNotes {
  skill: string;
  text: string;
  version: number;
  max_length: number;
  updated_at: string | null;
  updated_by: Actor | null;
  versions: NoteVersion[];
  versions_total: number;
}

/** The text of SKILL.md after its front matter, which the list already shows. */
export function body(content: string) {
  return content.replace(/^---\n[\s\S]*?\n---\n+/, "");
}

/**
 * Files of other skills a skill's text links to, as `../<skill>/<path>`:
 * the shared references an agent reads with it.
 */
export function linkedFiles(content: string, own: string) {
  const found = new Map<string, { skill: string; path: string }>();
  for (const match of content.matchAll(
    /\]\(\.\.\/([\w-]+)\/([\w./-]+\.md)\)/g,
  )) {
    const [, skill, path] = match;
    // Another skill's SKILL.md is that skill, listed beside this one.
    if (skill !== own && path !== "SKILL.md")
      found.set(`${skill}/${path}`, { skill, path });
  }
  return [...found.values()].sort((a, b) =>
    `${a.skill}/${a.path}`.localeCompare(`${b.skill}/${b.path}`),
  );
}

/** Text added to notes: a blank line between it and what is there. */
export function appended(current: string, addition: string) {
  const left = current.trimEnd(),
    right = addition.trim();
  if (!right) return current;
  return left ? `${left}\n\n${right}` : right;
}
