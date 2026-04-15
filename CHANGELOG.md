# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [6.0.2] - 2026-04-15

### Fixed

- **First-run permission error on non-root containers**: the default `docker-compose.yml` now uses a Docker-managed named volume (`jobsearch-data`) instead of a `./data` host bind mount. On hosts where Docker creates `./data` as `root:root` (the common case when the Docker daemon itself runs as root — e.g. alpine-docker without userns-remap), the non-root container (`appuser`, UID 1000) would fail to write with `mkdir: cannot create directory '/data/config': Permission denied`. Named volumes inherit their ownership from the image, so the container writes to them without any host-side preparation.

### Changed

- **`docker-compose.yml`** switches from `./data:/data` bind mount to `jobsearch-data:/data` named volume. Both services still share the same volume, still run as `appuser`, still auto-scaffold `settings.yaml` on first boot.
- **`docker-compose.dev.yml`** follows the same pattern for the local-build override.
- **README Quick Start** updated: new compose snippet, `docker compose cp` workflow for editing `settings.yaml`, documented `docker run --rm -v jobsearch-data:/data alpine tar …` backup/restore recipe (the canonical Docker named-volume backup pattern).
- Standalone `docker run` examples in the README now create and reuse a named volume (`docker volume create jobsearch-data`) instead of mounting host paths.
- `.gitignore` excludes the whole `data/` directory tree so local dev state under the repo root never accidentally ends up in a commit.

### Migration

No user-facing migration: v6.0.1 never successfully ran on a host with a root-owned bind mount, so there is no persisted state to preserve. If you already have a `./data/config/settings.yaml` from local experimentation, copy its contents into the new volume after the first `docker compose up -d`:

```bash
docker compose up -d
docker compose cp ./data/config/settings.yaml scheduler:/data/config/settings.yaml
docker compose restart scheduler
```

## [6.0.1] - 2026-04-15

### Changed

- **Single Docker image**: the dashboard/core variant split from v5.0.0 is removed. One image tree, one tag family (`:latest`, `:vX.Y.Z`, `:vX.Y`, `:vX`, `:sha-<commit>`). Both Compose services pull the same image — Docker downloads it once and shares layers — and differ only by the command they run.
- **Unified CLI subcommands**: `scripts/main.py` now accepts subcommands:
  - `python main.py` / `python main.py scheduler` — continuous scheduler loop (default)
  - `python main.py once` — single-shot run (for cron / CI)
  - `python main.py dashboard` — `exec`-replaces the process with Streamlit on port 8501
  Replaces the v6.0.0 transient `--once` flag.
- **`docker-compose.yml`** uses explicit `command: ["python", "main.py", <subcommand>]` on both services.
- **Streamlit moved back to main dependencies** in `pyproject.toml`; the `[project.optional-dependencies] dashboard` extra is removed.
- **Dockerfile** simplified to a single target: no more `ARG VARIANT`, no more `builder-core` / `builder-dashboard` / `builder-final` stages.
- **CI + publish workflows** drop the `[dashboard, core]` matrix and build once per run.
- **README Quick Start** fixes a copy-paste bug from v6.0.0 where the dashboard service was missing a `command:` override and would have silently run a second scheduler instead of Streamlit.

### Removed

- Docker image tag families `:latest-core`, `:vX.Y.Z-core`, `:core`, `:sha-<commit>-core`.
- `--build-arg VARIANT` on the Dockerfile.
- `[project.optional-dependencies] dashboard` in `pyproject.toml`.
- CI matrix build of two variants in `.github/workflows/ci.yml`, `publish-release.yml`, `publish-main.yml`.

## [6.0.0] - 2026-04-15

### Changed (BREAKING)

- **Minimal two-service Compose stack**: `docker-compose.yml` collapses to two flat services — `scheduler` on `:latest-core` and `dashboard` on `:latest` — sharing a single `./data:/data` volume. YAML anchors, profiles, `init-config`, `jobsearch`, and `analyze` services are gone. `docker compose up -d` now starts the continuous scheduler and the dashboard together out of the box.
- **Single `/data` volume**: every persistent file now lives under one mount point with a fixed layout — `/data/config/settings.yaml`, `/data/db/jobs.db`, `/data/chroma/`, `/data/results/`, `/data/logs/search.log`. Users go from four bind mounts (`config/`, `data/`, `results/`, `logs/`) to **one**. Override the root with `JOB_SEARCH_DATA_DIR`.
- **First-run auto-bootstrap**: on startup, the container creates `/data/config/settings.yaml` from the bundled template if it is missing, scaffolds the `/data/{config,db,chroma,results,logs}` subtree, and logs a clear "edit me and restart" hint. The `init-config` service and `scripts/bootstrap_config.py` helper are removed — both obsolete.
- **Scheduler is the default mode**: `python main.py` now starts the continuous APScheduler loop by default. Use `python main.py --once` for a one-off single-shot run (cron, CI). The `JOB_SEARCH_MODE=single|scheduled` env variable is gone.
- **Fixed persistent paths**: `output.results_dir`, `output.data_dir`, `output.database_file`, `logging.file`, `vector_search.model_name`, and `vector_search.persist_dir` are removed from `settings.yaml`. They are silently accepted with a one-line warning to ease the transition. Use `JOB_SEARCH_DATA_DIR` to relocate the whole tree.
- **Dockerfile runs under `tini`** for clean SIGTERM propagation, declares `VOLUME /data`, and exports `JOB_SEARCH_DATA_DIR=/data` as a default env.
- **`.env.example` slimmed down**: dropped `JOB_SEARCH_IMAGE` / `JOB_SEARCH_CORE_IMAGE` / `JOB_SEARCH_DASHBOARD_IMAGE`, kept only the Telegram token, UID/GID, and dashboard port.
- **`docker-compose.dev.yml` rewritten**: rebuilds both variants (`core` and `dashboard`) from the local checkout via `--build-arg VARIANT=...`.

### Removed

- `scripts/bootstrap_config.py` and its tests — the entrypoint does the bootstrap inline.
- Compose services: `init-config`, `jobsearch`, `analyze`, all profile-gated services. Use `docker compose exec scheduler python analyze_jobs.py` for ad-hoc analysis.
- `scripts/main.py::_resolve_scheduled_mode` and the `JOB_SEARCH_MODE` env switch.
- `OutputConfig.results_dir` / `.data_dir` / `.database_file`, `LoggingConfig.file`, `VectorSearchConfig.model_name` / `.persist_dir`.
- `get_vector_store(persist_dir, model_name=...)` signature — the `model_name` parameter is gone (it was already a no-op since v4.4.0).

### Quick Start

```yaml
services:
  scheduler:
    image: vincenzoimp/job-search-tool:latest-core
    restart: unless-stopped
    volumes: ["./data:/data"]

  dashboard:
    image: vincenzoimp/job-search-tool:latest
    restart: unless-stopped
    ports: ["8501:8501"]
    volumes: ["./data:/data"]
```

```bash
docker compose up -d
# edit ./data/config/settings.yaml, then:
docker compose restart scheduler
```

Six lines of YAML, one volume, one command. Dashboard at http://localhost:8501.

## [5.0.1] - 2026-04-15

### Documentation

- **Sync stale references** to match the v5.0.0 variant split and v4.4.0 ONNX embedder migration:
  - `README.md`: feature tables, ASCII execution-flow diagram, Docker Publishing section rewritten for the core/dashboard matrix, `docker run` examples updated to prefer `:latest-core` for headless usage, Acknowledgments cleaned of the removed `sentence-transformers` entry, test count refreshed.
  - `CONTRIBUTING.md`: dashboard launch command no longer references the removed `--profile dashboard`.
  - `.env.example`: replaces `JOB_SEARCH_IMAGE` with `JOB_SEARCH_CORE_IMAGE` and `JOB_SEARCH_DASHBOARD_IMAGE`.
  - `config/settings.example.yaml`: `vector_search` block now documents that `model_name` is ignored and describes the ONNX embedder.
  - `CLAUDE.md` / `AGENTS.md`: tech stack table, project tree comment on `Dockerfile`, internal changelog (v4.4.0 + v5.0.0 entries added), "Last Updated" date refreshed. `AGENTS.md` is now tracked alongside `CLAUDE.md`.
  - `scripts/dashboard.py`: "semantic search unavailable" hint no longer mentions the removed `sentence-transformers` package.

No functional or Docker-image changes — the v5.0.0 and v5.0.1 images are byte-for-byte equivalent aside from the `VERSION` build label.

## [5.0.0] - 2026-04-15

### Changed (BREAKING)

- **Two Docker image variants**: The project now publishes two variants from the same tag family:
  - `vincenzoimp/job-search-tool:X.Y.Z` (default, dashboard) — full stack with Streamlit UI, behaves like previous `:latest`.
  - `vincenzoimp/job-search-tool:X.Y.Z-core` — slim image, Streamlit removed (~200 MB smaller).
- **Dockerfile rewritten as variant-aware**: Single parameterized `runtime` stage, variant chosen at build time via `--build-arg VARIANT=core|dashboard` (default: `dashboard`). Replaces the previous single-target build.
- **`docker-compose.yml` wires each service to the right image**: `jobsearch`, `scheduler`, `analyze`, `init-config` → core image (`${JOB_SEARCH_CORE_IMAGE:-vincenzoimp/job-search-tool:latest-core}`); `dashboard` → dashboard image (`${JOB_SEARCH_DASHBOARD_IMAGE:-vincenzoimp/job-search-tool:latest}`). Headless services automatically benefit from the slim image without user intervention.
- **Dashboard runs by default**: `docker compose up` now starts `jobsearch` + `dashboard` out of the box. The `dashboard` profile has been removed (no longer needed). Old usage `docker compose --profile dashboard up dashboard` becomes `docker compose up dashboard`.
- **`JOB_SEARCH_IMAGE` env var removed**: Replaced by `JOB_SEARCH_CORE_IMAGE` and `JOB_SEARCH_DASHBOARD_IMAGE`. Users overriding the image via environment variable must update their setup.
- **`streamlit` moved to optional dependency** `[project.optional-dependencies] dashboard` in `pyproject.toml`. Local `uv sync` (with default dev group) still installs it for test suites; production core builds do not.
- **Pruned `.venv`** in builder stage: removes `__pycache__`, `*.pyc`, `*.pyo`, `*.pyi`, and bundled `tests/` directories from installed packages before the runtime copy. Saves ~50–100 MB on both image variants.
- **CI Docker smoke job** now builds both variants in a matrix and runs the healthcheck on each, so regressions in either build path are caught on PRs.

### Migration notes

- **`:latest` still works and still ships Streamlit** — no change for users pulling the default tag for a dashboard deployment.
- If you override the compose image via `JOB_SEARCH_IMAGE`, replace it with `JOB_SEARCH_CORE_IMAGE` (and optionally `JOB_SEARCH_DASHBOARD_IMAGE` for the dashboard service).
- If you had scripts doing `docker compose --profile dashboard up`, drop the flag — the dashboard is now a default service.

## [4.4.0] - 2026-04-15

### Changed

- **Lightweight Vector Search**: `JobVectorStore` now uses ChromaDB's built-in `DefaultEmbeddingFunction` (onnxruntime + bundled `all-MiniLM-L6-v2`) instead of `sentence-transformers`. Same embedding model, same search quality, no torch runtime.
- **Dependency Slimdown**: Removed `torch`, `sentence-transformers`, and `transformers` from runtime dependencies. Docker image size drops by roughly 2.5–3 GB (the previous lock also pulled the full CUDA stack — `nvidia-cublas`, `cudnn`, `nccl`, `triton`, etc. — despite `UV_TORCH_BACKEND=cpu`).
- **Dockerfile**: Removed the now-unused `UV_TORCH_BACKEND=cpu` build arg.

### Deprecated

- `vector_search.model_name` is now ignored — the store always uses the model bundled with ChromaDB's default embedder. A warning is logged if a non-default value is configured. The setting is retained for backward compatibility and will be removed in a future release.

## [4.3.2] - 2026-04-14

### Changed

- **Release Workflow Simplification**: Docker images now publish automatically from version tags only, while `publish-main.yml` is now a manual maintainer workflow and CI keeps the Docker smoke build on pull requests instead of every push to `main`
- **Release Documentation Alignment**: Updated the README and changelog so the documented release flow matches the actual GitHub Actions behavior

## [4.3.1] - 2026-04-14

### Changed

- **CI Pipeline Efficiency**: Split formatting/type checks out of the Python-version matrix, keep coverage on Python 3.11 only, skip docs-only runs, and cancel superseded in-flight CI runs
- **Docker CI Validation**: The Docker job now bootstraps a real config and runs the health check for the built image instead of masking failures

### Fixed

- **Dashboard CSV Safety**: Filtered dashboard CSV exports now reuse the shared spreadsheet sanitization path, preventing formula-injection regressions
- **Logger Handler Lifecycle**: Repeated logging setup now closes replaced handlers, avoiding file-descriptor leaks in long-lived scheduled runs
- **Telegram Delivery Reporting**: Notification success now reflects whether job chunks were actually delivered instead of treating partial failures as success
- **Stable Job IDs**: Internal job IDs now normalize trivial whitespace and Unicode spacing differences, and existing databases/blacklists are migrated automatically on startup
- **Dashboard Import Side Effects**: Importing `dashboard.py` no longer executes the Streamlit app outside `streamlit run`

## [4.3.0] - 2026-04-14

### Added

- **uv Project Tooling**: Added `pyproject.toml` and `uv.lock` so local setup, CI, and Docker builds resolve from the same locked dependency graph
- **Split Docker Publish Workflows**: Added dedicated `publish-main.yml` and `publish-release.yml` workflows to separate fast `main` publishes from full multi-arch release publishing

### Changed

- **CI Dependency Sync**: Test and security jobs now install dependencies with `uv` instead of `pip install -r ...`, improving setup consistency and cache reuse
- **Docker Builder Install Path**: The image builder now installs from `uv.lock` with `uv sync --locked --no-install-project`, keeping runtime layers aligned with CI
- **Publish Scope**: `main` publishes are now path-filtered to Docker/runtime-affecting files, so docs-only merges stop triggering image rebuilds
- **Docker Build Caching**: Builder-stage dependency install now uses a dedicated uv cache mount in addition to Buildx cache scopes
- **Developer Documentation**: README and CONTRIBUTING now describe `uv sync` and `uv run` as the default local workflow while keeping Docker Compose as the recommended runtime path

### Fixed

- **CI uv Action Pinning**: GitHub Actions now pins `astral-sh/setup-uv@v8.0.0`, avoiding resolution failures on floating major tags
- **Runtime Image Ownership**: Docker runtime setup now creates writable app directories explicitly instead of recursively chowning the bundled virtual environment

### Removed

- **Unused Plotting Dev Dependencies**: Removed `matplotlib` and `seaborn` from development dependencies because they were no longer used by `analyze_jobs.py` or the test/tooling stack

## [4.2.1] - 2026-04-14

### Fixed

- **Search Job-Type Filtering**: `search.job_types` is now applied to JobSpy requests so configured employment-type filters affect real searches
- **Run-Scoped Notifications**: Telegram notifications now include only jobs that are new in the current run instead of replaying all jobs first seen on the same day
- **Dashboard HTML Escaping**: Job metadata rendered with `unsafe_allow_html=True` is now escaped first to avoid markup injection from scraped content
- **CSV Formula Injection Protection**: CSV exports now reuse the spreadsheet sanitization path already used for Excel exports
- **Scheduler Retry Drift**: Retry runs no longer shift the cadence of the main scheduled job
- **Latest Results Detection**: `analyze_jobs.py` now uses file modification time (`mtime`) when picking the latest results export
- **CI Formatting Consistency**: Dashboard smoke-test formatting now matches `ruff format`, keeping `main` green in CI

## [4.2.0] - 2026-04-14

### Added

- **Persistent Deleted-Job Blacklist**: Deleting jobs from the dashboard now stores their internal `job_id` in a dedicated blacklist so future searches skip them automatically
- **Dashboard Bulk Delete Improvements**: Added clearer multi-select delete flows in the jobs view and kept vector-store deletions in sync
- **Docker Hub Publishing Workflow**: Added a dedicated GitHub Actions workflow for multi-arch Docker Hub publishing with OCI labels, SBOM, and provenance attestations
- **Docker Config Bootstrap**: Added `init-config`, `docker/entrypoint.sh`, and `bootstrap_config.py` so users can scaffold `config/settings.yaml` directly from the image
- **Local Docker Build Override**: Added `docker-compose.dev.yml` for contributors who want Compose UX while testing a local image build

### Changed

- **Docker UX**: `docker-compose.yml` is now Docker Hub-first and documents `jobsearch`, `scheduler`, `dashboard`, `analyze`, and `init-config` as the main user-facing services
- **Execution Mode Override**: Added `JOB_SEARCH_MODE` so Compose can force single-shot vs scheduled behavior without requiring users to toggle `scheduler.enabled`
- **Secure Dependency Baseline**: Updated the sentence-transformer / transformers stack and pinned `torch` for a more reproducible CPU-oriented Docker build
- **Contributor Onboarding**: Updated contributor docs to match the current Compose and CI workflow
- **Docker Publish Strategy**: `main` now publishes a faster `linux/amd64` image, while version tags publish the full multi-arch release set and refresh `latest`

### Fixed

- **Dashboard Excel Export**: Dashboard exports now reuse the shared Excel sanitization path to prevent formula injection regressions
- **Vector Store Config Respect**: The vector store now honors the configured persistence directory and recreates its singleton when path or model settings change
- **Test/Docs Drift**: Documentation now reflects the current 330+ test suite and the new deleted-job blacklist behavior

## [4.1.1] - 2026-03-13

### Fixed

- **Dashboard Port Binding**: Opened to all interfaces (`8501:8501` instead of `127.0.0.1:8501:8501`) for broader network accessibility
- **Logger Permission Handling**: File handler gracefully handles `PermissionError`, falling back to console-only logging instead of crashing
- **Noisy Third-Party Logs**: Suppressed JobSpy internal errors (Glassdoor 400s, LinkedIn country parsing) and ChromaDB telemetry warnings from console output
- **Search Error Logging**: Upstream library errors (e.g. JobSpy `LinkedInException`) logged as single-line warnings instead of full tracebacks

## [4.1.0] - 2026-03-13

### Added

- **Unapply Functionality**: `toggle_applied()` and `mark_as_unapplied()` methods in database API
- **Dashboard Toggle Apply/Unapply**: Per-job card toggle and bulk unapply button in DB management

### Fixed

- **Streamlit Server Address**: Changed to `0.0.0.0` inside Docker container for host accessibility
- **Default Location**: Updated `settings.example.yaml` default location

## [4.0.0] - 2026-03-13

### Added

- **Semantic Vector Search**: ChromaDB + sentence-transformers integration for natural language job search
- **New Module `vector_store.py`**: `JobVectorStore` class with add, search, delete, backfill operations
- **New Module `vector_commands.py`**: `backfill_embeddings()` and `sync_deletions()` utilities
- **New Module `scoring.py`**: Extracted relevance scoring engine from search_jobs.py
- **New Module `exporter.py`**: Extracted CSV/Excel export with formula injection protection from search_jobs.py
- **Unified Dashboard**: Rewritten `dashboard.py` as "Job Search Hub" with semantic search, card-based display, inline actions
- **Bookmark Feature**: `bookmarked` column in database, `toggle_bookmark()` method
- **Delete Feature**: `delete_job()` and `delete_jobs()` methods in database
- **Bulk Operations**: Select multiple jobs for batch bookmark/delete/apply from dashboard
- **VectorSearchConfig**: New configuration section (`vector_search`) with model, persistence, and backfill settings
- **New Tests**: test_exporter.py (14), test_search_jobs.py (20), test_healthcheck.py (12), test_report_generator.py (16), test_analyze_jobs.py (16), test_vector_store.py (34)
- **Pre-commit in CI**: Pre-commit hooks now run as part of the CI pipeline

### Changed

- **Frozen Dataclasses**: `Job`, `JobDBRecord`, `SearchResult` are now `@dataclass(frozen=True)` for immutability
- **Module Extraction**: Scoring and export logic moved from `search_jobs.py` to dedicated modules
- **Dashboard Rewrite**: Old multi-page dashboard replaced with unified single-page hub
- **CI Coverage Threshold**: Raised from 50% to 60%
- **Test Count**: From 160 to ~324 tests
- **Dependencies**: Added chromadb, sentence-transformers; removed Jinja2; moved matplotlib/seaborn to dev

### Fixed

- **Pandas 3.x Compatibility**: Excel column sizing uses `.str.len()` instead of `.map(len)`
- **Excel Sanitization**: `+/-` only escaped when followed by digit (avoids corrupting text like "-some description")
- **Config Validation**: `warnings.warn()` replaced with `logger.warning()` throughout config.py
- **Circular Imports**: database.py imports scoring from `scoring` module instead of `search_jobs`

## [3.1.0] - 2026-02-15

### Added

- **CI Pipeline**: GitHub Actions workflow with test matrix (Python 3.11/3.12), pip-audit security scan, and Docker build verification
- **Pre-commit Hooks**: Ruff lint/format, trailing whitespace, end-of-file fixer, detect-private-key
- **Scheduler Max Retries**: New `scheduler.max_retries` setting (default: 3, 0 = unlimited) to stop infinite retry loops
- **Consecutive Failure Tracking**: Scheduler tracks `_consecutive_failures` counter, resets on success
- **Config Cross-Validation**: Warns when scoring `weights` and `keywords` categories are mismatched
- **Bot Token Warning**: Warns when Telegram bot_token is hardcoded in config file (recommends env var)
- **Description Format Validation**: `search.description_format` validated against `{markdown, html, plain}`
- **Main Entry Point Tests**: 7 new tests for `run_job_search()` and `main()` functions
- **Config Singleton Reset**: Autouse fixture in conftest.py prevents state leakage between tests

### Fixed

- **SQLite WAL Mode**: Database now uses WAL journal mode + `busy_timeout=5000` for better concurrent access
- **Persistent DB Connection**: Connection reused across calls with auto-reconnect on error (was creating new connection per operation)
- **Thread Safety**: Deduplication `append` moved inside lock in search_jobs.py to prevent concurrent list mutations
- **DataFrame Side-Effect**: `filter_relevant_jobs` now works on a copy instead of mutating input DataFrame
- **Unicode Normalization**: `_normalize_text` uses `unicodedata.normalize("NFKD")` instead of manual 14-char replacement table
- **Null Safety**: Telegram `_format_job_message` handles None `title` and `relevance_score`
- **Async/Sync Bridge**: `send_all_sync` uses `asyncio.new_event_loop()` in thread instead of `asyncio.run()` (avoids nested loop issues)

### Changed

- **Dockerfile**: Multi-stage build with non-root user (`appuser`, UID 1000) for security
- **Docker Compose**: Removed `./scripts` volume mount from all services (was overriding built image, defeating Docker purpose)
- **Docker Compose**: Added `env_file: .env` (optional) to all services for secret management
- **.gitignore**: Added `.env`, `.env.*`, `.ruff_cache/`, `docker-compose.override.yml`
- **.dockerignore**: Added test files, dev configs, type checking caches, env files
- **requirements-dev.txt**: Added `pytest-timeout`, `pytest-randomly`, `pip-audit`

## [3.0.2] - 2026-01-12

### Fixed

- **Scheduler Interval**: Now calculated from run start to start (not end to start) for consistent intervals
- **Long-Running Jobs**: Scheduler skips to next future slot when run duration exceeds interval
- **Telegram Chunking**: Each chunk sent independently (one failed chunk doesn't stop others)
- **DateTrigger**: Fixed `next_run_time` attribute error with DateTrigger jobs

### Changed

- Replaced `IntervalTrigger` with `DateTrigger` for precise start-to-start scheduling
- Added `JOB_SEARCH_CONFIG` environment variable for config file override

## [3.0.1] - 2026-01-01

### Removed

- **Docker Memory Limits**: Removed memory limits from all services in docker-compose.yml due to compatibility issues with some Docker versions

## [3.0.0] - 2026-01-01

### Added

- **Top Jobs Overall in Notifications**: Telegram notifications now show two sections:
  - 🆕 New Jobs - Jobs found in the current search run
  - 🏆 Top Jobs Overall - Best jobs from the entire database (configurable via `include_top_overall` and `max_top_overall`)
- **New Database Methods**: `get_top_jobs(limit, min_score)` and `get_job_count()` for notification support
- **Configurable jobs_per_chunk**: Now exposed in settings.yaml (previously hardcoded constant)

### Fixed

- **SQLite Variable Limit**: Added batch querying (`SQLITE_VAR_LIMIT = 500`) to handle large job ID sets without hitting SQLite's 999 variable limit
- **Lock Duration**: Optimized deduplication to minimize lock scope (compute outside lock, quick set operations inside)
- **Scoring Config Mutation**: Fixed `_parse_scoring_config` to create new dicts instead of mutating defaults
- **Logger Levelname**: ColoredFormatter now restores original levelname after formatting
- **Excel Empty Check**: Added DataFrame empty check before Excel save to prevent errors
- **Environment Variable Warning**: Added warning when Telegram bot token env var is not resolved

### Changed

- **NotificationData Enhanced**: Added `top_jobs_overall` and `total_jobs_in_db` fields for comprehensive notifications
- **Precompiled Regex**: Added precompiled regex for MarkdownV2 escaping in notifier (performance improvement)
- **Docker Memory Limits**: Added to all services in docker-compose.yml (reverted in v3.0.1)

### Removed

- Unused imports in scheduler.py (`sys`, `time`), main.py (`pandas`, `datetime`), search_jobs.py (`hashlib`)

## [2.5.4] - 2026-01-01

### Added

- **Database Cleanup**: New `database.cleanup_enabled` and `database.cleanup_days` settings to automatically remove old jobs
- **Chunked Telegram Messages**: Messages now split into chunks of 10 jobs to avoid Telegram's 4096 character limit

### Changed

- Score recalculation moved to startup only (not every search iteration)
- Improved documentation with ASCII architecture diagrams

## [2.5.3] - 2026-01-01

### Added

- **Score Recalculation on Startup**: All existing jobs in the database now have their relevance scores recalculated on startup using the current scoring configuration
- New `recalculate_all_scores()` function in `database.py`

### Changed

- No rebuild needed when changing scoring criteria - just modify `settings.yaml` and run `docker compose up`

## [2.5.2] - 2025-12-31

### Fixed

- **Telegram MarkdownV2**: Fixed URL escaping in Telegram notifications - URLs with special characters now display correctly

## [2.5.1] - 2025-12-31

### Fixed

- **Docker Build**: Removed non-existent `templates/` directory reference from Dockerfile that was causing build failures

## [2.5.0] - 2025-12-31

### Added

- **Test Suite**: Comprehensive pytest test suite with 60+ tests covering models, config, database, and scoring
- **Health Check**: Real Docker health check script that verifies imports, config, database, and directories
- **Input Validation**: Comprehensive validation for all numeric configuration parameters
- **Timezone Config**: New `logging.timezone` setting for customizable log timestamps
- **Dev Dependencies**: New `requirements-dev.txt` with pytest, mypy, ruff, black

### Fixed

- **CRITICAL**: Added missing `self.logger` in `database.py` - was causing `AttributeError` on migration failures
- **CRITICAL**: Fixed async/sync bridge in `notifier.py` - `send_all_sync()` now works correctly in async contexts
- **CRITICAL**: Increased job ID hash from 16 to 64 characters (full SHA256) to prevent collisions
- Exception handling in `search_jobs.py` now uses specific exception types instead of broad `except Exception`
- Removed unnecessary DataFrame copies in `filter_relevant_jobs()` for better memory usage

### Changed

- Default timezone changed from hardcoded `Europe/Zurich` to configurable `UTC`
- Docker restart policies now consistent across all services

## [2.4.0] - 2025-12-31

### Changed

- **BREAKING**: Scoring system is now fully config-driven with no hardcoded categories
- `calculate_relevance_score()` dynamically iterates over all keyword categories defined in config
- Default scoring categories are now generic (primary_skills, technologies, seniority, etc.)
- Default queries are now generic software engineering roles
- Supports negative weights for penalizing unwanted matches (e.g., senior positions)
- Banner now uses logger instead of print() for consistency

### Fixed

- Scheduler `self._logger` typo causing silent failure on retry scheduling
- Excel cell type conversion now handles float/string values safely
- Banner text truncation prevents formatting issues with long profile strings

### Removed

- All hardcoded keywords (open source, hackathon, teaching, computer science, etc.)
- All hardcoded location bonuses (zurich, lausanne, eth, epfl, etc.)

## [2.3.0] - 2025-12-28

### Fixed

- **CRITICAL**: Scheduler retry time calculation bug (incorrect modulo arithmetic)
- **CRITICAL**: SQL error handling now only ignores duplicate column errors
- Telegram token now supports environment variable for security
- Removed hardcoded personal information from ProfileConfig defaults
- SQLite connection properly managed with context manager
- Race condition in job deduplication resolved
- asyncio.run() now works correctly in async contexts
- N+1 database query optimized to single batch query
- Config singleton now thread-safe with locking
- Input validation for all config parameters
- Type hints corrected (any → Any)
- Color codes only applied to TTY output

### Changed

- Dockerfile gcc removed after build for smaller image
- Version upper bounds added to all dependencies

## [2.2.0] - 2025-12-27

### Added

- **Fuzzy Post-Filtering**: Validate results match query terms with typo tolerance
- `PostFilterConfig` with min_similarity, check_query_terms, check_location settings
- `rapidfuzz` dependency for fuzzy string matching

### Fixed

- Removed hardcoded 10 job limit in Telegram notifications (now uses config)

### Changed

- Character variations (ü/u, ö/o) and typos handled automatically in post-filtering

## [2.1.0] - 2025-12-27

### Added

- **Configurable Throttling**: Per-site delays with jitter to prevent rate limiting
- `country_indeed` configuration option for Indeed domain selection

### Changed

- Renamed `search_switzerland_jobs()` to `search_jobs()` for genericity
- Removed Switzerland-specific defaults (now uses generic defaults)
- Updated logger names from `switzerland_jobs` to `job_search`
- Simplified banner display

## [2.0.0] - 2025-12-23

### Added

- **Automated Scheduling**: Run job searches automatically at configurable intervals using APScheduler
- **Telegram Notifications**: Receive instant alerts when new relevant jobs are found
- **Unified Entry Point**: New `main.py` script that integrates scheduling and notifications
- **Report Generator**: Formatting utilities for notification messages
- **Docker Scheduler Profile**: New `docker-compose --profile scheduler` for continuous execution

### Changed

- Updated documentation with scheduling and notification setup guides
- Improved Docker configuration with service profiles

## [1.0.0] - 2025-12-21

### Added

- **Multi-Site Scraping**: Search LinkedIn, Indeed, Glassdoor, Google Jobs, and more
- **Parallel Execution**: Concurrent searches using ThreadPoolExecutor
- **SQLite Persistence**: Track jobs across runs with full details
- **Relevance Scoring**: Customizable keyword-based scoring system
- **Interactive Dashboard**: Streamlit UI for exploring and filtering results
- **Excel Export**: Formatted output with clickable links and conditional formatting
- **YAML Configuration**: Fully customizable settings without code changes
- **Retry Logic**: Exponential backoff with tenacity for rate limit handling
- **Structured Logging**: File and console logs with rotation
- **Docker Support**: Containerized environment for cross-platform compatibility

[Unreleased]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.2...HEAD
[6.0.2]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.1...v6.0.2
[6.0.1]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.0...v6.0.1
[6.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v5.0.1...v6.0.0
[5.0.1]: https://github.com/VincenzoImp/job-search-tool/compare/v5.0.0...v5.0.1
[5.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.4.0...v5.0.0
[4.4.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.3.2...v4.4.0
[4.3.2]: https://github.com/VincenzoImp/job-search-tool/compare/v4.3.1...v4.3.2
[4.3.1]: https://github.com/VincenzoImp/job-search-tool/compare/v4.3.0...v4.3.1
[4.3.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.2.1...v4.3.0
[4.2.1]: https://github.com/VincenzoImp/job-search-tool/compare/v4.2.0...v4.2.1
[4.2.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.1.1...v4.2.0
[4.1.1]: https://github.com/VincenzoImp/job-search-tool/compare/v4.1.0...v4.1.1
[4.1.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v3.1.0...v4.0.0
[3.1.0]: https://github.com/VincenzoImp/job-search-tool/compare/v3.0.2...v3.1.0
[3.0.2]: https://github.com/VincenzoImp/job-search-tool/compare/v3.0.1...v3.0.2
[3.0.1]: https://github.com/VincenzoImp/job-search-tool/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.5.4...v3.0.0
[2.5.4]: https://github.com/VincenzoImp/job-search-tool/compare/v2.5.3...v2.5.4
[2.5.3]: https://github.com/VincenzoImp/job-search-tool/compare/v2.5.2...v2.5.3
[2.5.2]: https://github.com/VincenzoImp/job-search-tool/compare/v2.5.1...v2.5.2
[2.5.1]: https://github.com/VincenzoImp/job-search-tool/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/VincenzoImp/job-search-tool/releases/tag/v1.0.0
