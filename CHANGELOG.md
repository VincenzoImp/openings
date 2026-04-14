# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
