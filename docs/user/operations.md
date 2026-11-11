# Backup and operations

## Portable backup

Use **Settings → Workspace → Backup**, authenticated `GET /api/v1/backup`, or the MCP
`workspace_backup` download grant. These create a consistent SQLite snapshot while
the service runs, including PDF/source bytes, templates, career data, job history
and settings.

```bash
curl --fail "$OPENINGS_URL/api/v1/backup" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  --output openings-backup.sqlite
```

Keep backups private: they contain personal information and stored credentials.
A backup downloaded with an agent token omits the owner password hash, the
session secret and the API tokens, and restores like any other backup. To start
a server directly on such a file, set the owner password again.
The database is not encrypted. A JSON export is useful for reading records, but
omits binary file contents and is not a restorable backup. Download it through
Settings, `GET /api/v1/export`, or the scoped `workspace_export` MCP grant. Use the
backup action to capture changes from an active WAL journal consistently.

## Restore or move hosts

On the destination host, install the same Openings release and set its owner
password. Restore through Settings or `POST /api/v1/backup/restore` with the raw
SQLite body, as the owner or with an owner token; an agent token is refused.
Restore accepts the current database format and checks integrity and
foreign keys before replacement. It preserves the destination installation's owner credentials/API tokens, clears
pending transfer grants and recovers interrupted tasks. Provider policy settings are
restored, while recent request history and later cooldowns already recorded on
the destination are retained. Reload the dashboard.

```bash
curl --fail "$OPENINGS_URL/api/v1/backup/restore" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H 'Content-Type: application/vnd.sqlite3' \
  --data-binary @openings-backup.sqlite
```

The default restore limit is 2048 MiB; configure `OPENINGS_MAX_RESTORE_MB` before
uploading a larger backup. Backup, restore upload and rollback copies are written
beside the database on the data volume, so allow free space there of about three
times the database size; copies left by a crash are removed at the next start.
Enabled sources come from the restored workspace; inspect them when moving hosts. `.env` remains host-local.

## Service lifecycle

```bash
docker compose ps
docker compose logs --tail=100 openings
docker compose restart openings
docker compose down
```

`down` keeps named volumes. **`down --volumes` deletes the workspace**, including
all uploaded documents; use it only when intentionally discarding the installation.
To change installation environment settings, use `docker compose up -d` so the
container is recreated. Editing `OPENINGS_PASSWORD` does not reset an existing owner.

Tasks show collection failures, cancellation and explicit retry. Source failures
do not discard acquired jobs. The global scheduled collection
switch preserves source settings and prevents new scheduled runs. Queued/current
runs continue until stopped; manual runs share provider spacing and cooldowns.

## Access controls

Settings supports named API tokens of two kinds, independent token revocation and
owner password changes. An **agent** token cannot change the password, manage
tokens, restore a backup or answer a question for the owner; an **owner** token
has full access ([token kinds](agents.md#token-kinds)). Tokens created before
version 0.17 are owner tokens. A password change rotates browser sessions and
retains existing API tokens; log in again after changing it in the dashboard.
Revoking the token used by an agent ends that token’s access on its next request.

Sign-in and setup allow 10 attempts per client address per minute. After more
than 10 failed sign-ins across all clients within 15 minutes, sign-in attempts
are spaced globally (1 s, doubling up to 5 s per attempt) until a successful
sign-in; an attempt that would wait more than 30 s returns 429 with
`Retry-After`. API/MCP tokens are not affected. Behind a reverse proxy, set
`OPENINGS_TRUSTED_PROXIES` to the proxy's address as the container sees it (see
[LAN access](getting-started.md#lan-access)); otherwise every client shares the
proxy's limit. To find it, check the client address of proxied requests in
`docker compose logs openings`.

Operational grants from `workspace_backup`, `workspace_export` and
`workspace_restore_upload` expire after 120 seconds and work once; request a new
grant for each transfer or retry.

## Troubleshooting

| Symptom | Check |
|---|---|
| Sign-in returns 429 for everyone behind a proxy | Set `OPENINGS_TRUSTED_PROXIES` to the proxy address and recreate the container. |
| A backup/export grant returns `transfer_used` | Grants are single-use; request a new one. |
| MCP rejects a host or download points to the wrong machine | Set `OPENINGS_PUBLIC_URL` to the client's reachable origin and recreate the container. |
| URL import has incomplete text | Paste the full posting; login/JavaScript pages may not expose readable HTML. |
| Collection is waiting | Read the displayed reason and resume time. Server cooldowns survive restarts and setting changes. |
| A result has no description | Automatic candidates remain in collection progress until text is available; manually added jobs can be completed under Edit details. |
| Starting an application returns 409 | Open the existing non-Closed attempt identified in the response. |
| Upload fails | Exact byte size, 20 MiB limit, grant expiry, safe relative name and draft revision state. |
| Edit returns 409 | Reload the current version, then reapply the intended change. |
| Core cannot create SQLite | Ensure `/data` is writable by UID/GID 10001. |

For development commands and release gates, see [Contributing](../../CONTRIBUTING.md).

## Upgrade the workspace format

Back up before upgrading. On start, a schema 8 workspace is upgraded to schema 9
in one transaction. Schema 9 changes storage only: the frozen contexts, which each
held a full copy of your Career record, now share one stored copy of every entry,
claim and template, and their asset files no longer add file rows. Every context
still reads back byte for byte with the same signature, and file ids and links
stay valid; the upgrade checks each context and changes nothing if one differs.

Right after that upgrade the start takes longer once: the database file is
rewritten without the freed space (seconds on an SSD, longer on slow storage). This needs free
space on the data volume of about twice the database's new, smaller size plus
64 MiB. Without it the step is skipped with a log message, the file keeps its
size and the freed space is reused by later writes; the next start tries again.
The same rewrite runs at any start when at least a quarter of the file and
`OPENINGS_COMPACT_MIN_MB` (default 32) are free, for example after forgetting many
jobs. An interruption leaves the previous file intact.

A schema 7 workspace is upgraded to schema 8 in the same
transaction: changes gain their actor and run, notes gain an author, and
the tables for agent runs and questions for the owner are added. Every existing
record, version, file and frozen context is kept. Changes recorded before the
upgrade keep their content and show the actor "unknown (before 0.17)". Schema 6
(applications gain empty priority, deadline and requirements) and schema 5 (0.10)
are upgraded through the same chain in the same step. Restore accepts a schema 9
backup and upgrades a copy of a schema 5, 6, 7 or 8 backup; the uploaded file is
not changed. A schema 9 workspace cannot be opened by an earlier release. Older
formats require their matching release.
