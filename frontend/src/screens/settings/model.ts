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

/**
 * What a copy kept before an upgrade was taken before, from its file name
 * ("openings.pre-0.24.sqlite"): "Before 0.24".
 */
export function upgradeOf(name: string) {
  const match = name.match(/\.pre-(.+?)(?:-\d{8}T\d{6}Z)?\.sqlite$/);
  if (!match) return "Before an upgrade";
  return `Before ${match[1].replace(/^schema-?(\d+)$/, "schema $1")}`;
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
      "Works in the job search. Cannot change your password, manage tokens or restore a backup.",
  },
  owner: {
    label: "Full access",
    detail: "Everything you can do here, including tokens and restore.",
  },
};

export const accessOf = (kind: unknown): TokenKind =>
  kind === "owner" ? "owner" : "agent";

/** The agents with a ready connect snippet, and any MCP client (JSON). */
export const CLIENTS = [
  { id: "plugin", label: "Claude Code plugin" },
  { id: "claude", label: "Claude Code" },
  { id: "codex", label: "Codex" },
  { id: "json", label: "JSON" },
] as const;
export type ClientId = (typeof CLIENTS)[number]["id"];

/** The address the Claude Code plugin uses unless OPENINGS_URL says another. */
export const PLUGIN_ORIGIN = "http://127.0.0.1:8080";

/** The token placeholder of a snippet; the real one is shown once. */
export const TOKEN_PLACEHOLDER = "op_…";

const trimmed = (origin: string) => origin.replace(/\/+$/, "");

/** The line that puts a token in the shell, for every agent started there. */
export const tokenLine = (token = TOKEN_PLACEHOLDER) =>
  `export OPENINGS_TOKEN=${token}`;

/**
 * The lines for the shell's startup file: the token, and the address when the
 * Claude Code plugin's default is not where Openings answers.
 */
export function exportLines(origin: string, token = TOKEN_PLACEHOLDER) {
  const lines = [tokenLine(token)];
  if (trimmed(origin) !== PLUGIN_ORIGIN)
    lines.push(`export OPENINGS_URL=${trimmed(origin)}`);
  return lines.join("\n");
}

/** How an agent adds Openings: its MCP address and the token's variable. */
export function connectSnippet(client: ClientId, origin: string) {
  const endpoint = `${trimmed(origin)}/mcp/`;
  if (client === "plugin")
    return "/plugin marketplace add VincenzoImp/openings-job-search\n/plugin install openings@openings-job-search";
  if (client === "codex")
    return `# ~/.codex/config.toml\n[mcp_servers.openings]\nurl = "${endpoint}"\nbearer_token_env_var = "OPENINGS_TOKEN"`;
  if (client === "json")
    return JSON.stringify(
      {
        mcpServers: {
          openings: {
            type: "http",
            url: endpoint,
            headers: { Authorization: "Bearer ${OPENINGS_TOKEN}" },
          },
        },
      },
      null,
      2,
    );
  return `claude mcp add --transport http openings ${endpoint} \\\n  --header 'Authorization: Bearer \${OPENINGS_TOKEN}'`;
}

/** How to see that the agent reached Openings, per client. */
export const CLAUDE_CHECK =
  "Check it: claude mcp list shows openings ✔ Connected.";

/** The first session: three prompts, in order, and what each one does. */
export const FIRST_SESSION = [
  {
    prompt: "Set up my Openings workspace from my CV",
    result:
      "Fills your Profile from your CV and Preferences from a few questions.",
  },
  {
    prompt: "Go through my new jobs",
    result: "Shortlists or dismisses each new job, with a reason.",
  },
  {
    prompt: "Prepare CV and letter for my shortlist",
    result: "Tailors a CV and letter for each; finished ones are Ready.",
  },
] as const;

/** The project's repository, where help is asked for. */
export const REPOSITORY = "https://github.com/VincenzoImp/openings-job-search";

/** Where to go with a problem, a question or a vulnerability. */
export const HELP_LINKS = [
  { label: "Report a problem", href: `${REPOSITORY}/issues/new/choose` },
  { label: "Ask a question", href: `${REPOSITORY}/discussions` },
  { label: "Security", href: `${REPOSITORY}/security/policy` },
];

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
  if (provider.policy.enabled === false)
    return { tone: "neutral", text: "Off" };
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
