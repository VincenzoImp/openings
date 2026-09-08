# Architecture

## Modules

```text
openings/
  config.py          settings.yaml -> typed dataclasses; strict keys; $ENV secrets
  models.py          Job, JobStatus, Note, Attachment, Event, BlacklistEntry, RunSummary
  database.py        SQLite schema and every query; JobQuery, retention, runs
  scoring.py         keyword scoring, explain_score, thresholds, post filter
  sources/           one module per source, all returning the canonical frame
    base.py          CANONICAL_COLUMNS, HTTP helpers, html_to_markdown, to_date
    jobspy.py        boards through JobSpy: throttling, retry, thread pool
    ats/             greenhouse, lever, ashby, smartrecruiters public feeds
    rss.py           RSS and Atom through feedparser
    adzuna.py        Adzuna search API (keyed, optional)
    manual.py        add_job records
    collect.py       collect_all: run every source, isolate failures, dedupe
  pipeline.py        collect -> score -> partition -> upsert -> embed -> notify -> runs row
  scheduler.py       APScheduler loop with start-to-start intervals and retry
  notifier.py        Telegram digest
  vector_store.py    Chroma index; vector_commands.py keeps it in sync
  application/       JobApplicationService, AttachmentStore, command/result types
  web/               FastAPI app: api.py routes, mcp.py tools, static dashboard
  cli.py             openings {run, scheduler, web, healthcheck}
```

## Data flow

1. `collect_all` runs the configured sources. Each source returns a
   `SourceResult` with a DataFrame in the canonical shape plus per-task stats;
   a failing task or company never aborts the run.
2. `score_jobs` adds `relevance_score`; `partition_by_thresholds` splits rows
   into save and notify sets.
3. `JobDatabase.upsert_jobs` skips blacklisted identities, inserts new rows
   with status `new` and an `ingested` event, and refreshes posting fields and
   `last_seen` on existing rows. **It never touches `status`.**
4. New rows above the notify threshold go to Telegram; the run is recorded in
   `runs`.

## Schema

| Table | Holds |
|-------|-------|
| `jobs` | the posting fields, `raw_json`, `first_seen`, `last_seen`, `relevance_score`, `status`, `status_changed_at` |
| `job_labels` | `(job_id, label)` |
| `notes` | `kind` (`note`, `qa`), `title`, `body` |
| `attachments` | `kind`, `filename`, `stored_name`, `sha256`, `size_bytes`, `note`; files under `attachments/<job_id>/` |
| `events` | append-only timeline: `ingested`, `status`, `label`, `note`, `attachment` |
| `blacklist` | suppressed identities with title, company, location |
| `runs` | one row per collection with the per-source JSON |

Foreign keys cascade from `jobs`; deleting a job removes its labels, notes,
attachment rows and events, and the service removes its files.

## Invariants

- Identity is `generate_job_id(title, company, location)` everywhere: sources,
  the database, `add_job`, the blacklist.
- Retention SQL is restricted to `status = 'new'`; the protected set is
  `PROTECTED_STATUSES` and is enforced in `database.py`, not in callers.
- Blacklisting deletes the row and inserts the identity; `upsert_jobs` and
  `add_job` consult the blacklist first.
- The web process never writes the vector index. The scheduler runs
  `sync_deletions` and `backfill_embeddings` on its own interval.
- Every surface calls `JobApplicationService`. Routes and tools only parse
  input and serialize output.
- Configuration is parsed once per run (`reload_config` at the start of a
  collection) and is never consulted to decide a job's status.

## Frontend

`frontend/src`:

```text
api/        client.ts (fetch, token, query building), types.ts
app/        App, Shell, router (?view=&job=), hotkeys, toast, dialogs
components/ Button, Badge, Dialog, Field, FileDrop, Kbd, MarkdownBody, ScoreBar
features/   inbox, pipeline, companies, runs, system, job, shared (queries, JobList, format)
```

State lives in TanStack Query; every write invalidates the lists it can
change. The built `dist/` is copied into the image at `/opt/openings/frontend`
and served by `openings web`; `OPENINGS_FRONTEND_DIST` overrides the path.
