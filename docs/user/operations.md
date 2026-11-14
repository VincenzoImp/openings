# Operations

## Update

Read the [changelog](../../CHANGELOG.md), back up, then:

```bash
git pull
docker compose pull
docker compose up -d
```

Compose pins the release in `docker-compose.yml`. Other commands:

```bash
docker compose ps
docker compose logs --tail=100 openings
docker compose restart openings
docker compose down
```

`down` keeps the volume. **`down --volumes` deletes the workspace**, including every
document. To change `.env`, run `docker compose up -d` so the container is
recreated; `OPENINGS_PASSWORD` never resets an existing owner. See
[Configuration](configuration.md).

## Reach it from other devices

Set the address clients can reach in `.env`, then `docker compose up -d`:

```dotenv
OPENINGS_BIND=0.0.0.0
OPENINGS_PORT=8080
OPENINGS_PUBLIC_URL=http://openings.example:8080
```

`OPENINGS_PUBLIC_URL` controls MCP host checks and the file-transfer links agents
use; it must match the origin clients use. Set the owner password first, and use
HTTPS through a trusted reverse proxy on any untrusted network. Behind a proxy, set
`OPENINGS_TRUSTED_PROXIES` to its address as the container sees it, so sign-in
limits and secure cookies use each browser's real address. Without it every client
shares the proxy's limit.

Sign-in allows 10 attempts per client address per minute; after more than 10
failures across all clients within 15 minutes, attempts are spaced out until a
sign-in succeeds. API and MCP tokens are not affected.

## Backups

The database is not encrypted and backups hold personal data: keep them private.

**Download backup** under **Settings › Data**, or:

```bash
curl --fail "$OPENINGS_URL/api/v1/backup" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" --output openings-backup.sqlite
```

It is one consistent SQLite file with all documents and settings, taken while the
service runs. A backup taken with an agent token leaves out the password hash,
session secret and tokens. **Export records** gives JSON for reading; it has no
file bytes and cannot be restored.

**Automatic backups.** About once a day the server writes
`openings-<UTC time>.sqlite` into `OPENINGS_BACKUP_DIR` (`/data/backups`), checked
and readable only by the server user. The newest `OPENINGS_BACKUP_KEEP` (3) stay;
`0` turns them off. With less than 1.2 times the database size free, a backup is
skipped with a warning. **Settings › Data › Automatic backups** (owner
only) lists them with **Download**. Over REST: `GET /api/v1/backups`,
`GET /api/v1/backups/{name}` and `DELETE /api/v1/backups/{name}`, for owners only.
`GET /health` reports the newest backup's age and the worker's heartbeat, and
answers 503 if the worker stopped.

These copies sit on the same disk. Copy them elsewhere yourself, for example:

```bash
rsync -a "$(docker volume inspect openings_workspace --format '{{ .Mountpoint }}')/backups/" \
  backup-host:openings-backups/
```

## Restore or move hosts

Install the same release on the destination and set its owner password. Under
**Settings › Data** (owner only), choose **Restore from backup…** and the file,
or send it with an owner token:

```bash
curl --fail "$OPENINGS_URL/api/v1/backup/restore" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H 'Content-Type: application/vnd.sqlite3' --data-binary @openings-backup.sqlite
```

Restore checks integrity, keeps the destination's owner credentials and tokens,
and clears pending upload and download links. `.env` stays host-local. Check the enabled
sources after moving. The restore limit follows the free space of the data volume
(about four times the backup's size when restoring over itself); Settings shows it,
and a larger upload is refused with `413 backup_size`.

## Upgrades

A release opens a workspace of its own data format or of the **previous format
only**, and upgrades the latter at start. An older one is refused with the release
to open it with first; a newer one is refused too. Most releases keep the format;
the [changelog](../../CHANGELOG.md) says when one changes it, with its upgrade
notes. Back up before upgrading.

The upgrade builds a new file with the data copied in, so an upgraded workspace has
exactly the layout of a new one. It needs free space of about 2.2 times the
database; if there is not enough, the server does not start and changes nothing.
The original is kept byte for byte beside the database as
`openings.pre-<release>.sqlite` and is never deleted automatically; delete it
under **Settings › Data › Automatic backups** when you no longer need to go back.
Records and fields the release no longer keeps are written to
`openings.pre-<release>-archive.json` beside it, readable only by the owner of the
file. If a check fails, the start stops with the reason and the original is
untouched.

**Roll back** with the copy, here from the upgrade to 0.24:

```bash
docker compose down
cd "$(docker volume inspect openings_workspace --format '{{ .Mountpoint }}')"
mv openings.sqlite openings.failed-upgrade.sqlite
rm -f openings.sqlite-wal openings.sqlite-shm
cp -p openings.pre-0.24.sqlite openings.sqlite
# Set OPENINGS_IMAGE in .env to the previous release, then:
docker compose up -d
```

Changes made after the upgrade are not in the copy.

## Storage and retention

Finished collection runs and their tasks are removed after 90 days
(`OPENINGS_RETENTION_DAYS`; `0` keeps all); the 20 newest runs of every source
stay. Job and application history is never pruned. A refresh that only sees a
posting again records nothing. At start, a database with a quarter of its size
and `OPENINGS_COMPACT_MIN_MB` free is rewritten without the free space; this needs
about twice the new size free and may take a while once. **Settings › Data**
shows the size, free space and retention.

## Security

- Set `OPENINGS_PASSWORD`, or choose the password in the dashboard, before binding
  beyond localhost.
- Revoke a token in Settings to end its access on its next request. Changing the
  password signs out browsers and keeps tokens.
- Download links for backups and exports work once and expire after 120 seconds.
- Report vulnerabilities as described in [SECURITY.md](../../SECURITY.md).

## Troubleshooting

| Symptom | Check |
|---|---|
| Sign-in returns 429 for everyone behind a proxy | Set `OPENINGS_TRUSTED_PROXIES` and recreate the container. |
| A download link returns `transfer_used` | A link works once; request a new one. |
| MCP rejects the host, or links point to the wrong machine | Set `OPENINGS_PUBLIC_URL` to the origin clients use. |
| A job has incomplete text | Open the job's `…` › **Correct details** and paste the posting. |
| A source is waiting | Read the reason and the time it resumes; a pause of a job site survives restarts. |
| Starting an application returns 409 | Open the existing open attempt named in the error. |
| An upload fails | Check the size (20 MiB), the upload link's age and that the revision is still incomplete. |
| An edit returns 409 | Reload, then apply your change again. |
| The core cannot create SQLite | Make `/data` writable by UID/GID 10001. |

## Container details

The single `openings` container has a Compose budget of 0.5 CPU and 512 MiB; leave
room for the host. The `workspace` volume holds `/data/openings.sqlite`, its
journals and every uploaded file. The core runs as UID/GID 10001, so a
bind-mounted `/data` must be writable by it; the default named volume is.
