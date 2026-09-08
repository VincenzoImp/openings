# Operations

## Health

```bash
docker compose exec scheduler openings healthcheck
curl -s http://127.0.0.1:8501/health
```

The health check parses the configuration, opens the database and verifies
the data directories. The `runs` table (Runs view, `GET /api/runs`,
`list_runs`) answers "did the last collection work": per-source task counts,
rows and errors.

## Logs

```bash
docker compose logs -f scheduler
docker compose logs -f web
```

The application log is `/data/logs/openings.log`, rotated by size according to
the `logging` section.

## Backups

State is `settings.yaml` on the host plus the `openings-data` volume. The
database and the attachments directory belong together: attachment rows point
at files under `/data/attachments/<job_id>/`.

```bash
docker compose exec scheduler python -c \
  "import sqlite3; sqlite3.connect('/data/db/openings.db').backup(sqlite3.connect('/data/db/openings.backup.db'))"
docker run --rm -v openings-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/openings-data.tgz -C /data db attachments
```

The vector index under `/data/chroma` is disposable: delete it and the
scheduler rebuilds it on the next start when `vector_search.backfill_on_startup`
is on.

## Retention

Retention only ever touches jobs in status `new`. `scoring.save_threshold`
removes low scores on every run, `retention.max_age_days` removes rows not
seen for that long, `retention.purge_blacklist_after_days` trims the
blacklist. Every job you shortlisted, applied to or otherwise moved is
protected. `GET /api/cleanup/preview` (System view, `preview_cleanup`) shows
what a cleanup would do before it runs.

## Concurrency

The scheduler writes collected rows and the vector index. The web process
writes state changes (status, labels, notes, attachments, blacklist) but never
the vector index. SQLite in WAL mode with the application's connection lock
covers this single-user setup. Do not run two schedulers against one data
directory.

## Recovery

Compose creates `settings.yaml` as a directory when the host file is missing
at first start:

```bash
rm -rf settings.yaml
cp config/settings.example.yaml settings.yaml
docker compose up -d
```

A configuration error stops the container at boot with the offending key in
the log. `openings healthcheck` reproduces it outside the scheduler.
