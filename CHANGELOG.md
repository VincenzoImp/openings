# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[2.5.1]: https://github.com/VincenzoImp/job-search-tool/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/VincenzoImp/job-search-tool/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/VincenzoImp/job-search-tool/releases/tag/v1.0.0
