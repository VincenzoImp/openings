# Configuration

One file, `settings.yaml`, configures intake and scoring. It never describes
the state of a job: statuses, labels, notes and attachments live in the
database and change through the dashboard, the API or MCP.

[`config/settings.example.yaml`](../../config/settings.example.yaml) is the
annotated reference; every value in it is the default. The same text is
available at runtime through the MCP tool `get_settings_reference`.

Rules:

- Unknown keys fail startup. A typo is an error, not a silent no-op.
- Any secret can be written as `"$NAME"` and is read from the environment
  variable `NAME` at startup.
- `notify_threshold` must be at least `save_threshold`; every category in
  `scoring.keywords` needs a weight.
- The file is read at the start of every collection, so edits apply on the
  next run without a restart. The web process reads it when it starts.

## Sections

### `profile`

Informational: `name`, `headline`, `target`. Shown in the log banner.

### `sources`

`user_agent` and `timeout_seconds` apply to every direct HTTP request.

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
```

See [Sources](sources.md) for how to find the slug.

#### `sources.feeds`

RSS or Atom feeds: `name`, `url`, optional `locations`.

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
`retry_delay_minutes`, `max_retries`. `openings run` ignores this section.

### `notifications`

`telegram`: `enabled`, `bot_token` (`"$TELEGRAM_BOT_TOKEN"`), `chat_ids`,
`send_summary`, `max_jobs`, `jobs_per_chunk`. A digest goes out after each
run with the postings that are new in that run and at or above
`notify_threshold`; nothing already seen is repeated.

### `retention`

`max_age_days` removes jobs in status `new` not seen for that long;
`purge_blacklist_after_days` trims the blacklist. Both run at every start and
through `run_cleanup`. Jobs in any other status are never touched.

### `attachments`

`max_size_mb` per uploaded file.

### `vector_search`

Local semantic search with Chroma's bundled embedder: `enabled`,
`embed_on_save`, `default_results`, `backfill_on_startup`, `batch_size`,
`sync_interval_minutes`. The scheduler is the only writer.

### `logging`

`level`, `max_size_mb`, `backup_count`, `timezone` (IANA name).

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENINGS_DATA_DIR` | `/data` | root of the data tree |
| `OPENINGS_CONFIG` | `$OPENINGS_DATA_DIR/config/settings.yaml` | the settings file |
| `OPENINGS_API_TOKEN` | unset | token for `/api`, the dashboard and `/mcp` |
| `OPENINGS_WEB_LISTEN_PORT` | `8501` | port inside the process |
| `OPENINGS_WEB_ALLOWED_HOSTS`, `OPENINGS_WEB_ALLOWED_ORIGINS` | localhost | MCP DNS-rebinding and CORS allow-lists |
| `OPENINGS_FRONTEND_DIST` | packaged | directory of the built dashboard |
| `OPENINGS_TEMPLATE_PATH` | packaged | the example file served by `get_settings_reference` |

## Storage layout

Relative to `OPENINGS_DATA_DIR`:

```text
config/settings.yaml
db/openings.db
attachments/<job_id>/<file>
chroma/
logs/openings.log
```
