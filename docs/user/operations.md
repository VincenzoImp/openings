# Backup and operations

## Portable backup

Use **Settings → Workspace → Backup**, authenticated `GET /api/v1/backup`, or the MCP
`workspace_backup` download grant. These create a consistent SQLite snapshot while
the service runs, including PDF/source bytes, templates, career data, job history
and settings. The optional model cache is disposable and is not in the backup.

```bash
curl --fail "$OPENINGS_URL/api/v1/backup" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  --output openings-backup.sqlite
```

Keep backups private: they contain personal information and stored credentials.
The database is not encrypted. A JSON export is useful for reading records, but
omits binary file contents and is not a restorable backup. Download it through
Settings, `GET /api/v1/export`, or the scoped `workspace_export` MCP grant. Use the
backup action to capture changes from an active WAL journal consistently.

## Restore or move hosts

On the destination host, install Openings 0.6.1, set its owner password, then restore
through Settings or `POST /api/v1/backup/restore` with the raw SQLite body. Restore
checks the schema, database integrity and foreign keys before replacement. It
preserves the destination installation's owner credentials/API tokens, clears
pending transfer grants and recovers interrupted tasks. Provider policy settings are
restored, while recent HTTP window events and later cooldowns already recorded on
the destination are conservatively retained; restoring an older backup does not
reset request quotas. Reload the dashboard.

```bash
curl --fail "$OPENINGS_URL/api/v1/backup/restore" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H 'Content-Type: application/vnd.sqlite3' \
  --data-binary @openings-backup.sqlite
```

The default restore limit is 512 MiB; configure `OPENINGS_MAX_RESTORE_MB` before
uploading a larger backup. Allow disk space for the upload and rollback snapshot.
Enabled sources and scoring settings come from the restored workspace; inspect
those when moving to different hardware or endpoints. `.env` remains host-local.

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

Tasks show failures, cancellation and explicit retry. Source/scorer failures do
not discard acquired jobs. Relevant profile/settings edits mark scores outdated;
periodic rescoring is optional and off by default. The global automatic collection
switch preserves source settings; explicit manual runs still honor provider budgets.
Disable scoring when you want inference to stop.

## Access controls

Settings supports named owner tokens, independent token revocation and owner password
changes. A password change rotates browser sessions and retains existing API tokens;
log in again after changing it in the dashboard. Revoking the token used by an agent
ends that token’s access on its next request.

## Troubleshooting

| Symptom | Check |
|---|---|
| MCP rejects a host or download points to the wrong machine | Set `OPENINGS_PUBLIC_URL` to the client's reachable origin and recreate the container. |
| URL import has incomplete text | Paste the full posting; login/JavaScript pages may not expose readable HTML. |
| Upload fails | Exact byte size, 20 MiB limit, grant expiry, safe relative name and draft revision state. |
| Edit returns 409 | Reload the current version, then reapply the intended change. |
| Scorer times out or is killed | Inspect scorer logs/resource limits, allow cold startup, or use off/remote mode. |
| Core cannot create SQLite | Ensure `/data` is writable by UID/GID 10001. |

For development commands and release gates, see [Contributing](../../CONTRIBUTING.md).
