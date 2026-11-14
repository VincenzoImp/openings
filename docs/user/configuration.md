# Configuration

Openings reads a few environment variables at start. With Docker Compose, set them
in `.env` next to `docker-compose.yml` (see [`.env.example`](../../.env.example))
and recreate the container with `docker compose up -d`; a restart alone keeps the
old values. From source, export them before `uv run openings`, or use the matching
command-line option where one exists.

Every other setting lives in the workspace and is changed in the dashboard, REST or
MCP: sources, provider request spacing, Preferences, tokens and the owner password.

## Server

| Variable | Default | What it does |
|---|---|---|
| `OPENINGS_PUBLIC_URL` | unset (Compose: `http://127.0.0.1:8080`) | The origin browsers and agents use. MCP accepts this host besides `localhost`; file-transfer grants and their `curl` lines start with it; cookies are secure when it starts with `https://`. |
| `OPENINGS_PASSWORD` | unset | First-run owner password, at least 10 characters. Used only while no owner password exists. |
| `OPENINGS_TRUSTED_PROXIES` | empty: trust none | Comma-separated IPs or CIDR ranges of reverse proxies whose `X-Forwarded-For` and `X-Forwarded-Proto` are trusted. An invalid entry stops the start. Option `--trusted-proxies`. |
| `OPENINGS_RETENTION_DAYS` | `90` | Days finished collection runs and tasks are kept; `0` keeps all. The 20 newest runs of every source always stay. |
| `OPENINGS_BACKUP_DIR` | `<data dir>/backups` (`/data/backups`) | Where daily backups go. Created with mode 0700. |
| `OPENINGS_BACKUP_KEEP` | `3` | Daily backups kept; `0` turns them off. |
| `OPENINGS_MAX_RESTORE_MB` | unset | An upper bound on the backup a restore accepts. The limit otherwise follows free space; this can only lower it. |
| `OPENINGS_COMPACT_MIN_MB` | `32` | At start, the database is rewritten without free pages when at least a quarter of it and this many MiB are free. A very large value disables it. |

A retention or backup count that is not a number falls back to its default with a warning.

## Docker Compose only

| Variable | Default | What it does |
|---|---|---|
| `OPENINGS_BIND` | `127.0.0.1` | Host address the port is published on; `0.0.0.0` exposes it to the network. |
| `OPENINGS_PORT` | `8080` | Host port; the container listens on 8080. Update `OPENINGS_PUBLIC_URL` to match. |
| `OPENINGS_IMAGE` | the released image | The image to run, for a mirror or a local build. |

## Process and paths

The image sets these; change them only when running from source or building your
own image.

| Variable | From source | In the image | What it does |
|---|---|---|---|
| `OPENINGS_HOST` | `127.0.0.1` | `0.0.0.0` | Listen address. Option `--host`. |
| `OPENINGS_PORT` | `8080` | `8080` | Listen port inside the container. Option `--port`. |
| `OPENINGS_DATABASE` | `data/openings.sqlite` | `/data/openings.sqlite` | The workspace file. Option `--database`. |
| `OPENINGS_FRONTEND` | `frontend/dist` | `/app/frontend` | The built dashboard. |
| `OPENINGS_EXAMPLES` | `examples` | `/app/examples` | Synthetic example files served at `/api/v1/examples`. |
| `OPENINGS_SKILLS` | `skills` | `/app/skills` | The skills served to agents. |

## Clients

The server does not read these. Your scripts and agent use `OPENINGS_URL` and
`OPENINGS_TOKEN` (see [REST API](api.md) and [Work with an agent](agents.md)), and
`OPENINGS_CA_FILE` names a private certificate authority for the operator workspace
launcher. The browser tests' server reads `OPENINGS_E2E_PORT`, `OPENINGS_E2E_JOBS`
and `OPENINGS_E2E_APPLICATIONS`.
