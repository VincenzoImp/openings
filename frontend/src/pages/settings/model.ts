// What the Settings screen derives, as pure functions without React
// (tests/settings.test.mjs).

/** The four sections, in the order of the sub-navigation. */
export const SECTIONS = [
  { id: "account", label: "Account" },
  { id: "agents", label: "API & agents" },
  { id: "data", label: "Data" },
  { id: "advanced", label: "Advanced" },
] as const;
export type SectionId = (typeof SECTIONS)[number]["id"];

/** The section an address names; none on a phone shows the list. */
export function sectionOf(value: string | null): SectionId | null {
  return SECTIONS.find((section) => section.id === value)?.id ?? null;
}

/** Bytes as people read them: "912 KB", "1.4 MB", "136 GB". */
export function bytes(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  const units = ["bytes", "KB", "MB", "GB", "TB"];
  let size = value;
  let unit = 0;
  while (size >= 1000 && unit < units.length - 1) {
    size /= 1000;
    unit += 1;
  }
  if (unit === 0) return `${Math.round(size)} bytes`;
  return `${size >= 10 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

export type TokenKind = "agent" | "owner";

export const ACCESS: Record<TokenKind, { label: string; detail: string }> = {
  agent: {
    label: "Agent",
    detail:
      "Works in the job search. Cannot change your password, manage tokens, restore or export.",
  },
  owner: {
    label: "Full access",
    detail: "Everything you can do here, including tokens and restore.",
  },
};

export const accessOf = (kind: unknown): TokenKind =>
  kind === "owner" ? "owner" : "agent";

/** The agents with a ready connect snippet. */
export const CLIENTS = [
  { id: "claude", label: "Claude Code" },
  { id: "codex", label: "Codex" },
] as const;
export type ClientId = (typeof CLIENTS)[number]["id"];

/** How an agent adds Openings: its MCP address and the token's variable. */
export function connectSnippet(client: ClientId, origin: string) {
  const endpoint = `${origin.replace(/\/$/, "")}/mcp`;
  if (client === "codex")
    return `# ~/.codex/config.toml\n[mcp_servers.openings]\nurl = "${endpoint}"\nbearer_token_env_var = "OPENINGS_TOKEN"`;
  return `claude mcp add --transport http openings ${endpoint} \\\n  --header 'Authorization: Bearer \${OPENINGS_TOKEN}'`;
}

/** A request gate's state for one job site: a dot and a word. */
export function gateOf(
  provider: {
    capability: Record<string, unknown>;
    policy: Record<string, unknown>;
    runtime: Record<string, unknown>;
  },
  now = Date.now(),
): { tone: "success" | "warning" | "neutral"; text: string } {
  const future = (value: unknown) =>
    typeof value === "string" && new Date(value).getTime() > now;
  if (provider.capability.supported === false)
    return { tone: "neutral", text: "Not supported" };
  if (provider.policy.enabled === false) return { tone: "neutral", text: "Off" };
  if (future(provider.runtime.cooldown_until))
    return { tone: "warning", text: "Asked to wait" };
  return { tone: "success", text: "Ready" };
}

/** Seconds between requests as typed: a number from 0 to 3600, or null. */
export function spacing(value: string) {
  const number = Number(value.replace(",", "."));
  if (!value.trim() || !Number.isFinite(number)) return null;
  if (number < 0 || number > 3600) return null;
  return Math.round(number * 10) / 10;
}

/** This workspace as the setup guide reads it (every field may be missing). */
export interface WorkspaceInfo {
  origin?: string | null;
  version?: string;
  schema_version?: number;
}
