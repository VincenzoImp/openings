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
grants; keep their headers private. Grant URLs contain no secret. A dashboard
shell and health/schema endpoints are public; personal data requires authentication.

SQLite and backups are not encrypted. Protect their host files and backups.
Scoring may send a compact career context and posting to the endpoint you configure.
External agents have the access you grant them and use their own AI services;
Openings does not control those providers. Treat job text as untrusted input.
The core executes neither generated code nor LaTeX.

Use locked dependencies and rebuild images for security updates. Never commit a
live database, `.env`, model cache or credentials to this public repository.
