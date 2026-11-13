# Configuration

Openings reads a few environment variables at start. With Docker Compose, set
them in `.env` next to `docker-compose.yml` (see [`.env.example`](../../.env.example))
and recreate the container with `docker compose up -d`; a restart alone keeps the
old values. Run from source, export them before `uv run openings`, or pass the
matching command-line option where one exists.

Every other setting lives in the workspace and is changed in the dashboard or
through REST and MCP: collection sources, provider request spacing, Preferences,
tokens and the owner password.

## Server settings

| Variable | Default | What it does | Read by |
|---|---|---|---|
| `OPENINGS_PUBLIC_URL` | unset (Compose: `http://127.0.0.1:8080`) | The origin browsers and agents use. The MCP endpoint accepts this host besides `localhost`, `127.0.0.1` and `[::1]`; session cookies are marked secure when it starts with `https://`; `GET /workspace` and `workspace_info` report it as the origin. | `app.py`, `interfaces/core.py`, `interfaces/system.py` |
| `OPENINGS_PASSWORD` | unset | First-run owner password, at least 10 characters. Used only while no owner password exists; changing it later does not reset the owner. | `auth.py` |
| `OPENINGS_TRUSTED_PROXIES` | empty: trust no proxy | Comma-separated IP addresses or CIDR ranges of reverse proxies whose `X-Forwarded-For` and `X-Forwarded-Proto` are trusted. Each client behind a trusted proxy gets its own sign-in limit. An invalid entry stops the start with an error. Option `--trusted-proxies`. | `__main__.py` |
| `OPENINGS_RETENTION_DAYS` | `90` | Days finished collection runs and tasks are kept; `0` keeps everything. The 20 most recent finished runs of every source always stay. A value that is not a number falls back to 90 with a warning. | `retention.py` |
| `OPENINGS_MAX_RESTORE_MB` | unset | An upper bound, in MiB, on the backup a restore accepts. The limit otherwise follows the free space on the data volume (see [Operations](operations.md)); this setting can only lower it. | `operations.py` |
| `OPENINGS_BACKUP_DIR` | `<data dir>/backups` (the folder of the workspace file; `/data/backups` in the image) | Where the daily backups are written. Created with mode 0700 when missing; keep it on a volume the container can write. | `backups.py` |
| `OPENINGS_BACKUP_KEEP` | `3` | How many daily backups are kept; older ones are deleted after a new one is verified. `0` turns daily backups off. A value that is not a number falls back to 3 with a warning. See [Backups](operations.md#backups). | `backups.py` |
| `OPENINGS_COMPACT_MIN_MB` | `32` | At start, the database file is rewritten without its free pages when at least a quarter of the file and this many MiB are free. A very large value disables it. | `compaction.py` |

## Process and paths

The container image sets these; change them only when running from source or
building your own image.

| Variable | Default from source | Image value | What it does | Read by |
|---|---|---|---|---|
| `OPENINGS_HOST` | `127.0.0.1` | `0.0.0.0` | Address the server listens on. Option `--host`. | `__main__.py` |
| `OPENINGS_PORT` | `8080` | `8080` | Port the server listens on (inside the container). Option `--port`. | `__main__.py` |
| `OPENINGS_DATABASE` | `data/openings.sqlite` | `/data/openings.sqlite` | The workspace file. Option `--database`. | `__main__.py`, `app.py` |
| `OPENINGS_FRONTEND` | `frontend/dist` of the checkout | `/app/frontend` | The built dashboard. Without it the server answers with a short JSON notice. | `app.py` |
| `OPENINGS_EXAMPLES` | `examples` of the checkout | `/app/examples` | Synthetic example files served at `/api/v1/examples`. | `interfaces/system.py` |
| `OPENINGS_SKILLS` | `skills` of the checkout | `/app/skills` | The shipped workflow skills. | `skills.py` |

## Docker Compose only

| Variable | Default | What it does |
|---|---|---|
| `OPENINGS_BIND` | `127.0.0.1` | Host address the container port is published on; `0.0.0.0` exposes it on the network. |
| `OPENINGS_PORT` | `8080` | Host port; the container still listens on 8080. Update `OPENINGS_PUBLIC_URL` to match. |
| `OPENINGS_IMAGE` | the released image | Image to run, for a private mirror or a local build. |

## Clients and tests

The server does not read these. The guides use `OPENINGS_URL` and
`OPENINGS_TOKEN` in REST examples and agent environments, and `OPENINGS_CA_FILE`
for a private certificate authority. The browser tests read `OPENINGS_E2E_PORT`,
`OPENINGS_E2E_TOKEN`, `OPENINGS_E2E_JOBS` and `OPENINGS_E2E_APPLICATIONS` (see
[Contributing](../../CONTRIBUTING.md)).
