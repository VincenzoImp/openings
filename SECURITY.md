# Security

Report a vulnerability here, and read what stays yours when your agent works your
job search.

## Report a vulnerability

Report it privately through
[GitHub security advisories](https://github.com/VincenzoImp/openings-job-search/security/advisories/new).
Do not include personal databases, API tokens or CVs in public issues.

**Supported versions:** only the latest release receives fixes. Upgrade to it
before reporting a problem.

## Security model

Openings is a single-owner workspace, and your own AI agent works in it over MCP.
[Work with an agent](docs/user/agents.md#security-model) explains each point.

- **Tokens.** An agent token can do everything but the owner-only actions,
  including marking applied and deleting permanently
  ([details](docs/user/agents.md#what-an-agent-token-can-do)).
- **Nothing submits.** Nothing in Openings can submit an application to an
  employer or contact one; Mark applied only records what you did
  ([details](docs/user/agents.md#what-nothing-in-openings-can-do)).
- **Instructions.** The skills, not the server, tell your agent to mark applied,
  close and delete only on your word
  ([details](docs/user/agents.md#security-model)).
- **Attribution and undo.** Every change names its author, non-destructive
  changes can be undone, and a verified backup is kept daily
  ([details](docs/user/agents.md#attribution-and-undo)).
- **Posting text is data.** Your agent is told never to follow posting text,
  which lowers prompt-injection risk but cannot remove it
  ([details](docs/user/agents.md#posting-text-is-data)).
- **The agent's own shell.** Openings cannot see or limit your agent's own tools,
  so restrict its client with the shipped
  [permission profile](examples/operator-workspace/.claude/settings.json)
  ([details](docs/user/agents.md#the-risk-that-remains-the-agents-own-shell)).
- **One token per agent.** Name each token for its agent or schedule, keep it in
  the environment and revoke it when unused
  ([details](docs/user/agents.md#tokens-and-the-network)).
- **Network.** Claim the workspace with the setup code, and use HTTPS through a
  trusted proxy before exposing the port
  ([details](docs/user/operations.md#reach-it-from-other-devices)).

## Protections

- **Credentials.** Passwords and API tokens are stored as hashes, and tokens are
  revocable.
- **Browser writes.** Every browser write requires CSRF protection.
- **File links.** An upload or download link works once and expires after 10
  minutes, or 120 seconds for backups and exports. The secret is in the link's
  header, never in its URL.
- **Sign-in.** Attempts are limited per client and slowed globally after repeated
  failures; behind a proxy, set `OPENINGS_TRUSTED_PROXIES`.
- **Outbound fetches.** Job links, careers pages and feeds are fetched only from
  public addresses, checked for each request and redirect.
- **Authentication.** Only the dashboard shell and the health and schema
  endpoints are public; personal data requires authentication.
- **Dashboard.** The dashboard runs only its own scripts under a
  Content-Security-Policy, and stored files are served sandboxed.
- **Restore.** A restore keeps the installation's own triggers and views, never
  the backup's.
- **No generated code.** The core executes neither generated code nor LaTeX.

## What you protect

- **Your files.** SQLite and backups are not encrypted, so protect their host
  files and copies.
- **Your agent's provider.** Your agent has the access you grant it and uses its
  own AI service, which Openings does not control.
- **Your images.** Use locked dependencies, and rebuild images for security
  updates.
- **Your repository.** Never commit a live database, `.env` or credentials.
