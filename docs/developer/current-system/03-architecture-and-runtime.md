# Architecture and Runtime

## System Topology

The repository is a shared-core application with multiple adapters.

```text
                    settings.yaml
                         |
                         v
                +-------------------+
                |   config.py       |
                +-------------------+
                         |
                         v
 +----------------+  +-------------------+  +-------------------+
 | main.py / CLI  |->| search_jobs.py    |->| external job sites |
 +----------------+  +-------------------+  +-------------------+
         |                    |
         |                    v
         |             +-------------+
         |             | scoring.py  |
         |             +-------------+
         |                    |
         v                    v
 +----------------+   +-------------------+      +-------------------+
 | scheduler.py   |   | database.py       |<---->| dashboard / API / |
 +----------------+   +-------------------+      | MCP via service    |
         |                    |                  +-------------------+
         |                    |
         |                    +-------> exporter.py
         |                    |
         |                    +-------> notifier.py
         |                    |
         |                    +-------> vector_store.py
         |                             vector_commands.py
         |
         +------ logging.py
```

## Runtime Modes

The system has three CLI modes controlled by subcommand:

- `scheduler`: continuous periodic execution
- `once`: execute one search cycle and exit
- `dashboard`: replace the process with Streamlit on port 8501

The API and MCP server are separate installed entrypoints, not subcommands of
`main.py`.

## Boot Sequence

Boot behavior is more important than it may first appear because several
system-wide invariants are enforced there.

### Shared startup flow

1. load config via `get_config()`
2. set up logging
3. initialize database
4. if the database is non-empty, recalculate all scores
5. reconcile the database with current retention settings
6. if vector search is enabled:
   - get vector store
   - sync deletions if reconciliation removed jobs
   - optionally backfill embeddings for missing jobs
7. if reconciliation deleted anything and notifications are enabled, send a
   cleanup summary
8. hand off to scheduled execution or one-shot execution

### Why this matters

The repository treats the configuration file as declarative.
Changing `settings.yaml` and restarting is intended to bring stored state back
in line with the new rules.

## Search Iteration Flow

The active search loop in `run_job_search()` looks like this:

1. reload config
2. set up logging with the fresh config
3. print banner
4. open database and read statistics
5. search external sources in parallel
6. if no results:
   - optionally send empty-run notification
   - finish successfully
7. score all returned jobs
8. partition into `scored`, `to_save`, `to_notify`
9. remove blacklisted jobs from `to_save`
10. compute which current-run jobs are genuinely new
11. upsert `to_save` into SQLite
12. if vector search is enabled, embed saved jobs
13. print top jobs to logs
14. intersect current-run new IDs with the notify partition
15. load those jobs from the database
16. send notifications if applicable

## Search Execution Model

### Task generation

The search engine builds tasks from every `(query, location)` pair.

### Parallelism

- ThreadPoolExecutor is used for concurrency.
- Worker count is config-driven.
- Search results are collected as futures complete.

### Throttling

- The wrapper computes the slowest configured site delay among active sites.
- A global lock enforces a minimum gap between actual search dispatches.
- Jitter introduces random variation to reduce regular request patterns.

### Retry behavior

- `search_single_query()` retries on connection and timeout errors.
- Backoff is exponential with configurable multiplier and attempt count.

### Incremental deduplication

- Each result row gets a derived job ID.
- Search-time dedupe happens before persistence.
- Save-time dedupe also exists through database upsert.

## Data Flow by Layer

### External source layer

- Heterogeneous job boards
- unstable schemas and rate limits
- dependent on `JobSpy` support and source behavior

### Normalization layer

- pandas DataFrames
- shared column names across sources
- `Job` dataclass for local logical representation

### Decision layer

- fuzzy post-filter
- relevance scoring
- threshold partitioning
- blacklist exclusion

### Persistence layer

- active jobs table
- deleted jobs blacklist table

### Retrieval layer

- SQL queries for deterministic filtering
- vector search for semantic lookup over stored jobs

### Access layer

- Streamlit for human control
- FastAPI for scripts
- MCP for LLMs

## State Machines

### Job lifecycle

```text
Source listing
  -> normalized result
  -> scored result
  -> below save threshold -> dropped
  -> above save threshold -> active job in DB
  -> bookmarked/applied -> protected active job
  -> blacklisted -> removed from active table, stored in deleted_jobs
  -> purged blacklist -> forgotten negative memory
```

### Notification lifecycle

```text
Current run results
  -> score >= save threshold
  -> job ID is new for this run
  -> score >= notify threshold
  -> notification payload
  -> Telegram chunked delivery
```

## Service Surfaces

### Dashboard

The dashboard is a write-capable operational workbench, not only a report.
It allows:

- browsing and filtering
- state toggles
- blacklisting
- exports
- retention execution
- full reset

### REST API

The API is intentionally thin.
It does not launch searches or perform scoring pipelines.
It exposes the current persisted corpus.

### MCP server

The MCP server exposes the same corpus to an LLM plus static settings
documentation.
It explicitly does not read the user's private profile or configuration file.

## File and Deployment Topology

Every persistent path is derived from one root:

- `config/settings.yaml`
- `db/jobs.db`
- `chroma/`
- `results/`
- `logs/search.log`

In Docker this root is `/data`.
Locally it defaults to the repository root unless `JOB_SEARCH_DATA_DIR` is set.

## Failure Model

The system is designed for graceful degradation rather than strict guarantees.

- Source failures usually fail a query, not the entire process.
- Notification failures do not abort search completion.
- Vector store failures are logged as warnings and skipped.
- The dashboard is designed to remain useful even if vector search is
  unavailable.
- Health checks focus on local operability, not external source reachability.

## Architectural Summary

The current architecture is best described as a configuration-driven modular
single-user automation system with shared local state and multiple thin
interaction adapters.
