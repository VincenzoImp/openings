# Security

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/VincenzoImp/openings/security/advisories/new).
Do not include personal databases, API tokens or CVs in public issues.

**Supported versions:** only the latest release receives fixes. Upgrade to it
before reporting a problem.

## Access

Openings is a single-owner workspace. The owner's browser session and owner
tokens can do everything. Agent tokens can do the whole job search but not the
owner-only actions: the password, API tokens, restore, the records export, the
career import and downloading kept backups. Any token can read your personal
data, so give each agent its own token and revoke it when you stop using it.

The default Docker port binds to localhost. Set the owner password before exposing
it on a LAN, and use HTTPS through a trusted proxy across untrusted networks.

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
personal data requires authentication.

SQLite and backups are not encrypted. Protect their host files and backups.
External agents have the access you grant them and use their own AI services;
Openings does not control those providers. Treat job text as untrusted input.
The core executes neither generated code nor LaTeX.

Use locked dependencies and rebuild images for security updates. Never commit a
live database, `.env` or credentials to this public repository.
