# Configuration

One file, `settings.yaml`, configures intake and scoring. It never describes
the state of a job: statuses, labels, notes and attachments live in the
database and change through the dashboard, the API or MCP.

[`config/settings.example.yaml`](../../config/settings.example.yaml) is the
annotated reference; every value in it is the default. The same text is
available at runtime through `GET /api/settings/reference` and the MCP tool
`get_settings_reference`; `GET /api/settings` and `get_settings` summarize
the live values.

Rules:

- Unknown keys fail startup. A typo is an error, not a silent no-op.
- Any secret can be written as `"$NAME"` and is read from the environment
  variable `NAME` at startup.
- `notify_threshold` must be at least `save_threshold`; every category in
  `scoring.keywords` needs a weight.
- The file is read at the start of every collection, and the web process
  reloads it when its modification time changes, so edits apply without a
  restart.

## Sections

### `profile`

Informational: `name`, `headline`, `target`. Shown in the log banner and in
System.

### `sources`

`user_agent` and `timeout_seconds` apply to every direct HTTP request.
`feed_max_age_days` (default 60, `null` to disable) drops company-feed and
RSS postings whose date is older than that; evergreen postings on Greenhouse
or Lever boards otherwise return forever.

#### `sources.jobspy`

Job boards through JobSpy. `sites` (`linkedin`, `indeed`, `glassdoor`,
`google`, `zip_recruiter`, `bayt`, `naukri`, `bdjobs`), `locations` as the
board understands them, `queries` grouped by category (the grouping is yours;
every term is searched), `job_types`, `hours_old`, `results_wanted`,
`distance`, `is_remote`, `easy_apply`, `country_indeed`, LinkedIn options,
proxies. Requests per run are `queries x locations x job_types`; the
`throttling`, `retry` and `parallel` blocks pace them. `post_filter` drops
"related" results whose text does not contain the query terms.

#### `sources.companies`

Employers whose applicant tracking system publishes a feed:

```yaml
companies:
  - name: "Example Corp"
    ats: "greenhouse"          # greenhouse | lever | ashby | smartrecruiters
    slug: "examplecorp"
    locations: ["Berlin", "Remote"]   # optional substrings; omit to keep all
    titles: ["engineer", "developer"] # optional substrings on the title
    max_age_days: 90                  # optional; overrides feed_max_age_days
```

See [Sources](sources.md) for how to find the slug.

#### `sources.feeds`

RSS or Atom feeds: `name`, `url`, optional `locations`, `titles` and
`max_age_days`.

#### `sources.adzuna`

The Adzuna API, off by default: `enabled`, `country` (Adzuna code: `gb`, `us`,
`de`, ...), `queries`, `locations`, `app_id`, `app_key`, `results_per_page`,
`max_pages`, `max_days_old`.

### `scoring`

```yaml
scoring:
  save_threshold: 0        # store a posting only at or above this score
  notify_threshold: 20     # notify only at or above this score
  weights:
    role: 25
    stack: 15
    language_required: -60
  keywords:
    role: ["backend engineer", "platform engineer"]
    stack: ["python", "go", "postgresql"]
    language_required: ["fluent in german", "deutsch erforderlich"]
```

For each category, if any term appears in the posting text (title,
description, company, location; case-insensitive; accents ignored), the
category's weight is added once. Negative weights express hard limits. The
job page and `get_job` show which categories matched, so weights are easy to
tune: watch `GET /api/distribution` after a run and move the thresholds.

### `scheduler`

`interval_hours` (start to start), `run_on_startup`, `retry_on_failure`,
`retry_delay_minutes`, `max_retries`. A run whose every task failed counts as
failed and is retried. `openings run` ignores this section. "Run now" (the
Runs view, `POST /api/runs`, `run_now`) is picked up within 30 seconds.

### `notifications`

`telegram`: `enabled`, `bot_token` (`"$TELEGRAM_BOT_TOKEN"`), `chat_ids`,
`send_summary`, `send_empty`, `max_jobs`, `jobs_per_chunk`. A digest goes out
after each run with the postings that are new in that run and at or above
`notify_threshold`; nothing already seen is repeated, and nothing is sent
when nothing is new unless `send_empty` is on.

### `retention`

`max_age_days` removes jobs in status `new` not seen for that long, at every
start and through `run_cleanup`. Jobs in any other status, blacklisted ones
included, are never touched.

### `attachments`

`max_size_mb` per uploaded file.

### `embeddings`

Local semantic search: `enabled`, `embed_on_save`, `backfill_on_startup`,
`batch_size`. The sentence model (all-MiniLM-L6-v2 as ONNX, about 90 MB) is
downloaded once into `models/` under the data directory; vectors are stored
in the database. Both the scheduler and the web process embed the jobs they
write.

### `logging`

`level`, `max_size_mb`, `backup_count`, `timezone` (IANA name). Timestamps
are stored in UTC and rendered in this zone in logs and digests.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENINGS_DATA_DIR` | `./data` (`/data` in Docker) | root of the data tree |
| `OPENINGS_CONFIG` | `$OPENINGS_DATA_DIR/config/settings.yaml` | the settings file |
| `OPENINGS_API_TOKEN` | unset | token for `/api`, the dashboard and `/mcp` |
| `OPENINGS_WEB_LISTEN_PORT` | `8501` | port inside the process |
| `OPENINGS_WEB_ALLOWED_HOSTS`, `OPENINGS_WEB_ALLOWED_ORIGINS` | localhost | MCP DNS-rebinding and CORS allow-lists |
| `OPENINGS_FRONTEND_DIST` | packaged | directory of the built dashboard |
| `OPENINGS_TEMPLATE_PATH` | packaged | the example file served as the settings reference |

## Storage layout

Relative to `OPENINGS_DATA_DIR`:

```text
config/settings.yaml
db/openings.db
attachments/<job_id>/<file>
models/
logs/openings.log
run-now                      # created by "Run now", consumed by the scheduler
```
