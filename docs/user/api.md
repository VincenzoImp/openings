# REST API

The REST API is a thin FastAPI adapter over the shared job service layer. It is
intended for local scripts and trusted automations.

## Start

Docker Compose:

```bash
docker compose --profile api up -d
```

Local Python:

```bash
uv run job-search-api
```

Default base URL:

```text
http://127.0.0.1:8502
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
API gateway. Keep the API bound to `127.0.0.1` unless you explicitly need LAN
access.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | status and job count |
| `GET` | `/jobs` | list jobs with filtering and pagination |
| `GET` | `/jobs/{job_id}` | fetch one job |
| `GET` | `/jobs/search/semantic` | semantic search over ChromaDB |
| `GET` | `/stats` | summary statistics |
| `GET` | `/distribution` | score distribution |
| `POST` | `/jobs/{job_id}/bookmark` | toggle bookmark |
| `POST` | `/jobs/{job_id}/apply` | toggle applied state |
| `DELETE` | `/jobs/{job_id}` | blacklist and remove one job |
| `DELETE` | `/jobs/below-score/{score}` | bulk delete below score |

OpenAPI metadata uses the project version from `pyproject.toml`.
