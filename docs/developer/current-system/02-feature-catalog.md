# Feature Catalog

This document groups the repository's capabilities by user value rather than by
source file.

## 1. Discovery Features

### Multi-source search aggregation

- Uses `JobSpy` to query multiple job boards from one runtime.
- Supports sites such as LinkedIn, Indeed, Glassdoor, Google Jobs, and others
  depending on `JobSpy` support and configuration.
- Runs query-location combinations in parallel.

### Query-category organization

- `queries` is a dictionary of named categories to lists of search strings.
- Categories are organizational rather than behavioral.
- Every query string is flattened and executed against each configured location.

### Search filtering controls

- Results count
- job age cutoff
- job types
- remote-only filter
- location radius
- pagination offset
- Indeed country routing
- LinkedIn-specific options
- Google Jobs search term support
- optional proxies and custom user agent

### Post-search fuzzy validation

- A fuzzy post-filter checks that the returned listing still resembles the
  query and optionally the location.
- This reduces source-side false positives.

## 2. Prioritization Features

### Configurable keyword-based scoring

- Relevance is computed from configurable keyword categories and integer
  weights.
- Categories are entirely user-defined.
- Positive and negative weights are supported at the config level.

### Dual-threshold partitioning

- `save_threshold` determines archive inclusion.
- `notify_threshold` determines notification inclusion.
- This gives the system a proper triage model.

### Boot-time rescoring

- All stored jobs are rescored on startup with the current configuration.
- This makes the archive responsive to changed scoring rules.

## 3. Persistence and Lifecycle Features

### SQLite-backed persistence

- Jobs are stored in SQLite with WAL mode and a persistent connection.
- The database records both first seen and last seen dates.

### Deterministic deduplication

- Dedupe is based on normalized SHA256 job identity.
- Duplicate listings across sources or queries collapse into one active record.

### Upsert semantics

- Existing jobs update `last_seen`.
- Relevance score only increases on conflict.
- Many nullable fields are filled through `COALESCE` logic.

### Manual state tracking

- Toggle bookmark
- Toggle applied

### Persistent blacklist

- Deleting a job from the active corpus can also blacklist it.
- Blacklisted jobs are excluded from future saves.

### Retention and reconciliation

- Delete jobs below score
- Delete stale jobs older than retention window
- Purge blacklist rows older than a configured age
- Apply all configured cleanup rules in one reconciliation pass at boot

### SQL-level protection

- Automatic delete paths never remove bookmarked or applied jobs.
- `reset_all()` is the explicit escape hatch that bypasses protection.

## 4. Attention Routing Features

### Telegram notifications

- Notifications are optional and channel-driven.
- The implementation supports chunking to respect Telegram message limits.
- Notifications can include both new jobs and top jobs already present in the
  database.

### Empty-run notifications

- The system can still send a summary even when no new matching jobs were found.

### Reconciliation notifications

- Cleanup performed at startup can trigger a compact summary notification.

## 5. Semantic Retrieval Features

### Local vector search

- Saved jobs can be embedded with ChromaDB's default ONNX embedding function.
- The vector store is stored locally under the data root.

### Backfill and sync

- Existing jobs can be backfilled into the vector store on startup.
- Deletions from the active database can be synced out of the vector store.

### Semantic search interfaces

- Streamlit dashboard search bar
- REST endpoint
- MCP tool

## 6. Human Interface Features

### Streamlit dashboard

The dashboard provides:

- semantic or fallback text search
- score, site, company, job type, remote, status, and date filtering
- paginated browsing
- inline actions for apply, bookmark, delete, open, and multi-select
- analytics charts
- database health metrics
- cleanup actions with previews
- on-demand CSV and Excel exports
- confirmation-gated full reset

### Export safety

- CSV and Excel outputs sanitize values that could trigger spreadsheet formula
  injection.

## 7. Programmatic Interface Features

### REST API

The FastAPI server exposes:

- health
- list jobs with filters and pagination
- get single job
- semantic search
- stats
- score distribution
- bookmark toggle
- apply toggle
- delete job
- bulk delete below score

### MCP server

The MCP server exposes:

- list jobs
- get job detail
- semantic search
- stats and score distribution
- bookmark/apply/delete actions
- bulk delete below score
- embedded settings documentation for LLM guidance

## 8. Operational Features

### Scheduled execution

- APScheduler-based continuous loop
- optional run-on-startup
- retry on failure with configurable delay
- consecutive failure tracking
- graceful shutdown via signals

### Logging

- colored console output
- rotating log file
- third-party noise deduplication
- rerouting of JobSpy loggers into the application's filter chain

### Docker packaging

- one image, multiple roles
- persistent `/data` root
- runtime entrypoint that requires user configuration
- Compose setup for scheduler and dashboard, with opt-in API and MCP services

### Health checks and CI

- import/config/database/directory health checks
- lint, type check, tests, security audit, Docker build verification in CI

## 9. Explicit Non-features

Important missing capabilities are not accidents; they define product scope:

- no multi-user accounts
- no authentication or authorization layer
- no employer-facing tools
- no resume tailoring workflow
- no application pipeline beyond boolean applied state
- no official source-partner integrations
- no advanced ranking model beyond configurable rules and optional semantic
  retrieval over stored jobs
