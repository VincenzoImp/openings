# Backup and operations

## Portable backup

Use **Settings → Backup and restore → Download a backup**, authenticated `GET /api/v1/backup`, or the MCP
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
omits binary file contents and is not a restorable backup. Download it with
**Export records** in the same tab, `GET /api/v1/export`, or the scoped `workspace_export` MCP grant. Use the
backup action to capture changes from an active WAL journal consistently.

## Backups

The server keeps its own copies of the workspace on the data volume, without a
cron job or any setup:

- **Daily backups.** About once a day the worker writes
  `openings-<UTC time>.sqlite` into `OPENINGS_BACKUP_DIR` (default: a `backups`
  folder beside the workspace file, `/data/backups` in the container). Each copy
  is the whole workspace, written with `VACUUM INTO` under a temporary name,
  checked with `quick_check`, made readable by the server user only (0600) and
  then renamed into place. The newest `OPENINGS_BACKUP_KEEP` (default 3) are kept;
  `0` turns daily backups off. When the volume has less than 1.2 times the
  database size free, the backup is skipped with a warning in the log and tried
  again on the next cycle.
- **Copies before an upgrade.** Before a new release upgrades the workspace
  format in place, it writes `openings.pre-schema<old>-<UTC time>.sqlite` beside
  the workspace, verified the same way. When the volume has less than 2.2 times
  the database size free, or the copy fails its check, the server does not start
  and says how much space it needs; the workspace file is not touched. The two
  most recent copies are kept.

**Settings → Backup and restore → Automatic backups** (owner only) shows when the
last daily backup was written and how many are kept, lists every copy with
Download, and lets you delete a copy taken before an upgrade once you no longer
need to go back (daily backups rotate by themselves). Over REST, as the owner or
with an owner token: `GET /api/v1/backups`, `GET /api/v1/backups/{name}` and
`DELETE /api/v1/backups/{name}` (pre-upgrade copies only). These copies include
the password hash, the session secret and the token hashes, so an agent token is
refused and no MCP tool reaches them. `GET /health` reports the age of the
newest daily backup (`backup.last_at`, `age_hours`, `ok`) and the worker's
heartbeat (`worker.heartbeat_age_seconds`); it answers 503 when the worker has
stopped cycling, so the container healthcheck fails.

To restore a daily backup, download it and restore it under **Restore** below.

These copies live on the same disk as the workspace. Copying them to another
machine is your job; for example, from the Docker host:

```bash
# Copy new backups of the named volume to another machine (older ones stay there).
rsync -a "$(docker volume inspect openings_workspace --format '{{ .Mountpoint }}')/backups/" \
  backup-host:openings-backups/
# Or keep versioned, encrypted copies with restic.
restic -r sftp:backup-host:openings-restic backup \
  "$(docker volume inspect openings_workspace --format '{{ .Mountpoint }}')/backups"
```

## Restore or move hosts

On the destination host, install the same Openings release and set its owner
password. Restore under **Settings → Backup and restore** (marked Owner only:
choose the file and type RESTORE to confirm) or `POST /api/v1/backup/restore` with the raw
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
checked again before the database is replaced. **Settings → Backup and restore** and
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
[Configuration](configuration.md) lists every setting with its default.

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
Settings → Workspace, Retention shows the period in use; Collection → Runs and
tasks lists what is kept.

A source refresh that only sees a posting again is recorded on the posting
(`last_seen_at` in the job's sources), not as an event. When a refresh changes
the title, company, location or posting text, the job gets one `job_refreshed`
event that names the changed fields. A posting keeps its source key and the
employer's apply link a job board reported; the provider's full response is not
stored.

## Access controls

Settings supports named API tokens of two kinds, independent token revocation and
owner password changes; the parts that need owner authority (tokens, restore,
the password, the automatic backups) are marked **Owner only**. An **agent** token cannot change the password, manage
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
`workspace_restore` expire after 120 seconds and work once; request a new
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

## Roll back an upgrade

When a release that upgraded the workspace format misbehaves, go back to the
previous image with the copy it kept:

```bash
docker compose down
# The container's volume, e.g. /var/lib/docker/volumes/openings_workspace/_data
cd "$(docker volume inspect openings_workspace --format '{{ .Mountpoint }}')"
mv openings.sqlite openings.failed-upgrade.sqlite
rm -f openings.sqlite-wal openings.sqlite-shm
cp -p openings.pre-schema<old>-<UTC time>.sqlite openings.sqlite
# Pin the previous release, e.g. OPENINGS_IMAGE=docker.io/vincenzoimp/openings:<previous>
docker compose up -d
```

Changes made after the upgrade are not in the copy. An earlier release cannot
open a workspace upgraded by a later one, so the copy is the only way back.

## Upgrade the workspace format

The server keeps a verified copy of the workspace before every in-place upgrade
([Backups](#backups)); downloading a backup first is still a good idea. A release
upgrades the workspace to its schema on start, in one transaction, and a restore
upgrades a copy of an older backup the same way; the uploaded file is not changed.
A workspace cannot be opened by an earlier release ([Roll back an
upgrade](#roll-back-an-upgrade)). Workspaces older than 0.23 must be opened once
with 0.23 first; release history is in [CHANGELOG.md](../../CHANGELOG.md).

After an upgrade that frees space, the start takes longer once: the database file
is rewritten without the freed space (seconds on an SSD, longer on slow storage).
This needs free space on the data volume of about twice the database's new size
plus 64 MiB. Without it the step is skipped with a log message, the file keeps its
size and the freed space is reused by later writes; the next start tries again.
The same rewrite runs at any start when at least a quarter of the file and
`OPENINGS_COMPACT_MIN_MB` (default 32) are free, for example after forgetting many
jobs. An interruption leaves the previous file intact.
