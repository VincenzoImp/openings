# Security

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/VincenzoImp/openings/security/advisories/new).
Do not include personal databases, API tokens or CVs in public issues.
Security fixes target the latest published release. Upgrade to that release
when reporting a problem.

Openings is a single-owner workspace. Every owner session/API token can read and
change career data, jobs and documents; tokens are not separate restricted roles.
The default Docker port binds to localhost. Set the owner password before exposing
it on a LAN, and use HTTPS through a trusted proxy across untrusted networks.

Passwords are hashed; API tokens are stored as hashes and are revocable. Browser
writes require CSRF protection. File/operational transfers use short-lived scoped
grants; operational grants are single-use. Keep their headers private. Grant URLs
contain no secret. Sign-in is limited per client and slowed globally after repeated
failures; behind a proxy, set `OPENINGS_TRUSTED_PROXIES` so limits apply per client.
URL imports and feed/board fetches connect only to the public addresses checked for
each request and redirect. A dashboard shell and health/schema endpoints are public;
personal data requires authentication.

SQLite and backups are not encrypted. Protect their host files and backups.
External agents have the access you grant them and use their own AI services;
Openings does not control those providers. Treat job text as untrusted input.
The core executes neither generated code nor LaTeX.

Use locked dependencies and rebuild images for security updates. Never commit a
live database, `.env`, model cache or credentials to this public repository.
