// What the Settings screen reads, and the pure helpers it uses.
import type { TokenKind } from "../../api";

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
/** A copy the server keeps: a daily backup or a copy taken before an upgrade. */
export interface KeptBackup {
  name: string;
  kind: "scheduled" | "pre_upgrade";
  size_bytes: number;
  created_at: string;
}
export interface BackupAttempt {
  attempted_at: string;
  outcome: "ok" | "skipped" | "failed";
  name: string | null;
  error: string | null;
}
export interface KeptBackups {
  items: KeptBackup[];
  total: number;
  schedule: {
    enabled: boolean;
    keep: number;
    interval_hours: number;
    last_at: string | null;
    age_hours: number | null;
    ok: boolean;
    last_attempt: BackupAttempt | null;
  };
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
    "Runs the job search. Cannot change your password, manage tokens or restore a backup.",
  owner: "Full access, the same as your dashboard session.",
};

/** A served skill, as listed: what the owner can ask the agent with it. */
export interface SkillItem {
  name: string;
  /** A plain title: "Prepare for an interview". */
  title: string;
  /** One sentence on what the owner can ask. */
  summary: string;
  /** One phrase the owner could say in the agent's chat. */
  example: string;
  /** The skill's description for agents. */
  description: string;
  files: string[];
  file_details?: { path: string; bytes: number; title: string }[];
}
