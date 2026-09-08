# Architecture

## Modules

```text
openings/
  config.py          settings.yaml -> typed dataclasses; strict keys; $ENV secrets
  models.py          Job, JobStatus, Posting, Note, Attachment, Event, RunSummary;
                     posting keys, identities, aware timestamps
  text.py            text normalisation shared by scoring and sources
  scoring.py         keyword scoring, explain_score, thresholds, post filter
  db/                SQLite behind the JobDatabase facade
    base.py          connection, WAL, row mapping, events
    schema.py        tables and indexes
    jobs.py          upsert, queries, status, merge, statistics, facets
    postings.py      the postings of a job, lookups by posting key
    material.py      labels, notes, attachments
    events.py        timeline
    embeddings.py    vectors as float32 blobs
    runs.py          open, finish and list runs
    retention.py     cleanup restricted to status new
  embeddings.py      ONNX sentence model, embed on save, backfill, cosine search
  runtime.py         one object per process: config (reloaded on change), db,
                     attachments, embeddings, service
  sources/           one module per source, all returning the canonical frame
    base.py          CANONICAL_COLUMNS, HTTP helpers, html_to_markdown, to_date
    jobspy.py        boards through JobSpy: throttling, retry, thread pool
    ats/             greenhouse, lever, ashby, smartrecruiters public feeds
    rss.py           RSS and Atom through feedparser
    adzuna.py        Adzuna search API (keyed, optional)
    manual.py        add_job records
    collect.py       collect_all: run every source, isolate failures, dedupe
  pipeline.py        collect -> score -> partition -> upsert -> embed -> notify
  scheduler.py       APScheduler loop, start-to-start intervals, retry, run-now
  notifier.py        Telegram digest
  application/       JobApplicationService, AttachmentStore, bundle, command types
  web/               FastAPI app: api.py routes, mcp.py tools, token gate, dashboard
  cli.py             openings {run, scheduler, web, healthcheck}
```

## Data flow

1. `collect_all` runs the configured sources. Each source returns a
   `SourceResult` with a DataFrame in the canonical shape plus per-task stats;
   a failing task or company never aborts the run.
2. `score_jobs` adds `relevance_score`; `partition_by_thresholds` splits rows
   into save and notify sets.
3. `JobDatabase.upsert_jobs` matches each row to a job: by posting key
   (canonical URL or `source:external_id`), else by identity
   (`sha256(title | company | location)`) against jobs seen on other sources,
   else it inserts a new job with status `new` and an `ingested` event.
   Known jobs get their posting fields and `last_seen` refreshed; a new
   posting of a known job is recorded with a `posting` event. Blacklisted
   jobs are skipped. **It never touches `status`.**
4. New and refreshed jobs are embedded; new rows above the notify threshold
   go to Telegram; the run row opened at the start is closed with its
   statistics.

## Schema

| Table | Holds |
|-------|-------|
| `jobs` | posting fields, `raw_json`, `identity`, `first_seen`, `last_seen`, `relevance_score`, `status`, `status_changed_at` |
| `postings` | `(job_id, key, source, external_id, url, first_seen, last_seen)`; `key` is unique |
| `job_labels` | `(job_id, label)` |
| `notes` | `kind` (`note`, `qa`), `title`, `body`, `updated_at` |
| `attachments` | `kind`, `filename`, `stored_name`, `sha256`, `size_bytes`, `note`; files under `attachments/<job_id>/` |
| `events` | append-only timeline: `ingested`, `posting`, `status`, `label`, `note`, `attachment`, `updated`, `merged` |
| `embeddings` | `(job_id, model, vector, updated_at)` |
| `runs` | one row per collection with the per-source JSON; `finished_at` is null while open |

Foreign keys cascade from `jobs`; deleting a job removes its postings,
labels, notes, attachment rows, events and embedding, and the service removes
its files. Every timestamp is stored in UTC with an offset.

## Invariants

- A job id is `sha256(posting key)` when the first posting has one, else the
  identity. `Job.from_row` applies the rule for every producer.
- Retention SQL is restricted to `status = 'new'`; the protected set is
  `PROTECTED_STATUSES` and is enforced in `db/`, not in callers.
- Blacklisting is `set_status(blacklisted)`; `upsert_jobs` skips blacklisted
  jobs in one statement, `add_job` refuses them, every list excludes them
  unless asked, and `unblacklist_jobs` restores the status recorded in the
  last status event.
- Every surface calls `JobApplicationService`. Routes and tools only parse
  input and serialize output. `/api` and `/mcp` share one token check.
- Configuration is read through `Runtime.config()`, which reloads the file
  when its modification time changes, and is never consulted to decide a
  job's status.
- Both processes may write the database and the embeddings; SQLite WAL and
  the connection lock serialize them.

## Frontend

`frontend/src`:

```text
api/        client.ts (fetch, token, query building, downloads), types.ts
app/        App, Shell, router (?view=&job=&...), HotkeyProvider + hotkeys registry,
            theme, toast, confirm, ErrorBoundary, HelpDialog, TokenDialog
components/ Button, Badge, Card, Table, Stat, Menu, Dialog, Field, FileDrop,
            Kbd, MarkdownBody, ScoreBar, EmptyState
features/   inbox, pipeline, companies, runs, system, job,
            shared (queries, actions, JobList, LabelsEditor, dialogs, format, labels)
styles.css  design tokens (@theme over CSS variables), dark variant, markdown
```

Colours, radii and shadows are tokens; `[data-theme=dark]` overrides them and
an inline script applies the stored preference before paint. State lives in
TanStack Query; writes patch the cached lists optimistically and invalidate
only what they can change. One hotkey registry with scopes (dialog > view >
global) also generates the Help dialog. The built `dist/` is copied into the
image at `/opt/openings/frontend` and served by `openings web`;
`OPENINGS_FRONTEND_DIST` overrides the path.
