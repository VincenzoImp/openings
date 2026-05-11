# Configuration

Runtime behavior is controlled by `settings.yaml`. The canonical reference is
`config/settings.example.yaml`; the MCP settings documentation is generated
from that same template.

## Required File

For Docker Compose, keep `settings.yaml` next to `docker-compose.yml`:

```bash
cp config/settings.example.yaml settings.yaml
```

The container reads it at `/data/config/settings.yaml`. It is mounted read-only,
so edit the host-side file and restart the relevant services.

## Main Sections

| Section | Purpose |
|---------|---------|
| `search` | sites, locations, result limits, remote/date filters |
| `queries` | job titles and terms submitted to each site/location |
| `scoring` | keyword weights, save threshold, notify threshold |
| `parallel` | concurrent query workers |
| `retry` | retry attempts and exponential backoff |
| `throttling` | per-site delays and rate-limit cooldown |
| `post_filter` | fuzzy validation after scraping |
| `database.retention` | stale job and blacklist cleanup |
| `notifications.telegram` | Telegram delivery settings |
| `vector_search` | ChromaDB semantic search settings |

Current template defaults include `search.hours_old: 720`,
`parallel.max_workers: 3`, `throttling.rate_limit_cooldown: 60.0`, and
`notifications.telegram.max_jobs_in_message: 20`.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `JOB_SEARCH_DATA_DIR` | root for database, ChromaDB, results, logs |
| `JOB_SEARCH_TEMPLATE_PATH` | template path used for generated settings docs |
| `JOB_SEARCH_WEB_BIND` | web bind host in Compose |
| `JOB_SEARCH_WEB_PORT` | web host port |
| `JOB_SEARCH_API_TOKEN` | optional token for API routes under `/api` and the dashboard token gate |
| `JOB_SEARCH_WEB_ALLOWED_HOSTS` | comma-separated MCP allowed hosts for LAN use |
| `JOB_SEARCH_WEB_ALLOWED_ORIGINS` | comma-separated MCP/CORS allowed origins for LAN use |

## Thresholds

`scoring.save_threshold` decides what is stored. `scoring.notify_threshold`
decides what is sent to notifications. The loader rejects configurations where
`notify_threshold < save_threshold`.

Unsupported configuration keys are rejected at startup. This keeps stale
settings visible instead of silently accepting options that no longer affect the
runtime.

## Storage Layout

Inside Docker, persistent state lives under `/data`:

```text
/data/config/settings.yaml
/data/db/jobs.db
/data/chroma/
/data/results/
/data/logs/search.log
```

Only `settings.yaml` should be edited manually.
