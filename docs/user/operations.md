# Operations

## Health

Run the container health check directly:

```bash
docker compose exec scheduler job-search-healthcheck
```

Check API health when the API profile is enabled:

```bash
curl http://127.0.0.1:8502/health
```

## Logs

Container logs:

```bash
docker compose logs -f scheduler
docker compose logs -f dashboard
docker compose logs -f api
docker compose logs -f mcp
```

Application logs are written to `/data/logs/search.log` inside the shared data
volume.

## Backups

The important state is the host `settings.yaml` plus the Docker volume
`jobsearch-data`.

Example SQLite backup:

```bash
docker compose exec scheduler python -c "import sqlite3; sqlite3.connect('/data/db/jobs.db').backup(sqlite3.connect('/data/db/jobs.backup.db'))"
```

For full-state backups, snapshot the Docker volume using your normal host backup
tooling.

## Concurrency

The scheduler writes to SQLite. Dashboard, API, and MCP read from the same
database and can mutate curation state. SQLite WAL mode and the application
connection lock cover normal single-user local usage.

Do not run multiple independent scheduler/search instances against the same data
directory at the same time.

## Recovery

If Compose accidentally created `settings.yaml` as a directory because the file
was missing on first start:

```bash
rm -rf settings.yaml
cp config/settings.example.yaml settings.yaml
docker compose up -d
```
