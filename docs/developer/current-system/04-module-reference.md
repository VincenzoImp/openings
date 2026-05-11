# Module Reference

This reference maps the repository to responsibilities and important contracts.

## Core Runtime Modules

| Module | Responsibility | Key exports | Important notes |
|---|---|---|---|
| `src/job_search_tool/main.py` | Runtime orchestration | `main()`, `run_job_search()` | Owns boot flow, search iteration, and notification dispatch logic |
| `src/job_search_tool/scheduler.py` | Periodic execution | `JobSearchScheduler`, `create_scheduler()` | Start-to-start scheduling, retry support, signal handling |
| `src/job_search_tool/search_jobs.py` | External retrieval | `search_jobs()`, `search_single_query()`, `ThrottledExecutor` | Uses `JobSpy`, ThreadPoolExecutor, throttling, retry, incremental dedupe |
| `src/job_search_tool/scoring.py` | Ranking and partitioning | `calculate_relevance_score()`, `score_jobs()`, `partition_by_thresholds()` | Entirely config-driven keyword scoring plus fuzzy post-filtering |
| `src/job_search_tool/database.py` | Persistence and lifecycle | `JobDatabase`, `recalculate_all_scores()` | SQLite schema, blacklist, retention, stats, export |
| `src/job_search_tool/notifier.py` | Attention routing | `NotificationManager`, `TelegramNotifier`, notification dataclasses | Chunked Telegram output, best-effort delivery |

## Configuration and Models

| Module | Responsibility | Key exports | Important notes |
|---|---|---|---|
| `src/job_search_tool/config.py` | Config loading and validation | `Config`, `get_config()`, `reload_config()` | Fixed data-root layout, typed dataclasses, cross-section validation |
| `src/job_search_tool/models.py` | In-memory domain structures | `Job`, `JobDBRecord`, `SearchSummary`, `generate_job_id()` | Job identity is derived locally, not inherited from sources |
| `src/job_search_tool/logger.py` | Logging setup and helpers | `setup_logging()`, `get_logger()`, `ProgressLogger` | Deduplicates noisy third-party logging and rotates files |
| `src/job_search_tool/exporter.py` | On-demand export | `export_dataframe()`, byte helpers | Sanitizes spreadsheet-injection payloads |

## Search and Retrieval Extensions

| Module | Responsibility | Key exports | Important notes |
|---|---|---|---|
| `src/job_search_tool/vector_store.py` | Semantic index | `JobVectorStore`, `get_vector_store()` | Uses ChromaDB default ONNX embedder and local persistence |
| `src/job_search_tool/vector_commands.py` | Vector maintenance | `backfill_embeddings()`, `sync_deletions()` | Keeps embeddings aligned with SQLite state |
| `src/job_search_tool/job_service.py` | Shared server-facing service layer | `get_db()`, `get_vs()`, filtering/serialization helpers | Thin abstraction shared by dashboard, API, and MCP |

## Access Surface Modules

| Module | Responsibility | Key exports | Important notes |
|---|---|---|---|
| `src/job_search_tool/dashboard.py` | Human UI | `main()` plus many private rendering helpers | Streamlit app for review, analytics, cleanup, exports |
| `src/job_search_tool/api_server.py` | REST API | FastAPI app, response models | Thin adapter over `job_service`; exposes persisted corpus only |
| `src/job_search_tool/mcp_server.py` | LLM tool interface | `FastMCP` server with tool functions | Exposes read/write tools and generated settings documentation |
| `src/job_search_tool/healthcheck.py` | Container health | `main()` | Checks imports, config, database, and writable directories |

## Infrastructure and Packaging Files

| File | Responsibility |
|---|---|
| `Dockerfile` | Builds one runtime image for scheduler, dashboard, API, and MCP roles |
| `docker/entrypoint.sh` | Validates `/data/config/settings.yaml` and creates required directories |
| `docker-compose.yml` | Default deployment topology with scheduler and dashboard, opt-in API/MCP |
| `.github/workflows/ci.yml` | Quality, test, security, and Docker verification pipeline |
| `config/settings.example.yaml` | Exhaustive reference template, documentation artifact rather than runtime default |
| `src/job_search_tool/defaults/settings.example.yaml` | Packaged copy of the public settings template for installed entrypoints |

## Test Suite as Specification

The test suite documents important behavior beyond docstrings.

### High-signal test modules

| Test file | What it really specifies |
|---|---|
| `tests/test_config.py` | validation rules, path invariants, unsupported-key rejection |
| `tests/test_search_jobs.py` | throttling, retry, search task semantics, dedupe expectations |
| `tests/test_database.py` | blacklist semantics, score monotonicity, retention protection, batch behavior |
| `tests/test_main.py` | boot ordering, save/notify interplay, notification eligibility |
| `tests/test_integration.py` | real score-partition-save-reconcile behavior and end-to-end API/MCP flows |
| `tests/test_dashboard.py` | helper correctness and destructive-action behavior around blacklisting |
| `tests/test_api_server.py` | API contract and filter behavior |
| `tests/test_mcp_server.py` | MCP tool contract |
| `tests/test_vector_store.py` | vector store add/search/filter/delete semantics |

## Dependency Structure

### Most central modules

The conceptual center of gravity is:

- `config.py`
- `database.py`
- `main.py`
- `search_jobs.py`
- `scoring.py`

### Adapter pattern in practice

The repository already exhibits a lightweight adapter/core split:

- core behavior in config, database, search, scoring, notifier, vector store
- adapters in dashboard, API, MCP, Docker entrypoint, scheduler shell

This is not a full clean architecture, but it is enough to keep most code paths
coherent.

## Modules with the Most Domain Weight

### `database.py`

This file is not just persistence plumbing.
It encodes product policy:

- blacklisted jobs stay excluded,
- bookmarks and applied jobs survive automated deletion,
- reconciliation is the operational meaning of retention,
- full reset is an exceptional escape hatch.

### `main.py`

This file is not just a CLI shell.
It defines the business sequence:

- when rescoring happens,
- when cleanup happens,
- when embedding happens,
- which jobs are considered new,
- which new jobs are worthy of notification.

### `config.py`

This file is not just config parsing.
It defines what the product considers configurable and what it treats as fixed
operational doctrine, especially around the persistent directory layout.

## Notable Design Choices by Module

### Search uses DataFrames early

The system stays in pandas/DataFrame form through search and scoring because the
source library already returns that shape efficiently.
Typed models are used mainly at persistence boundaries and server/UI output
boundaries.

### Dashboard is intentionally stateful and imperative

The dashboard uses Streamlit session state, reruns, and direct database writes.
This is appropriate for a single-user operator console, even if it would be
insufficient for a complex multi-user product.

### API and MCP are intentionally thin

The servers do not reinvent business logic.
They rely on `job_service` and the database layer, which keeps the adapters
small and behaviorally aligned.

## Modules That Encode Invariants

If someone wants to modify system behavior safely, these files deserve the most
care:

- `src/job_search_tool/config.py`
- `src/job_search_tool/scoring.py`
- `src/job_search_tool/database.py`
- `src/job_search_tool/main.py`
- `src/job_search_tool/job_service.py`

Together they define the meaning of search, persistence, cleanup, retrieval,
and exposure.
