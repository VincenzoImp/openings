# Data Storage and Configuration

## Persistent Filesystem Model

The repository treats the filesystem as part of the product contract.
Everything persistent lives under one data root:

```text
{DATA_DIR}/config/settings.yaml
{DATA_DIR}/db/jobs.db
{DATA_DIR}/chroma/
{DATA_DIR}/results/
{DATA_DIR}/logs/search.log
```

Key implications:

- users can relocate the whole state tree with `JOB_SEARCH_DATA_DIR`,
- individual paths are not configurable in `settings.yaml`,
- the Docker runtime and local runtime share the same conceptual layout.

## Configuration Philosophy

The system is intentionally configuration-driven.
Most user-facing product behavior is controlled through `settings.yaml`.

### What is configurable

- search breadth and filters
- query strings
- scoring categories, weights, and thresholds
- parallelism
- retry behavior
- throttling
- post-filter matching strictness
- logging verbosity and retention
- database retention window
- profile banner fields
- scheduler cadence
- notification channel behavior
- vector-search enablement and batch sizing

### What is not configurable

- persistent directory tree shape
- SQLite as primary store
- ChromaDB as vector store implementation
- ONNX default embedding function
- CLI mode names
- SQL-level protection rules for bookmarked/applied jobs

This distinction is important:
the project does not aim for unlimited flexibility; it aims for configurable
behavior within a deliberately fixed runtime model.

## Configuration Sections

### `search`

Controls source-side retrieval.
Includes source list, result count, filters, remote behavior, location radius,
pagination, source-specific settings, and network options.

### `queries`

Dictionary of named categories to lists of query strings.
The category labels are informational and organizational only.

### `scoring`

Defines the relevance function and the two threshold boundaries.

This section is the core product intelligence configuration.

### `parallel`, `retry`, `throttling`, `post_filter`

These four sections together shape how aggressively the system interacts with
external sources and how suspicious it is of returned results.

### `database`

Currently focused on retention policy rather than storage engine tuning.

### `notifications`

Controls whether attention-routing exists and how Telegram behaves as a channel.

### `vector_search`

Controls whether the semantic index is active, whether new jobs are embedded
when saved, whether startup backfill occurs, and how large embedding batches
should be.

## SQLite Data Model

The primary table stores active jobs.
Important fields:

- identity and descriptive fields
- source metadata
- compensation data
- first seen / last seen dates
- relevance score
- applied and bookmarked flags

The `deleted_jobs` table stores blacklist memory.

## Job Identity Semantics

The identity function is local and deterministic:

```text
job_id = SHA256(normalize(title) + "|" + normalize(company) + "|" + normalize(location))
```

Advantages:

- stable across runs,
- easy to reproduce anywhere,
- independent of unreliable or source-specific IDs,
- useful for dedupe before persistence and at persistence time.

Tradeoffs:

- collisions are cryptographically implausible but semantic conflation is
  possible,
- different postings that share title/company/location collapse,
- source-native updates are not modeled as separate snapshots.

## Save Semantics

### Insert

A new job inserts with:

- `first_seen = today`
- `last_seen = today`
- current score
- `applied = false`
- `bookmarked = false`

### Update

An existing job updates:

- `last_seen` always
- `relevance_score` only when the new score is higher
- nullable metadata through `COALESCE`

This makes the active record a merged, best-known view of the job over time.

## Blacklist Semantics

Blacklisting is conceptually a move:

- capture active job metadata into `deleted_jobs`
- remove the active row from `jobs`
- prevent re-entry in later saves

This creates persistent negative memory.

## Retention Semantics

The repository distinguishes three cleanup operations:

- delete jobs below score
- delete stale jobs based on `last_seen`
- purge blacklist rows by age

Automatic delete operations respect SQL-level guards:

- `bookmarked = 0`
- `applied = 0`

That protection is embedded in SQL statements, not in UI-only logic.

## Vector Store Model

The semantic index is not the primary store.
It is a derived store built from active job records.

### Embedded text

The document is composed from:

- title
- company
- location
- description

### Metadata

Selected scalar fields are stored for search result enrichment.

### Consistency model

The vector store is eventually consistent with SQLite:

- new jobs can be embedded after save,
- startup can backfill missing embeddings,
- startup or dashboard actions can remove stale embeddings.

If vector maintenance fails, the primary SQLite corpus remains authoritative.

## Export Model

Exports are on-demand and dashboard-driven.
They are not part of the main search pipeline.

The exporter supports:

- CSV bytes
- Excel bytes
- persisted CSV
- persisted Excel

All export paths sanitize values that could be interpreted as spreadsheet
formulas.

## Data Safety and Practical Limits

### Good safety properties

- state is local and inspectable
- SQLite is easy to back up
- blacklisting is explicit
- destructive cleanup previews exist in the dashboard
- full reset is separately gated

### Practical limits

- no row versioning or snapshot history for job changes
- no per-run raw payload archive
- no audit trail for user actions
- no multi-user concurrency or authorization model
- no transactional coupling between SQLite mutations and vector operations

## Most Important Data-Level Insight

The active database is not a full historical ledger.
It is a curated working corpus shaped by score thresholds, manual curation, and
retention policy.
