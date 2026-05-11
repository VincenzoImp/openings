# Docker Deployment

Docker Compose is the recommended way to run the tool locally or on a trusted
LAN. The image is `vincenzoimp/job-search-tool`.

## Services

| Service | Role | Default bind |
|---------|------|--------------|
| `scheduler` | continuous search loop | none |
| `web` | React dashboard, REST API, MCP endpoint | `127.0.0.1:8501` |

Both services share the Docker-managed `jobsearch-data` volume for the
database, vector store, exports, and logs. The editable configuration remains a
host file: `./settings.yaml`, mounted read-only at
`/data/config/settings.yaml`.

## Quick Start

```bash
cp config/settings.example.yaml settings.yaml
docker compose up -d
```

Open:

```text
http://127.0.0.1:8501
```

Show logs:

```bash
docker compose logs -f scheduler
docker compose logs -f web
```

Stop everything:

```bash
docker compose down
```

## LAN Binding

Published ports are localhost-only by default. This is intentional for a local
automation tool that can expose personal job data and mutate state.

To expose the web surface on a trusted LAN, create `.env`:

```dotenv
JOB_SEARCH_WEB_BIND=0.0.0.0
```

For API or dashboard access outside the same machine, set `JOB_SEARCH_API_TOKEN`.
Scripts can send `Authorization: Bearer <token>`. The dashboard will show a token
gate and then send `X-Job-Search-Token` on browser API requests.

For MCP access from another LAN device, also allow the host seen by the MCP
client:

```dotenv
JOB_SEARCH_WEB_ALLOWED_HOSTS=192.168.1.10:8501
JOB_SEARCH_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8501
```

`JOB_SEARCH_WEB_ALLOWED_ORIGINS` also controls browser CORS for API calls from a
separate origin. It is not required when the built dashboard and API are served
from the same web process.

Do not expose the web port directly to untrusted networks.

## Updates

```bash
docker compose pull
docker compose up -d
```

Since 9.0.0, the current SQLite schema is the runtime baseline and does
not migrate prior database layouts. For a clean major-version start, reset the
Docker-managed state volume before bringing services back up:

```bash
docker compose down -v
docker compose up -d
```

Release tags are published by GitHub Actions to Docker Hub when `v*` tags are
pushed.

## Commands

Runtime services use installed package entrypoints:

```text
job-search scheduler
job-search-web
job-search-healthcheck
```
