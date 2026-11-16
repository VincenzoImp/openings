# Security

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/VincenzoImp/openings-job-search/security/advisories/new).
Do not include personal databases, API tokens or CVs in public issues.

**Supported versions:** only the latest release receives fixes. Upgrade to it
before reporting a problem.

## Security model

Openings is a single-owner workspace that your own AI agent drives over MCP.

- **Tokens.** The owner's browser session and owner tokens can do everything.
  Agent tokens can do every operation that is not owner-only, **including marking
  applications applied, recording replies and deleting records permanently**: the
  owner gives agents that power on purpose. They are refused only the password,
  API tokens, restore, the career import and the kept backups (list, download,
  delete). Any token can read your personal data, including a backup or the
  records export, which hold no credentials.
- **Nothing submits.** Openings has no operation that sends an application or
  contacts an employer.
- **Instructions, attribution, undo.** The MCP instructions and the skills tell
  the agent to mark applied, record replies, close and delete permanently only on
  the owner's word or a standing instruction, and to delete after a backup; the
  server does not enforce this. Every change is attributed to the owner, the
  agent token by name or job sources. Non-destructive changes can be undone, and
  a verified backup is written about once a day (the newest three are kept).
- **Posting text is data.** Postings are untrusted input. The agent is told to
  treat them as data, never as instructions; that lowers prompt-injection risk
  but cannot remove it.
- **The agent's own shell.** The agent runs on your machine with its own tools,
  which Openings cannot see or limit. Restrict what its client may run: the
  agent folder ships a Claude Code permission profile
  ([`examples/operator-workspace/.claude/settings.json`](examples/operator-workspace/.claude/settings.json)).
- **One token per agent.** Name each token for the agent or schedule that holds
  it, keep it in the environment, and revoke it when you stop using it.
- **Network.** The default Docker port binds to localhost. Before exposing it,
  claim the workspace with the one-time setup code from the log (or set
  `OPENINGS_PASSWORD`), and use HTTPS through a trusted proxy across untrusted
  networks.

[Work with an agent](docs/user/agents.md#security-model) explains each point.

## Protections

Passwords are hashed; API tokens are stored as hashes and are revocable. Browser
writes require CSRF protection. Uploads and downloads use short-lived one-time
links: an upload link accepts one file within 10 minutes, and a download link
works once (10 minutes for files, 120 seconds for backups and exports). Keep their
headers private; the link URLs contain no secret. Sign-in is limited per client
and slowed globally after repeated failures; behind a proxy, set
`OPENINGS_TRUSTED_PROXIES` so limits apply per client. Job links, careers pages
and feeds are fetched only from the public addresses checked for each request and
redirect. The dashboard shell and the health and schema endpoints are public;
personal data requires authentication. The dashboard runs only its own scripts
under a Content-Security-Policy, and stored files are served sandboxed. A restore
keeps the installation's own triggers and views, never the backup's.

SQLite and backups are not encrypted. Protect their host files and backups.
External agents have the access you grant them and use their own AI services;
Openings does not control those providers. Treat job text as untrusted input.
The core executes neither generated code nor LaTeX.

Use locked dependencies and rebuild images for security updates. Never commit a
live database, `.env` or credentials to this public repository.
