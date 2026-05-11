# Job Search Tool

[![CI](https://github.com/VincenzoImp/job-search-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/VincenzoImp/job-search-tool/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

Local-first job search automation: collect jobs from multiple boards, score
them against your own criteria, store them in SQLite, review them in a React
dashboard, query them through REST, and expose the same data to MCP clients.

## Features

- Multi-board ingestion through JobSpy.
- Configurable keyword scoring with separate save and notification thresholds.
- SQLite persistence with bookmarks, applied state, blacklist, and retention.
- React dashboard for review, filtering, analytics, cleanup, and CSV export.
- Local semantic search through ChromaDB's bundled ONNX embedder.
- Telegram notifications for high-scoring new jobs.
- Unified ASGI web server for dashboard, REST API, and MCP.
- Docker Compose deployment with localhost-first network defaults.

## Docker Quick Start

1. Create your runtime configuration:

   ```bash
   cp config/settings.example.yaml settings.yaml
   ```

2. Edit `settings.yaml`, especially `locations`, `queries`, `scoring`, and
   optional Telegram settings.

3. Start the scheduler and web server:

   ```bash
   docker compose up -d
   ```

4. Open the dashboard:

   ```text
   http://127.0.0.1:8501
   ```

The same web process exposes REST at `http://127.0.0.1:8501/api` and MCP at
`http://127.0.0.1:8501/mcp`. Published ports bind to `127.0.0.1` by default.
For trusted LAN use, set `JOB_SEARCH_WEB_BIND=0.0.0.0` in `.env` and keep
firewall rules tight.

## Interfaces

| Surface | Command | Default URL | Notes |
|---------|---------|-------------|-------|
| Scheduler | `job-search scheduler` | none | continuous search loop |
| Web dashboard | `job-search-web` | `http://127.0.0.1:8501` | human review UI |
| REST API | `job-search-web` | `http://127.0.0.1:8501/api` | optional `JOB_SEARCH_API_TOKEN` |
| MCP | `job-search-web` | `http://127.0.0.1:8501/mcp` | streamable HTTP |

## Documentation

- [Docker deployment](docs/user/docker.md)
- [Configuration](docs/user/configuration.md)
- [REST API](docs/user/api.md)
- [MCP server](docs/user/mcp.md)
- [Operations](docs/user/operations.md)
- [Architecture](docs/developer/architecture.md)
- [Testing](docs/developer/testing.md)
- [Release process](docs/developer/release.md)

## Local Development

```bash
uv sync
npm --prefix frontend install
cp config/settings.example.yaml config/settings.yaml
uv run pytest
npm --prefix frontend run test
uv run pre-commit run --all-files
```

Local commands run through installed package entrypoints:

```bash
uv run job-search once
uv run job-search scheduler
uv run job-search-web
```

## Releases

Docker images are published to Docker Hub by the release workflow when a `v*`
tag is pushed. Release tags produce semver tags, `latest`, SBOM, and provenance
metadata for `vincenzoimp/job-search-tool`.

## License

MIT. See [LICENSE](LICENSE).
