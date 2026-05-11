# REST API

The REST API is mounted under the unified web server at `/api`. It is intended
for local scripts and trusted automations.

## Start

Docker Compose:

```bash
docker compose up -d
```

Local Python:

```bash
uv run job-search-web
```

Default base URL:

```text
http://127.0.0.1:8501/api
```

OpenAPI docs:

```text
http://127.0.0.1:8501/docs
```

## Authentication

Authentication is disabled unless `JOB_SEARCH_API_TOKEN` is set.

```dotenv
JOB_SEARCH_API_TOKEN=change-me
```

Then send:

```text
Authorization: Bearer change-me
```

This is a local/LAN protection mechanism, not a substitute for a hardened public
API gateway. Keep the web server bound to `127.0.0.1` unless you explicitly need
LAN access.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | status and job count |
| `GET` | `/api/jobs` | list jobs with filtering and pagination |
| `GET` | `/api/jobs/{job_id}` | fetch one job |
| `GET` | `/api/jobs/search/semantic` | semantic search over ChromaDB |
| `GET` | `/api/stats` | summary statistics |
| `GET` | `/api/distribution` | score distribution |
| `PUT` | `/api/jobs/{job_id}/bookmark` | set bookmark state |
| `PUT` | `/api/jobs/{job_id}/applied` | set applied state |
| `POST` | `/api/jobs/blacklist` | blacklist and remove jobs |
| `GET` | `/api/cleanup/preview` | preview configured cleanup |
| `POST` | `/api/cleanup/run` | run configured cleanup |

OpenAPI metadata uses the project version from `pyproject.toml`.
