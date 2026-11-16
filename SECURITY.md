# Security

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/VincenzoImp/openings-job-search/security/advisories/new).
Do not include personal databases, API tokens or CVs in public issues.

**Supported versions:** only the latest release receives fixes. Upgrade to it
before reporting a problem.

## Security model

Openings is a single-owner workspace that your own AI agent drives over MCP.

- **Tokens.** Owner tokens can do everything; agent tokens can do everything but the
  owner-only actions (password, API tokens, restore, career import, kept backups),
  **including marking applied and deleting permanently**; any token reads personal
  data ([details](docs/user/agents.md#what-an-agent-token-can-do)).
- **Nothing submits.** No operation sends an application to an employer or contacts
  one; marking applied only records it
  ([details](docs/user/agents.md#what-nothing-in-openings-can-do)).
- **Instructions, attribution, undo.** The skills, not the server, tell the agent to
  mark applied, close and delete only on the owner's word; every change names its
  author, non-destructive changes can be undone, and a verified backup is kept daily
  ([details](docs/user/agents.md#attribution-and-undo)).
- **Posting text is data.** Postings are untrusted input that the agent is told
  never to follow, which lowers prompt-injection risk but cannot remove it
  ([details](docs/user/agents.md#posting-text-is-data)).
- **The agent's own shell.** Openings cannot see or limit the agent's own tools, so
  restrict its client with the shipped permission profile
  ([`examples/operator-workspace/.claude/settings.json`](examples/operator-workspace/.claude/settings.json);
  [details](docs/user/agents.md#the-risk-that-remains-the-agents-own-shell)).
- **One token per agent.** Name each token for its agent or schedule, keep it in the
  environment and revoke it when unused
  ([details](docs/user/agents.md#tokens-and-the-network)).
- **Network.** The Docker port binds to localhost; before exposing it, claim the
  workspace with the setup code (or `OPENINGS_PASSWORD`) and use HTTPS through a
  trusted proxy ([details](docs/user/operations.md#reach-it-from-other-devices)).

[Work with an agent](docs/user/agents.md#security-model) explains each point.

## Protections

- **Credentials.** Passwords are hashed; API tokens are stored as hashes and are
  revocable.
- **Browser writes.** They require CSRF protection.
- **File links.** Uploads and downloads use short-lived one-time links: an upload
  link accepts one file within 10 minutes, and a download link works once (10
  minutes for files, 120 seconds for backups and exports). Keep their headers
  private; the link URLs contain no secret.
- **Sign-in.** Limited per client and slowed globally after repeated failures;
  behind a proxy, set `OPENINGS_TRUSTED_PROXIES` so limits apply per client.
- **Outbound fetches.** Job links, careers pages and feeds are fetched only from the
  public addresses checked for each request and redirect.
- **Authentication.** The dashboard shell and the health and schema endpoints are
  public; personal data requires authentication.
- **Dashboard.** It runs only its own scripts under a Content-Security-Policy, and
  stored files are served sandboxed.
- **Restore.** It keeps the installation's own triggers and views, never the
  backup's.

SQLite and backups are not encrypted. Protect their host files and backups.
External agents have the access you grant them and use their own AI services;
Openings does not control those providers. Treat job text as untrusted input.
The core executes neither generated code nor LaTeX.

Use locked dependencies and rebuild images for security updates. Never commit a
live database, `.env` or credentials to this public repository.
