# Docker deployment

Docker Compose is the intended way to run Openings. The image is
`vincenzoimp/openings`; one image, two roles.

## Services

| Service | Command | Bind |
|---------|---------|------|
| `scheduler` | `openings scheduler` | none |
| `web` | `openings web` | `127.0.0.1:8501` |

Both share the named volume `openings-data` mounted at `/data`:

```text
/data/config/settings.yaml   bind-mounted from ./settings.yaml, read-only
/data/db/openings.db         the database
/data/attachments/<job_id>/  uploaded files
/data/chroma/                the vector index (optional)
/data/logs/openings.log      application log
```

## Start

```bash
cp config/settings.example.yaml settings.yaml
docker compose up -d
docker compose logs -f scheduler
```

The container refuses to start without `settings.yaml`; there is no default
configuration. Edit the file and `docker compose restart` to apply changes.

## Environment

Set these in `.env` next to the Compose file (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `OPENINGS_WEB_BIND` | host interface for the web port, default `127.0.0.1` |
| `OPENINGS_WEB_PORT` | host port, default `8501` |
| `OPENINGS_API_TOKEN` | protect `/api`, the dashboard and `/mcp` |
| `OPENINGS_WEB_ALLOWED_HOSTS`, `OPENINGS_WEB_ALLOWED_ORIGINS` | extra hosts and origins for MCP DNS-rebinding protection and CORS |
| `TELEGRAM_BOT_TOKEN`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | secrets referenced as `$NAME` in `settings.yaml` |

Inside the container `OPENINGS_DATA_DIR=/data` and
`OPENINGS_CONFIG=/data/config/settings.yaml`.

## LAN access

Ports are localhost-only by default because the data is personal and every
surface can change it. On a trusted network:

```dotenv
OPENINGS_WEB_BIND=0.0.0.0
OPENINGS_API_TOKEN=<long random string>
OPENINGS_WEB_ALLOWED_HOSTS=192.168.1.10:8501
OPENINGS_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8501
```

Do not expose the port to untrusted networks.

## Update

```bash
docker compose pull
docker compose up -d
```

The database schema is created by the running version; back up the volume
before upgrading across major versions.

## Build locally

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

`docker/smoke.sh` builds the image and exercises the dashboard, REST and MCP
end to end.
