# Configuration

Set the few environment variables Openings reads at start here. How you set them
depends on how you run Openings:

- **Docker Compose:** put them in `.env` next to `docker-compose.yml`
  ([`.env.example`](../../.env.example) lists them), then recreate the container
  with `docker compose up -d`. A restart alone keeps the old values.
- **`docker run`:** pass each as `-e NAME=value` and create the container again.
- **From source:** export them before `uv run openings`, or use the matching
  command-line option where one exists.

Every other setting lives in the workspace, and you change it by hand, over REST
or over MCP: sources, the spacing of requests to job sites, Preferences, tokens
and the owner password.

## Server

| Variable | Default | What it does |
|---|---|---|
| `OPENINGS_PUBLIC_URL` | unset (Compose: `http://127.0.0.1:<OPENINGS_PORT>`) | The address browsers and agents use to reach Openings. Set it when other devices or agents connect. MCP accepts its host besides `localhost`, upload and download links start with it, and cookies are secure when it starts with `https://`. MCP refuses another host with a message that names this variable, and a dashboard opened at another address shows the value to set. With `docker run` and another host port, pass it too, for example `-p 127.0.0.1:18080:8080 -e OPENINGS_PUBLIC_URL=http://127.0.0.1:18080`. |
| `OPENINGS_PASSWORD` | unset | First-run owner password, at least 10 characters. Used only while no owner password exists. Without it, a new workspace prints a one-time setup code to the log at each start, and the first owner enters it. |
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
| `OPENINGS_PORT` | `8080` | Host port; the container listens on 8080. The default `OPENINGS_PUBLIC_URL` follows it. |
| `OPENINGS_IMAGE` | the released image | The image to run, for a mirror or a local build (`docker build -t openings:dev .`). |

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

Openings does not read these. Your scripts and your agent use `OPENINGS_URL` and
`OPENINGS_TOKEN`, as [REST API](api.md) and [Work with an agent](agents.md) show.
`OPENINGS_CA_FILE` names a private certificate authority for the launcher of the
[agent folder](../../examples/operator-workspace/README.md).
