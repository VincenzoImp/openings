# Docker Deployment

Docker Compose is the recommended way to run the tool locally or on a trusted
LAN. The image is `vincenzoimp/job-search-tool`.

## Services

| Service | Role | Default bind | Profile |
|---------|------|--------------|---------|
| `scheduler` | continuous search loop | none | always on |
| `dashboard` | Streamlit dashboard | `127.0.0.1:8501` | always on |
| `api` | REST API | `127.0.0.1:8502` | `api` |
| `mcp` | MCP server | `127.0.0.1:3001` | `mcp` |

All services share the Docker-managed `jobsearch-data` volume for database,
vector store, exports, and logs. The editable configuration remains a host file:
`./settings.yaml`, mounted read-only at `/data/config/settings.yaml`.

## Quick Start

```bash
cp config/settings.example.yaml settings.yaml
docker compose up -d
```

Start API and MCP as well:

```bash
docker compose --profile api --profile mcp up -d
```

Show logs:

```bash
docker compose logs -f scheduler
```

Stop everything:

```bash
docker compose --profile api --profile mcp down
```

## LAN Binding

Published ports are localhost-only by default. This is intentional for a local
automation tool that can expose personal job data and mutate state.

To expose a surface on a trusted LAN, create `.env`:

```dotenv
JOB_SEARCH_DASHBOARD_BIND=0.0.0.0
JOB_SEARCH_API_BIND=0.0.0.0
JOB_SEARCH_MCP_BIND=0.0.0.0
```

Set only the services you need. Keep firewall rules tight and avoid public
internet exposure. For API access outside the same machine, set
`JOB_SEARCH_API_TOKEN` and send `Authorization: Bearer <token>`.

## Updates

```bash
docker compose pull
docker compose --profile api --profile mcp up -d
```

Version 8.0.0 treats the current SQLite schema as the runtime baseline and does
not migrate prior database layouts. For a clean major-version start, reset the
Docker-managed state volume before bringing services back up:

```bash
docker compose --profile api --profile mcp down -v
docker compose --profile api --profile mcp up -d
```

Release tags are published by GitHub Actions to Docker Hub when `v*` tags are
pushed.

## Commands

Runtime services use installed package entrypoints:

```text
job-search scheduler
job-search dashboard
job-search-api
job-search-mcp
job-search-healthcheck
```
