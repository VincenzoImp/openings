# Operations

Keep your installation running here: update it, reach it from other devices,
back it up, restore it and fix what goes wrong.

## Update

Read the [changelog](../../CHANGELOG.md) and take a backup with **Settings › Data
› Download backup**. Then update the way you installed:

- **`docker run`:** pull the image and replace the container, then run the
  same `docker run` line as at install, with your own options such as
  `OPENINGS_PUBLIC_URL`. The `openings` volume keeps your workspace.

  ```bash
  docker pull vincenzoimp/openings:latest && docker rm -f openings
  docker run -d --name openings -p 127.0.0.1:8080:8080 -v openings:/data --read-only --tmpfs /tmp --restart unless-stopped vincenzoimp/openings:latest
  ```

- **Docker Compose:** run `docker compose pull && docker compose up -d` in the
  folder of `docker-compose.yml`. The file pins a minor release, such as `0.28`,
  so this brings its patch releases. For a new minor release, download
  `docker-compose.yml` again ([Getting started](getting-started.md#use-it)), or
  set `OPENINGS_IMAGE` in `.env`.
- **From a clone:** run `git pull`, then the same two Compose commands.

Other Compose commands:

```bash
docker compose ps
docker compose logs --tail=100 openings
docker compose restart openings
docker compose down
```

`down` keeps the volume, but `down --volumes` deletes the workspace, and so does
`docker volume rm openings`. After you change `.env`, run `docker compose up -d`
so the container is recreated. `OPENINGS_PASSWORD` never resets an existing
owner; [Configuration](configuration.md) lists every variable.

### Supported versions

- Only the latest release receives fixes.
- A release opens a workspace of its own data format or of the **previous format
  only**, and upgrades the latter at start.
- An older workspace is refused with the release to open it with first, and a
  newer one is refused too. When you skip releases, the changelog says which one
  to pass through. Opening any older format directly is planned for 1.0.0.
- Releases come at most once a week, unless a fix unblocks someone. No 0.28.x
  release changes the data format.

### Upgrades

When a release changes the format, the upgrade builds a new file with the data
copied in, so an upgraded workspace has exactly the layout of a new one.

- **Space:** the upgrade needs free space of about 2.2 times the database.
  Without enough, the server does not start and changes nothing.
- **The original** is kept byte for byte beside the database as
  `openings.pre-<release>.sqlite` and is never deleted automatically; delete it
  under **Settings › Data › Automatic backups** when you no longer need to go back.
- **Dropped data:** records and fields the release no longer keeps are written to
  `openings.pre-<release>-archive.json` beside it, readable only by the owner of
  the file.
- **Failures:** if a check fails, the start stops with the reason and the original
  is untouched.

### Roll back

After a release that kept the format, run the previous release's tag,
`vincenzoimp/openings:X.Y.Z`, instead of `latest`, as in Update.

After a release that changed the format, here 0.28, stop the container, put the
pre-upgrade copy back in place and start the previous release. With
`docker run`:

```bash
docker stop openings && docker rm openings
docker run --rm -v openings:/data --entrypoint sh vincenzoimp/openings:0.28 -c '
  cd /data && mv openings.sqlite openings.failed-upgrade.sqlite &&
  rm -f openings.sqlite-wal openings.sqlite-shm &&
  cp -p openings.pre-0.28.sqlite openings.sqlite'
docker run -d --name openings -p 127.0.0.1:8080:8080 -v openings:/data \
  --read-only --tmpfs /tmp --restart unless-stopped vincenzoimp/openings:0.27.3
```

With Compose, run `docker compose down`, the same middle command with the volume
`openings_workspace`, set `OPENINGS_IMAGE=vincenzoimp/openings:0.27.3` in `.env`
and run `docker compose up -d`. Changes made after the upgrade are not in the copy;
`openings.failed-upgrade.sqlite` keeps them.

## Reach it from other devices

Open Openings to the other devices on your network, then put HTTPS in front.
[Run it on a server or NAS](getting-started.md#run-it-on-a-server-or-nas) has the
short form. In `.env`:

```dotenv
OPENINGS_BIND=0.0.0.0
OPENINGS_PORT=8080
OPENINGS_PUBLIC_URL=http://openings.example:8080
```

- `OPENINGS_BIND` publishes the port on every interface of the host instead of
  localhost only.
- `OPENINGS_PUBLIC_URL` is the address browsers and agents use. MCP accepts its
  host, and upload and download links start with it, so it must match the origin
  clients use. MCP refuses another host with `421 mcp_host`, in a message that
  names this variable; the dashboard opened at another address shows a notice
  with the value to set. With Compose, its default follows `OPENINGS_PORT`.
- Claim the workspace before anyone else can reach it, with the one-time setup
  code from the log (`docker logs openings`). Or set `OPENINGS_PASSWORD` before
  the first start.

### Put HTTPS in front with a reverse proxy

Use HTTPS on any network you do not trust. Put a reverse proxy in front, and set
`OPENINGS_PUBLIC_URL` to its `https://` address, which makes cookies secure. Set
`OPENINGS_TRUSTED_PROXIES` to the proxy's address as the container sees it, so
sign-in limits apply to each browser's real address. Without it, every client
shares the proxy's limit.

**Caddy** obtains and renews a certificate by itself. Beside
`docker-compose.yml`, add `compose.override.yaml`:

```yaml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    command: caddy reverse-proxy --from openings.example.com --to openings:8080
    volumes: [caddy:/data]
volumes:
  caddy:
```

**Traefik** that already runs with the Docker provider, a `websecure` entry point
and a certificate resolver `le`, on a network called `proxy`:

```yaml
services:
  openings:
    networks: [default, proxy]
    labels:
      - traefik.enable=true
      - traefik.docker.network=proxy
      - traefik.http.routers.openings.rule=Host(`openings.example.com`)
      - traefik.http.routers.openings.entrypoints=websecure
      - traefik.http.routers.openings.tls.certresolver=le
      - traefik.http.services.openings.loadbalancer.server.port=8080
networks:
  proxy:
    external: true
```

Then add the proxy's network range to `.env`. `docker network inspect
openings_default` (Caddy) or `docker network inspect proxy` (Traefik) shows it
under `Subnet`. For example:

```dotenv
OPENINGS_PUBLIC_URL=https://openings.example.com
OPENINGS_TRUSTED_PROXIES=172.18.0.0/16
```

Run `docker compose up -d`. Keep `OPENINGS_BIND` at `127.0.0.1`, since the proxy
reaches Openings over the Docker network. A name that resolves only on your home
network gets no public certificate. In that case, add `--internal-certs` to the Caddy
command and trust Caddy's root certificate on your devices.

Sign-in allows 10 attempts per client address per minute; after more than 10
failures across all clients within 15 minutes, attempts are spaced out until a
sign-in succeeds. API and MCP tokens are not affected.

## Backups

Take a backup before every update, and copy the automatic ones off the machine.
The database is not encrypted and backups hold personal data, so keep them
private.

**Download backup** under **Settings › Data**, or:

```bash
curl --fail "$OPENINGS_URL/api/v1/backup" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" --output openings-backup.sqlite
```

It is one consistent SQLite file with all documents and settings, taken while the
service runs. A backup taken with an agent token leaves out the password hash,
session secret and tokens. **Export records** gives JSON for reading; it has no
file bytes and cannot be restored.

**Automatic backups.** About once a day Openings writes
`openings-<UTC time>.sqlite` into `OPENINGS_BACKUP_DIR` (`/data/backups`), checked
and readable only by the server user. The newest `OPENINGS_BACKUP_KEEP` (3) stay,
and `0` turns them off. With less than 1.2 times the database size free, a backup
is skipped with a warning.

**Settings › Data › Automatic backups** (owner only) lists them with
**Download**. Owners can also use REST: `GET /api/v1/backups`,
`GET /api/v1/backups/{name}` and `DELETE /api/v1/backups/{name}`. `GET /health`
reports the newest backup's age and the worker's heartbeat, and answers 503 if
the worker stopped.

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
and clears pending upload and download links. `.env` stays host-local, so check
the enabled sources after moving. The restore limit follows the free space of the
data volume (about four times the backup's size when restoring over itself).
Settings shows it, and a larger upload is refused with `413 backup_size`.

## Storage and retention

Finished collection runs and their tasks are removed after 90 days
(`OPENINGS_RETENTION_DAYS`; `0` keeps all), and the 20 newest runs of every
source stay. Job and application history is never pruned, and a refresh that only
sees a posting again records nothing. **Settings › Data** shows the size, free
space and retention.

At start, a database with a quarter of its size and `OPENINGS_COMPACT_MIN_MB`
free is rewritten without the free space. This needs about twice the new size
free, and may take a while once.

## Security

- **Claim the workspace** before binding beyond localhost.
- **Revoke a token** in Settings to end its access on its next request. Changing
  the password signs out browsers and keeps tokens.
- **Read the [security model](agents.md#security-model)** for what tokens and
  agents can do, and [SECURITY.md](../../SECURITY.md) for how to report a
  vulnerability.

## Troubleshooting

### Nothing arrives

1. **Is collection on?** The top line of **Sources** shows whether automatic
   checks are paused.
2. **Is the source on and checked?** A paused source is grayed; a source added
   over REST or MCP starts paused. Choose **Check now** and read **Recent checks**.
3. **Did the check fail or wait?** The source row and Recent checks give the
   reason in words, with the time it resumes.
4. **Did it find only known jobs?** A check counts new and already-known jobs
   apart; a narrow query or **Title must include** can leave nothing new.
5. **Are new jobs hidden?** **Hide jobs requiring languages I don't speak** and
   the filters of **Jobs › New** hide jobs; the count of hidden jobs is shown.
6. **Is the worker alive?** `curl -fsS http://127.0.0.1:8080/health` answers
   503 when the background worker stopped; read the logs.

### A job site refused requests

LinkedIn, Indeed and Glassdoor searches use the sites' public guest pages. When a
site answers "too many requests", the source says so, for example:

> LinkedIn refused this request from your network; Openings waits until 14:30
> UTC and tries again. Careers pages are not affected.

Openings pauses requests to that site until then, across restarts, and nothing
needs doing. If a refusal comes every day, check fewer searches, less often, or
space the requests further under **Settings › Advanced**.

Servers in a data center or at a VPS provider are refused far more often than a
home connection, and some sites refuse them outright. Company careers pages are
public job-board APIs and are rarely affected, so on a server, follow the
companies you want there first.

### Other symptoms

| Symptom | Check |
|---|---|
| The setup page asks for a code | It is in the log: `docker logs openings` (Compose: `docker compose logs openings`). Each restart prints a new one until the workspace is claimed. |
| Sign-in returns 429 for everyone behind a proxy | Set `OPENINGS_TRUSTED_PROXIES` and recreate the container. |
| MCP refuses the host, or links point to the wrong machine | Set `OPENINGS_PUBLIC_URL` to the origin clients use, and recreate the container. |
| Your agent cannot upload or download a file | The `curl` line goes to `OPENINGS_PUBLIC_URL`, which the agent's machine must reach; `127.0.0.1` there is the agent's own machine. A link works once and expires after ten minutes, so ask for a new one. |
| An upload fails | Check the size (20 MiB) and that the revision is still incomplete. |
| A job has incomplete text | Open the job's `…` › **Correct details** and paste the posting. |
| Starting an application returns 409 | Open the existing open attempt named in the error. |
| An edit returns 409 | Reload, then apply your change again. |
| The core cannot create SQLite | Make `/data` writable by UID/GID 10001. |

## Container details

The image is `vincenzoimp/openings` on Docker Hub, for linux/amd64 and arm64.
`X.Y.Z` is one release, `X.Y` the newest patch of a minor and `latest` the newest
release. The same image, with the same tags and digest, is at
`ghcr.io/vincenzoimp/openings` for when Docker Hub's anonymous pull limit gets in
the way. To use it, set `OPENINGS_IMAGE=ghcr.io/vincenzoimp/openings:X.Y.Z` in
`.env`.

The single `openings` container has a Compose budget of 0.5 CPU and 512 MiB; leave
room for the host. The `workspace` volume holds `/data/openings.sqlite`, its
journals and every uploaded file. The core runs as UID/GID 10001, so a
bind-mounted `/data` must be writable by it; the default named volume is.
