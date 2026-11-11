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

The restore limit follows the free space on the data volume, because the upload,
the upgraded copy of an earlier-format backup and the rollback copy of the current
database are written beside the database, and the restored pages pass through its
write-ahead log. Restoring a backup of *B* bytes over a database of *D* bytes
needs 3 × *B* + *D* + 64 MiB free, plus *B* − *D* when the backup is the larger
one: about four times the size when you restore a workspace over itself. A larger
upload is refused before it is written, with `413 backup_size` and the backup
size, the free space and the space needed in the error details; the room is
checked again before the database is replaced. **Settings → Workspace** and
`GET /api/v1/workspace` (`workspace_info`) show the database size, the free space
and the largest backup that fits now (`storage`). `OPENINGS_MAX_RESTORE_MB` is an
optional upper bound, unset by default; it can only lower the limit. Copies left
by a crash are removed at the next start.
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

## Retention

Finished collection runs and their tasks are removed 90 days after they were
created; set `OPENINGS_RETENTION_DAYS` to another number of days, or to `0` to
keep everything. The 20 most recent finished runs of every source stay whatever
their age, so each source keeps its last run and its run history. Queued and
running work, including the progress stored with it, is never removed. The
change-log entries of a removed run or task (queued, cancelled, retried) go with
it unless an agent run recorded them. Job and application history is never
pruned. The worker does this at start and every six hours, in small batches;
Settings → Workspace shows the period in use.

A source refresh that only sees a posting again is recorded on the posting
(`last_seen_at` in the job's sources), not as an event. When a refresh changes
the title, company, location or posting text, the job gets one `job_refreshed`
event that names the changed fields. A posting keeps its source key and the
employer's apply link a job board reported; the provider's full response is not
stored.

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

Back up before upgrading. On start, a schema 9 workspace (0.18) is upgraded to
schema 10 (0.19) in one transaction. Schema 10 only adds: the
[policy](policy.md), three typed fields on claims and the policy versions a
prepared application records. The Profile's free-form `metadata` is copied into
unconfirmed **Facts** items and its **Preferences** and **Target roles** text
into unconfirmed **Decision** items; the Profile itself, every Career entry,
claim and template and every frozen context keep each value they had. A claim
whose `metadata` has a key `default_in_cv` (true or false), `role` (`core`,
`supporting` or `bench`) or `group` (a text of at most 100 characters) gets
that value in the typed field of the same name; nothing else is guessed, and
the metadata stays.

A schema 8 workspace (0.17.0) is upgraded through schema 9 in the same
transaction. Schema 9 changes storage only: the frozen contexts, which each
held a full copy of your Career record, now share one stored copy of every entry,
claim and template, and their asset files no longer add file rows. Every context
still reads back byte for byte with the same signature, and file ids and links
stay valid; the upgrade checks each context and changes nothing if one differs.

The same step removes what earlier releases stored without using it. Every
`posting_updated` event that recorded a refresh without a change to the title,
company, location or posting text is deleted; the others become `job_refreshed`
events with those field names, and `posting_updated` no longer appears in the
change log, the overview activity or run change counts. Stored provider responses
are reduced to the source key and the employer's apply link, so the `payload` of
`postings` in a JSON export holds only those two values. Identity lookups,
duplicate candidates, the sources of a job and collection run summaries read the
same as before. Finished collection runs older than the retention period are
removed by the worker after the start, not by the upgrade
([Retention](#retention)). A development database that already has the
unreleased schema 9 is not changed by this step: its old events and payloads
stay until the jobs are refreshed or forgotten.

Right after that upgrade the start takes longer once: the database file is
rewritten without the freed space (seconds on an SSD, longer on slow storage). This needs free
space on the data volume of about twice the database's new, smaller size plus
64 MiB. Without it the step is skipped with a log message, the file keeps its
size and the freed space is reused by later writes; the next start tries again.
The same rewrite runs at any start when at least a quarter of the file and
`OPENINGS_COMPACT_MIN_MB` (default 32) are free, for example after forgetting many
jobs. An interruption leaves the previous file intact.

A schema 7 workspace is upgraded to schema 8, which shipped with 0.17.0, in the same
transaction: changes gain their actor and run, notes gain an author, and
the tables for agent runs and questions for the owner are added. Every existing
record, version, file and frozen context is kept. Changes recorded before the
upgrade keep their content and show the actor "unknown (before 0.17)". Schema 6
(applications gain empty priority, deadline and requirements) and schema 5 (0.10)
are upgraded through the same chain in the same step. Restore accepts a schema 10
backup and upgrades a copy of a schema 5, 6, 7, 8 or 9 backup; the uploaded file is
not changed. A schema 10 workspace cannot be opened by an earlier release. Older
formats require their matching release.
