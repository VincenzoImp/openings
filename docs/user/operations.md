# Operations

## Health

```bash
docker compose exec scheduler openings healthcheck
curl -s http://127.0.0.1:8501/health
```

The health check parses the configuration, opens the database and verifies
the data directories. `/health` also reports the embeddings state. The `runs`
table (Runs view, `GET /api/runs`, `list_runs`) answers "did the last
collection work": per-source task counts, rows and errors, and whether a run
is still open. `GET /api/sources` joins the last run to each configured
source.

## Logs

```bash
docker compose logs -f scheduler
docker compose logs -f web
```

The application log is `/data/logs/openings.log`, rotated by size according to
the `logging` section, with timestamps in `logging.timezone`.

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

The sentence model under `/data/models` is disposable: delete it and the next
process downloads it again. Embeddings live in the database and are rebuilt
for any job that lacks one when `embeddings.backfill_on_startup` is on.

One job's whole application (posting, notes, answers, timeline and files) can
also be taken out as a zip: `GET /api/jobs/{job_id}/bundle.zip` or the
"Download bundle" button.

## Retention

Retention only ever touches jobs in status `new`. `scoring.save_threshold`
removes low scores on every run and `retention.max_age_days` removes rows not
seen for that long. Every job you shortlisted, applied to, otherwise moved or
blacklisted is protected. `GET /api/cleanup/preview` (System view,
`preview_cleanup`) shows what a cleanup would do before it runs, and the
score and staleness deletions accept `dry_run`.

## Blacklist

Blacklisting is a status, not a deletion: the job keeps its notes, files and
timeline, leaves every list and export, and is never refreshed or re-created
by a run. Restore it from System › Blacklist, `POST /api/blacklist/remove` or
`unblacklist_jobs`; it goes back to the status it held before.

## Concurrency

The scheduler writes collected rows, the web process writes state changes,
and both embed what they write. SQLite in WAL mode with the application's
connection lock covers this single-user setup. Do not run two schedulers
against one data directory. The web process picks up edits to
`settings.yaml` without a restart.

## Recovery

Compose creates `settings.yaml` as a directory when the host file is missing
at first start:

```bash
rm -rf settings.yaml
cp config/settings.example.yaml settings.yaml
docker compose up -d
```

A configuration error stops the container at boot with the offending key in
the log. `openings healthcheck` reproduces it outside the scheduler. A run
left open by a crash is closed as failed when the next process starts.
