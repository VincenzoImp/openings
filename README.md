# Job Search Tool

[![CI](https://github.com/VincenzoImp/job-search-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/VincenzoImp/job-search-tool/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

Local-first job search automation: collect jobs from multiple boards, score
them against your own criteria, store them in SQLite, review them in a
dashboard, query them through REST, or expose them to MCP clients.

## Features

- Multi-board ingestion through JobSpy.
- Configurable keyword scoring with separate save and notification thresholds.
- SQLite persistence with bookmarks, applied state, blacklist, and retention.
- Streamlit dashboard for review, filtering, cleanup, and CSV/Excel export.
- Local semantic search through ChromaDB's bundled ONNX embedder.
- Telegram notifications for high-scoring new jobs.
- REST API and MCP server over the same local data layer.
- Docker Compose deployment with localhost-first network defaults.

## Docker Quick Start

1. Create your runtime configuration:

   ```bash
   cp config/settings.example.yaml settings.yaml
   ```

2. Edit `settings.yaml`, especially `locations`, `queries`, `scoring`, and
   optional Telegram settings.

3. Start the scheduler and dashboard:

   ```bash
   docker compose up -d
   ```

4. Open the dashboard:

   ```text
   http://127.0.0.1:8501
   ```

API and MCP are opt-in Compose profiles:

```bash
docker compose --profile api --profile mcp up -d
```

By default, dashboard, API, and MCP bind to `127.0.0.1`. To expose a service on
a trusted LAN, set the relevant bind variable in `.env`, for example
`JOB_SEARCH_MCP_BIND=0.0.0.0`. Do not expose these services directly to the
public internet.

## Interfaces

| Surface | Command | Default URL | Notes |
|---------|---------|-------------|-------|
| Scheduler | `job-search scheduler` | none | continuous search loop |
| Dashboard | `job-search dashboard` | `http://127.0.0.1:8501` | human review UI |
| REST API | `job-search-api` | `http://127.0.0.1:8502` | optional `JOB_SEARCH_API_TOKEN` |
| MCP | `job-search-mcp` | `http://127.0.0.1:3001/mcp` | streamable HTTP |

## Documentation

- [Docker deployment](docs/user/docker.md)
- [Configuration](docs/user/configuration.md)
- [REST API](docs/user/api.md)
- [MCP server](docs/user/mcp.md)
- [Operations](docs/user/operations.md)
- [Architecture](docs/developer/architecture.md)
- [Testing](docs/developer/testing.md)
- [Release process](docs/developer/release.md)
- [Current system audit](docs/developer/current-system/)

## Local Development

```bash
uv sync
cp config/settings.example.yaml config/settings.yaml
uv run pytest
uv run pre-commit run --all-files
```

Local commands run through installed package entrypoints:

```bash
uv run job-search once
uv run job-search dashboard
uv run job-search-api
uv run job-search-mcp
```

## Releases

Docker images are published to Docker Hub by the release workflow when a `v*`
tag is pushed. Release tags produce semver tags, `latest`, SBOM, and provenance
metadata for `vincenzoimp/job-search-tool`.

## License

MIT. See [LICENSE](LICENSE).
