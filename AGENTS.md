# AGENTS.md - Developer Documentation

> **Purpose**: This document provides comprehensive technical documentation for developers working on the Job Search Tool codebase. It covers architecture, implementation details, API references, and development guidelines.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Module Reference](#module-reference)
- [Database Schema](#database-schema)
- [Configuration System](#configuration-system)
- [Execution Flow](#execution-flow)
- [Development Guide](#development-guide)
- [Testing](#testing)
- [Performance Optimization](#performance-optimization)
- [External Dependencies](#external-dependencies)
- [Changelog](#changelog)

---

## Project Overview

The Job Search Tool is an automated job aggregation platform built on the [JobSpy](https://github.com/speedyapply/JobSpy) library. It provides:

- **Multi-source scraping** from LinkedIn, Indeed, Glassdoor, and other job boards
- **Intelligent relevance scoring** with configurable keyword matching
- **Persistent storage** via SQLite for cross-run job tracking
- **Scheduled automation** using APScheduler
- **Real-time notifications** through Telegram
- **Interactive analysis** via Streamlit dashboard

### Design Philosophy

1. **Configuration-Driven**: All behavior is controlled via YAML configuration
2. **No Hardcoded Values**: Categories, keywords, and scoring are fully dynamic
3. **Separation of Concerns**: Each module has a single responsibility
4. **Type Safety**: Comprehensive type hints throughout the codebase
5. **Graceful Degradation**: Handles rate limits and failures without crashing

---

## Architecture

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.11+ | Core runtime (3.10+ required by JobSpy) |
| Scraping | JobSpy v1.1.82 | Multi-site job board aggregation |
| Data | Pandas 2.x | DataFrame manipulation and analysis |
| Database | SQLite 3 | Persistent job storage |
| Scheduling | APScheduler 3.x | Periodic task execution |
| Notifications | python-telegram-bot | Telegram message delivery |
| Dashboard | Streamlit | Interactive web UI |
| Configuration | PyYAML | Settings file parsing |
| Retry Logic | Tenacity | Exponential backoff |
| Fuzzy Matching | rapidfuzz | Post-filter validation |
| Excel Output | OpenPyXL | Formatted spreadsheet generation |
| Vector Search | ChromaDB | Semantic job similarity search |
| Embeddings | ChromaDB DefaultEmbeddingFunction | ONNX-based, bundles `all-MiniLM-L6-v2` (no torch) |

### Project Structure

```
job-search-tool/
├── config/
│   └── settings.example.yaml      # Bundled template (auto-scaffolded into data/config/ on first run)
│
├── docker/
│   └── entrypoint.sh              # First-run bootstrap + /data scaffolding (tini-init)
│
├── scripts/
│   ├── main.py                    # Scheduler loop (default) or --once single-shot
│   ├── search_jobs.py             # Core search engine
│   ├── scheduler.py               # APScheduler wrapper
│   ├── notifier.py                # Notification channels
│   ├── report_generator.py        # Report formatting
│   ├── analyze_jobs.py            # Analysis utilities
│   ├── dashboard.py               # Streamlit application
│   ├── config.py                  # Configuration loader
│   ├── database.py                # SQLite operations
│   ├── models.py                  # Data structures
│   ├── logger.py                  # Logging setup
│   ├── scoring.py                 # Relevance scoring engine
│   ├── exporter.py                # CSV/Excel export with formula injection protection
│   ├── vector_store.py            # ChromaDB vector store for semantic search
│   ├── vector_commands.py         # Vector store backfill and sync utilities
│   └── healthcheck.py             # Docker health verification
│
├── tests/
│   ├── conftest.py                # Pytest fixtures + global state reset
│   ├── test_models.py             # Model tests
│   ├── test_config.py             # Configuration tests
│   ├── test_database.py           # Database tests
│   ├── test_scoring.py            # Scoring calculation, fuzzy matching
│   ├── test_main.py               # Entry point tests
│   ├── test_notifier.py           # Notification tests
│   ├── test_scheduler.py          # Scheduler tests
│   ├── test_logger.py             # Logger tests
│   ├── test_exporter.py           # Export and sanitization tests
│   ├── test_healthcheck.py        # Health check tests
│   ├── test_report_generator.py   # Report generation tests
│   ├── test_analyze_jobs.py       # Analysis utility tests
│   ├── test_search_jobs.py        # Search engine tests
│   └── test_vector_store.py       # Vector store tests
│
├── .github/
│   └── workflows/
│       └── ci.yml                 # CI pipeline (test, audit, Docker)
│
├── data/                           # Local state root (gitignored)
│   ├── config/settings.yaml        # User configuration
│   ├── db/jobs.db                  # SQLite store
│   ├── chroma/                     # ChromaDB vector store
│   ├── results/                    # CSV/Excel exports
│   └── logs/search.log             # Rotating log
│
├── Dockerfile                      # Multi-stage, variant-aware build (core | dashboard), tini-init
├── docker-compose.yml              # Two-service stack sharing ./data:/data
├── docker-compose.dev.yml          # Local-build override (rebuilds both variants)
├── .pre-commit-config.yaml         # Pre-commit hooks (ruff, etc.)
├── requirements.txt                # Production dependencies (compat mirror)
├── requirements-dev.txt            # Development dependencies (compat mirror)
└── pytest.ini                      # Test configuration
```

---

## Core Components

### 1. Entry Point (`main.py`)

The unified entry point that orchestrates the entire application.

**Key Functions:**

```python
def run_job_search() -> bool:
    """
    Execute a single search iteration.

    Flow:
    1. Reload configuration (picks up any changes)
    2. Initialize database connection
    3. Cleanup old jobs (if enabled)
    4. Execute parallel search via search_jobs()
    5. Filter by relevance threshold
    6. Save to database
    7. Send notifications for new jobs

    Returns:
        True if successful, False on error.
    """

def main() -> int:
    """
    Application entry point.

    - Determines execution mode (single-shot vs scheduled)
    - Recalculates scores for existing jobs (once at startup)
    - Creates and starts scheduler

    Returns:
        Exit code (0 = success, 1 = failure).
    """
```

**Execution Modes:**

| Mode | Trigger | Behavior |
|------|---------|----------|
| Single-shot | `scheduler.enabled: false` | Runs once and exits |
| Scheduled | `scheduler.enabled: true` | Runs continuously at interval |

### 2. Search Engine (`search_jobs.py`)

The core search implementation with parallel execution and throttling.

**Key Classes:**

```python
class ThrottledExecutor:
    """
    ThreadPoolExecutor wrapper with rate limiting.

    Attributes:
        _delays: dict[str, float]  # Per-site delay configuration
        _jitter: float             # Random variation factor
        _locks: dict[str, Lock]    # Per-site thread locks

    Methods:
        throttled_search(query, location, site, config) -> DataFrame
    """
```

**Key Functions:**

```python
def search_jobs(config: Config) -> tuple[pd.DataFrame | None, SearchSummary]:
    """
    Execute parallel job search across all sites and locations.

    Features:
    - Parallel query execution via ThreadPoolExecutor
    - Per-site throttling with jitter
    - Incremental deduplication during collection
    - Retry logic with exponential backoff

    Returns:
        Tuple of (combined DataFrame, SearchSummary).
    """
```

> **Note:** `calculate_relevance_score` and `filter_relevant_jobs` have been extracted to `scoring.py`. `save_results` has been extracted to `exporter.py`.

### 2a. Scoring Engine (`scoring.py`)

Relevance scoring engine, extracted from `search_jobs.py`.

**Key Functions:**

```python
def calculate_relevance_score(row: pd.Series, config: Config) -> int:
    """
    Calculate job relevance score.

    Algorithm:
    1. Build searchable text: title + description + company + location
    2. For each category in config.scoring.keywords:
       - If ANY keyword matches (case-insensitive): add weight
    3. Return total score

    Args:
        row: DataFrame row with job data.
        config: Configuration with scoring settings.

    Returns:
        Integer score (can be negative if 'avoid' categories match).
    """

def filter_relevant_jobs(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """
    Filter jobs by relevance score threshold.

    Args:
        df: DataFrame with all jobs.
        config: Configuration with threshold.

    Returns:
        Filtered and sorted DataFrame.
    """
```

### 2b. Exporter (`exporter.py`)

CSV/Excel export with formula injection protection, extracted from `search_jobs.py`.

**Key Functions:**

```python
def save_results(df: pd.DataFrame, config: Config) -> None:
    """
    Save search results to CSV and/or Excel.

    Features:
    - Formula injection protection (sanitizes cell values)
    - Formatted Excel output via OpenPyXL
    - Configurable output directory
    """
```

### 3. Scheduler (`scheduler.py`)

APScheduler integration for automated periodic execution.

```python
class JobSearchScheduler:
    """
    Scheduler wrapper for job search automation.

    Attributes:
        _scheduler: BackgroundScheduler
        _search_func: Callable[[], bool]
        _config: SchedulerConfig

    Methods:
        start() -> None       # Begin scheduled execution
        run_once() -> bool    # Execute single search
        stop() -> None        # Graceful shutdown
    """
```

**Features:**

- Configurable interval (default: 24 hours)
- Optional immediate execution on startup
- Retry logic on failure with configurable delay and max retry limit
- Consecutive failure tracking (`_consecutive_failures` counter)
- Signal handling for graceful shutdown (SIGINT, SIGTERM)

### 4. Notification System (`notifier.py`)

Extensible notification framework with Telegram implementation.

**Class Hierarchy:**

```python
class BaseNotifier(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    async def send_notification(self, data: NotificationData) -> bool:
        """Send notification. Returns True on success."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if channel is properly configured."""

class TelegramNotifier(BaseNotifier):
    """
    Telegram notification implementation.

    Features:
    - MarkdownV2 formatting
    - Chunked messages (10 jobs per message)
    - URL escaping for special characters
    - Configurable minimum score threshold
    """

class NotificationManager:
    """
    Manages all configured notification channels.

    Methods:
        send_all(data) -> dict[str, bool]       # Async
        send_all_sync(data) -> dict[str, bool]  # Sync wrapper
    """
```

**Notification Data Structure:**

```python
@dataclass
class NotificationData:
    run_timestamp: datetime
    total_jobs_found: int
    new_jobs_count: int
    updated_jobs_count: int
    avg_score: float
    new_jobs: list[JobDBRecord]  # All new jobs, sorted by score descending
    top_jobs_overall: list[JobDBRecord]  # Top jobs from entire database
    total_jobs_in_db: int = 0  # Total number of jobs in database
```

**Telegram Notification Sections:**
- 🆕 **New Jobs** - Jobs found in the current search run (filtered by `min_score_for_notification`)
- 🏆 **Top Jobs Overall** - Best jobs from entire database (controlled by `include_top_overall` and `max_top_overall`)

### 5. Database Layer (`database.py`)

SQLite persistence with automatic migration support. Uses WAL journal mode
and `busy_timeout=5000` for improved concurrency. Maintains a persistent
connection (reused across calls) with context manager support (`with db:`).

```python
class JobDatabase:
    """
    SQLite database for job persistence.

    Methods:
        save_job(job, site, job_level, company_url) -> tuple[str, bool]
        save_jobs_from_dataframe(df) -> tuple[int, int]
        get_all_jobs() -> list[JobDBRecord]
        get_jobs_first_seen_today() -> list[JobDBRecord]
        get_new_job_ids(job_ids) -> set[str]
        filter_new_jobs(df) -> pd.DataFrame
        mark_as_applied(job_id) -> bool
        delete_job(job_id) -> bool
        delete_jobs(job_ids) -> int
        toggle_bookmark(job_id) -> bool
        get_job_by_id(job_id) -> JobDBRecord | None
        get_statistics() -> dict
        export_to_dataframe() -> pd.DataFrame
    """
```

**Utility Functions:**

```python
def recalculate_all_scores(db: JobDatabase, config: Config) -> int:
    """
    Recalculate relevance scores for all existing jobs.

    Called once at startup to apply current scoring criteria
    to historical data.

    Returns:
        Number of jobs updated.
    """

def cleanup_old_jobs(db: JobDatabase, days: int) -> int:
    """
    Delete jobs not seen in the specified number of days.

    Returns:
        Number of jobs deleted.
    """
```

### 6. Configuration System (`config.py`)

Type-safe configuration loading with validation.

**Dataclass Hierarchy:**

```python
@dataclass
class Config:
    search: SearchConfig
    queries: dict[str, list[str]]
    scoring: ScoringConfig
    parallel: ParallelConfig
    retry: RetryConfig
    throttling: ThrottlingConfig
    post_filter: PostFilterConfig
    logging: LoggingConfig
    database: DatabaseConfig
    output: OutputConfig
    profile: ProfileConfig
    scheduler: SchedulerConfig
    notifications: NotificationsConfig
    vector_search: VectorSearchConfig
```

**Key Functions:**

```python
def load_config() -> Config:
    """Load configuration from YAML with validation."""

def get_config() -> Config:
    """Get singleton configuration instance (thread-safe)."""

def reload_config() -> Config:
    """Force reload configuration from file."""
```

**Validation:**

All numeric parameters are validated:
- `max_workers >= 1`
- `max_attempts >= 1`
- `base_delay >= 0`
- `backoff_factor >= 1.0`
- `jitter` between 0 and 1.0
- `cleanup_days >= 1`
- `max_retries >= 0` (0 = unlimited)
- `description_format` must be `markdown`, `html`, or `plain`

**Cross-Section Validation (warnings):**
- Categories in `weights` without matching `keywords` (will never match)
- Categories in `keywords` without matching `weights` (will contribute 0)
- Hardcoded `bot_token` in config file (recommends env var)

### 7. Data Models (`models.py`)

Type-safe dataclasses for data structures.

```python
@dataclass(frozen=True)
class Job:
    """
    Single job listing.

    Properties:
        job_id: str  # SHA256 hash of title+company+location (64 chars)

    Methods:
        from_dict(data: dict) -> Job
        to_dict() -> dict
    """

@dataclass(frozen=True)
class JobDBRecord:
    """Database record with all columns."""
    # ...
    bookmarked: bool = False

@dataclass(frozen=True)
class SearchResult:
    """Results from a single query."""

@dataclass
class SearchSummary:
    """Statistics for complete search run."""
```

### 8. Vector Store (`vector_store.py`)

ChromaDB-based vector store for semantic job similarity search.

```python
class JobVectorStore:
    """
    Vector store for semantic job search using ChromaDB.

    Methods:
        embed_jobs(jobs: list[JobDBRecord]) -> int
        search_similar(query: str, n_results: int) -> list[JobDBRecord]
        delete_jobs(job_ids: list[str]) -> None
        get_collection_count() -> int
    """
```

### 9. Vector Commands (`vector_commands.py`)

Utilities for backfilling and syncing the vector store.

```python
def backfill_embeddings(db: JobDatabase, config: Config) -> int:
    """
    Backfill vector embeddings for all jobs in the database.

    Called once at startup when vector_search is enabled.

    Returns:
        Number of jobs embedded.
    """

def embed_new_jobs(jobs: list[JobDBRecord], config: Config) -> int:
    """
    Embed newly discovered jobs into the vector store.

    Called after each search iteration when vector_search is enabled.

    Returns:
        Number of jobs embedded.
    """
```

---

## Database Schema

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,           -- SHA256 hash (64 chars)
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    job_url TEXT,
    site TEXT,                          -- indeed, linkedin, glassdoor
    job_type TEXT,                      -- fulltime, contract, etc.
    is_remote BOOLEAN,
    job_level TEXT,                     -- entry, mid, senior
    description TEXT,
    date_posted DATE,
    min_amount REAL,                    -- Salary minimum
    max_amount REAL,                    -- Salary maximum
    currency TEXT,
    company_url TEXT,
    first_seen DATE NOT NULL,           -- When first discovered
    last_seen DATE NOT NULL,            -- Most recent occurrence
    relevance_score INTEGER DEFAULT 0,
    applied BOOLEAN DEFAULT FALSE,
    bookmarked BOOLEAN DEFAULT FALSE
)
```

**Update Logic (UPSERT):**

On conflict (same `job_id`):
- `last_seen` is always updated to current date
- `relevance_score` is updated only if new score is higher
- Other fields use `COALESCE` (keep existing if new is NULL)

**Automatic Migration:**

When the database is opened, missing columns are added via `ALTER TABLE`.

---

## Configuration System

### File Structure

```yaml
# Search parameters
search:
  results_wanted: 50
  hours_old: 168
  job_types: ["fulltime", "contract"]
  sites: ["indeed", "linkedin"]
  locations: ["San Francisco, CA"]
  distance: 50
  is_remote: false

# Query definitions (by category)
queries:
  category_name:
    - "query string"

# Scoring system
scoring:
  threshold: 15
  weights:
    category_name: 25
  keywords:
    category_name:
      - "keyword"

# Execution tuning
parallel:
  max_workers: 4

retry:
  max_attempts: 3
  base_delay: 2
  backoff_factor: 2

throttling:
  enabled: true
  default_delay: 1.5
  site_delays:
    linkedin: 3.0
  jitter: 0.3

# Scheduling
scheduler:
  enabled: true
  interval_hours: 24
  run_on_startup: true
  max_retries: 3          # Max consecutive retries (0 = unlimited)

# Notifications
notifications:
  enabled: true
  telegram:
    enabled: true
    bot_token: "..."
    chat_ids: ["..."]
    min_score_for_notification: 20
    max_jobs_in_message: 50
    jobs_per_chunk: 10
    include_top_overall: true  # Show top jobs from entire database
    max_top_overall: 10  # Max top jobs to show

# Database maintenance
database:
  cleanup_enabled: true
  cleanup_days: 30

# Output toggles (persistent paths are fixed under JOB_SEARCH_DATA_DIR)
output:
  save_csv: true
  save_excel: true

# Vector search (semantic similarity)
vector_search:
  enabled: true
  embed_on_save: true
  default_results: 20
  backfill_on_startup: true
  batch_size: 100
```

**Fixed path layout under `JOB_SEARCH_DATA_DIR`** (default `/data` in Docker,
repo root in local dev):

```
{DATA_DIR}/config/settings.yaml
{DATA_DIR}/db/jobs.db
{DATA_DIR}/chroma/
{DATA_DIR}/results/
{DATA_DIR}/logs/search.log
```

None of these paths are configurable through `settings.yaml`. Override the
root directory via the `JOB_SEARCH_DATA_DIR` environment variable to relocate
the whole tree.

### Dynamic Scoring

The scoring system is fully configuration-driven:

1. Category names in `weights` must match those in `keywords` (mismatches emit warnings)
2. Weights can be positive (bonus) or negative (penalty)
3. Unknown categories default to weight 0
4. All matching is case-insensitive with Unicode normalization (NFKD)

---

## Execution Flow

### Startup Sequence

```
main()
├── Load configuration
├── Setup logging
├── Get database connection
├── recalculate_all_scores()     # Once at startup
├── backfill_embeddings()       # Once at startup (if vector_search enabled)
├── Create scheduler
└── scheduler.start() or scheduler.run_once()
```

### Search Iteration

```
run_job_search()
├── Reload configuration
├── Get database connection
├── cleanup_old_jobs()           # Each iteration (if enabled)
├── search_jobs()
│   ├── Build query-location pairs
│   ├── Execute parallel searches (ThreadPoolExecutor)
│   ├── Apply per-site throttling
│   ├── Deduplicate results
│   └── Return combined DataFrame
├── filter_relevant_jobs()
│   ├── Calculate scores for all jobs
│   ├── Filter by threshold
│   └── Sort by score descending
├── save_results()               # CSV/Excel (if enabled)
├── db.save_jobs_from_dataframe()
├── embed_new_jobs()            # Vector store (if enabled)
└── _send_notifications()        # For new jobs only
```

---

## Development Guide

### Adding a Scoring Category

No code changes required:

```yaml
# config/settings.yaml
scoring:
  weights:
    new_category: 15
  keywords:
    new_category:
      - "keyword1"
      - "keyword2"
```

### Adding a Database Column

1. Update `CREATE_TABLE` in `database.py`
2. Add to `MIGRATE_COLUMNS` list
3. Update `INSERT_OR_UPDATE` query
4. Update `SELECT_ALL` and `SELECT_NEW` queries
5. Add field to `JobDBRecord` in `models.py`
6. Update `_row_to_record()` method
7. Update `export_to_dataframe()` method

### Adding a Notification Channel

1. Create class extending `BaseNotifier`:

```python
class SlackNotifier(BaseNotifier):
    def __init__(self, config: SlackConfig):
        self.config = config

    def is_configured(self) -> bool:
        return self.config.enabled and bool(self.config.webhook_url)

    async def send_notification(self, data: NotificationData) -> bool:
        # Implementation
        pass
```

2. Add configuration dataclass in `config.py`
3. Register in `NotificationManager._setup_notifiers()`

### Adding a Configuration Section

1. Create dataclass:

```python
@dataclass
class NewSectionConfig:
    param1: str = "default"
    param2: int = 10
```

2. Add parsing function:

```python
def _parse_new_section_config(data: dict) -> NewSectionConfig:
    section_data = data.get("new_section", {})
    # Validation...
    return NewSectionConfig(...)
```

3. Add to `Config` dataclass
4. Update `load_config()` to include parsing

---

## Testing

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures + global state reset (autouse)
├── test_models.py           # Job ID, dataclass conversions
├── test_config.py           # Configuration validation
├── test_database.py         # CRUD, deduplication, statistics
├── test_scoring.py          # Scoring calculation, fuzzy matching
├── test_main.py             # Entry point (run_job_search, main)
├── test_notifier.py         # Notification formatting, sending, chunking
├── test_scheduler.py        # Scheduler lifecycle, retry logic
├── test_logger.py           # Logger setup, formatting, colors
├── test_exporter.py         # Export and sanitization tests
├── test_healthcheck.py      # Health check tests
├── test_report_generator.py # Report generation tests
├── test_analyze_jobs.py     # Analysis utility tests
├── test_search_jobs.py      # Search engine tests
└── test_vector_store.py     # Vector store tests
```

### Running Tests

```bash
# Install dependencies
pip install -r requirements-dev.txt

# All tests
pytest

# With coverage
pytest --cov=scripts --cov-report=html

# Specific file
pytest tests/test_config.py -v

# Specific test
pytest tests/test_models.py::test_job_id_generation -v
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| models.py | 13 | Job ID, conversions |
| config.py | 32 | All validation, cross-section |
| database.py | 21 | CRUD, dedup, stats, top jobs |
| main.py | 7 | run_job_search, main, recalc |
| notifier.py | 22 | Formatting, sending, chunking |
| scheduler.py | 15 | Lifecycle, retry, signals |
| logger.py | 17 | Setup, formatting, colors |
| scoring | varies | Requires rapidfuzz |
| exporter.py | 14 | Export and sanitization |
| search_jobs.py | 20 | Search engine |
| healthcheck.py | 12 | Health check |
| report_generator.py | 16 | Report generation |
| analyze_jobs.py | 16 | Analysis utilities |
| vector_store.py | 34 | Vector store |

Total: **~324 tests**.

---

## Performance Optimization

### Parallel Execution

| Throttling | Workers | Est. Time (100 queries) | Rate Limit Risk |
|------------|---------|-------------------------|-----------------|
| Disabled | 5 | ~3 min | High |
| 1.5s delay | 5 | ~8 min | Moderate |
| 3.0s delay | 3 | ~15 min | Low |
| 3.0s delay | 1 | ~30 min | Minimal |

### Memory Optimization

- Incremental deduplication during collection
- No unnecessary DataFrame copies
- SQLite for persistent storage (not in-memory)

### Database Performance

- SHA256 job IDs for O(1) deduplication
- Batch inserts via `save_jobs_from_dataframe()`
- Persistent connection (reused across calls, auto-reconnect on error)
- WAL journal mode for concurrent read/write performance
- `busy_timeout=5000` to handle lock contention

---

## External Dependencies

### JobSpy Library

- **Repository**: https://github.com/speedyapply/JobSpy
- **Version**: 1.1.82+

**Key Behaviors:**

| Site | Rate Limiting | Jobs/Page | Notes |
|------|---------------|-----------|-------|
| Indeed | Minimal | 100 | Best coverage |
| LinkedIn | Aggressive | 25 | 3-7s built-in delays |
| Glassdoor | Moderate | 30 | GraphQL API |

**Indeed Filter Limitation:**

Indeed can only use ONE of:
- `hours_old` (date filtering)
- `job_type` + `is_remote`
- `easy_apply`

We prioritize `hours_old` for fresh results.

### DataFrame Schema (JobSpy Output)

```python
columns = [
    'id', 'site', 'job_url', 'job_url_direct', 'title', 'company',
    'location', 'date_posted', 'job_type', 'salary_source', 'interval',
    'min_amount', 'max_amount', 'currency', 'is_remote', 'job_level',
    'job_function', 'listing_type', 'emails', 'description',
    'company_industry', 'company_url', 'company_logo', 'company_url_direct',
    'company_addresses', 'company_num_employees', 'company_revenue',
    'company_description', 'skills', 'experience_range', 'company_rating',
    'company_reviews_count', 'vacancy_count', 'work_from_home_type',
]
```

---

## Changelog

### v6.0.0 (2026-04-15)

**Breaking (major UX simplification — "just run it"):**
- `docker-compose.yml` collapses to **two flat services** (`scheduler` on `:latest-core`, `dashboard` on `:latest`) sharing a single `./data:/data` volume. Removed anchors, profiles, `init-config`, `jobsearch`, `analyze` services. `docker compose up -d` starts the full stack.
- **Single `/data` volume** replaces the four-mount pattern. Fixed layout: `config/settings.yaml`, `db/jobs.db`, `chroma/`, `results/`, `logs/search.log`.
- **First-run auto-bootstrap**: the container scaffolds `settings.yaml` from the bundled template on first start if missing, then prints a one-line "edit me" hint. `scripts/bootstrap_config.py` and `init-config` service removed.
- **Scheduler is the default mode**: `python main.py` runs the APScheduler loop continuously. Use `python main.py --once` for single-shot CI/cron runs. `JOB_SEARCH_MODE` env var removed.
- **Fixed persistent paths**: `output.results_dir` / `output.data_dir` / `output.database_file` / `logging.file` / `vector_search.model_name` / `vector_search.persist_dir` are removed from `settings.yaml`. Override the whole tree with `JOB_SEARCH_DATA_DIR`.
- `config.Config` gains `data_dir`, `config_dir`, `logs_dir`, and a `log_path` that resolves against `DATA_DIR`. `data_path` is removed.
- `get_vector_store(persist_dir, model_name=...)` becomes `get_vector_store(persist_dir)` — the `model_name` was a no-op since v4.4.0.
- Dockerfile runs under `tini` for clean SIGTERM propagation, declares `VOLUME /data`, exports `JOB_SEARCH_DATA_DIR=/data`.
- `.env.example` slimmed to Telegram token, UID/GID, dashboard port.

### v5.0.0 (2026-04-15)

**Breaking:**
- Dockerfile split into two variants via `--build-arg VARIANT=core|dashboard` (default: `dashboard`). Single parameterized `runtime` stage resolves `builder-${VARIANT}` for the selected variant.
- Docker Hub publishes two tag families from the same repo: unsuffixed (dashboard, e.g. `:latest`, `:v5.0.0`) and `-core` suffixed (slim, e.g. `:latest-core`, `:v5.0.0-core`).
- `docker-compose.yml`: headless services (`jobsearch`, `scheduler`, `analyze`, `init-config`) default to the core image via `JOB_SEARCH_CORE_IMAGE`; the `dashboard` service uses `JOB_SEARCH_DASHBOARD_IMAGE`. The `JOB_SEARCH_IMAGE` var is removed.
- `dashboard` service no longer has a Compose profile — `docker compose up` starts jobsearch + dashboard by default.
- `streamlit` moved to `[project.optional-dependencies] dashboard` in `pyproject.toml` (also in the dev group so `test_dashboard.py` still runs locally).
- `.venv` is pruned in the builder stage (removes `__pycache__`, `*.pyc`, `*.pyo`, `*.pyi`, bundled `tests/`), saving ~50–100 MB on both variants.
- CI Docker smoke job now runs as a matrix over `[dashboard, core]` and healthchecks each built image.

### v4.4.0 (2026-04-15)

**Changed:**
- `JobVectorStore` now uses ChromaDB's built-in `DefaultEmbeddingFunction` (onnxruntime + bundled `all-MiniLM-L6-v2`) instead of `sentence-transformers`. Same embedding model, same search quality, no PyTorch runtime.
- Removed `torch`, `sentence-transformers`, `transformers` from runtime dependencies. The previous lock also pulled the full CUDA stack (`nvidia-cublas`, `cudnn`, `nccl`, `triton`, ...) despite `UV_TORCH_BACKEND=cpu` — all removed. Docker image shed ~2.5–3 GB.
- `Dockerfile`: removed the now-unused `UV_TORCH_BACKEND=cpu` build arg.

**Deprecated:**
- `vector_search.model_name` is now ignored — the store always uses the model bundled with ChromaDB's default embedder. A warning is logged if a non-default value is configured.

### v4.1.1 (2026-03-13)

**Fixes:**
- Dashboard port binding opened to all interfaces for broader network accessibility
- Logger file handler gracefully handles `PermissionError`, falling back to console-only logging instead of crashing
- Suppressed noisy JobSpy and ChromaDB third-party logs from console output
- Upstream library errors logged as single-line warnings instead of full tracebacks

### v4.1.0 (2026-03-13)

**Features:**
- Unapply functionality: `toggle_applied()` and `mark_as_unapplied()` in database API
- Dashboard: toggle apply/unapply per job card, bulk unapply button in DB management

**Fixes:**
- Streamlit server address changed to `0.0.0.0` inside Docker container for host accessibility
- Updated `settings.example.yaml` default location

### v4.0.0 (2026-03-13)

**Major Changes:**
- Codebase restructuring: extracted `scoring.py` and `exporter.py` from `search_jobs.py`
- Semantic vector search via ChromaDB + sentence-transformers (`vector_store.py`, `vector_commands.py`)
- Unified "Job Search Hub" dashboard (replaces old dashboard)
- Bookmark and delete job functionality in database layer
- Frozen dataclasses (`@dataclass(frozen=True)`) for `Job`, `JobDBRecord`, `SearchResult` immutability
- Formula injection protection in Excel exports

**Testing & CI:**
- 324 tests (was 160)
- CI coverage threshold raised to 60%
- Pre-commit hooks integrated into CI
- New test files: `test_exporter.py`, `test_search_jobs.py`, `test_healthcheck.py`, `test_report_generator.py`, `test_analyze_jobs.py`, `test_vector_store.py`

### v3.1.0 (2026-02-15)

**Security & Infrastructure:**
- Multi-stage Dockerfile with non-root user (`appuser`, UID 1000)
- GitHub Actions CI pipeline (test matrix Python 3.11/3.12, pip-audit, Docker build)
- Pre-commit hooks (ruff lint/format, trailing whitespace, detect-private-key)
- Removed `./scripts` volume mount from docker-compose (was overriding built image)
- Added `env_file: .env` (optional) to all docker-compose services

**Stability Fixes:**
- SQLite WAL mode + `busy_timeout=5000` for concurrent access
- Persistent database connection (reused across calls, auto-reconnect on error)
- Thread-safe deduplication (`append` inside lock in search_jobs.py)
- `filter_relevant_jobs` now works on a copy (no side-effect on input DataFrame)
- Unicode text normalization via `unicodedata.normalize("NFKD")` (replaces manual table)
- Null-safe formatting in Telegram notifications (title, relevance_score)
- Improved async/sync bridge using `new_event_loop()` in separate thread

**Configuration Validation:**
- Cross-section validation: warns on weight/keyword category mismatches
- `description_format` validated against `{markdown, html, plain}`
- Warning when bot_token is hardcoded in config file
- New `scheduler.max_retries` (default: 3, 0 = unlimited)

**Scheduler:**
- Consecutive failure counter (`_consecutive_failures`)
- Max retry limit (`max_retries`) stops retries after N consecutive failures

**Testing:**
- New `test_main.py` (7 tests for entry point)
- Config singleton reset fixture (`autouse`) in conftest.py
- Updated `.gitignore` with `.env`, `.ruff_cache/`, `docker-compose.override.yml`
- Total: 160 tests passing

### v3.0.2 (2026-01-12)

**Fixes:**
- Scheduler interval now calculated from run start to start (not end to start)
- Scheduler handles long-running jobs by skipping to next future slot
- Telegram notification chunks now sent independently (one failed chunk doesn't stop others)
- Fixed `next_run_time` attribute error with DateTrigger jobs

**Changes:**
- Replaced `IntervalTrigger` with `DateTrigger` for precise start-to-start scheduling
- Added `JOB_SEARCH_CONFIG` environment variable for config file override

### v3.0.1 (2026-01-01)

**Removed:**
- Docker memory limits from all services (compatibility issues with some Docker versions)

### v3.0.0 (2026-01-01)

**Features:**
- Top Jobs Overall in Telegram notifications (🆕 New Jobs + 🏆 Top Jobs Overall sections)
- New `include_top_overall` and `max_top_overall` Telegram config options
- New database methods: `get_top_jobs(limit, min_score)` and `get_job_count()`
- Configurable `jobs_per_chunk` (previously hardcoded)

**Fixes:**
- SQLite batch querying (`SQLITE_VAR_LIMIT = 500`) for large job ID sets
- Lock duration optimized in deduplication (compute outside lock)
- Scoring config mutation fixed (creates new dicts instead of mutating defaults)
- Logger levelname restored after color formatting
- Excel empty DataFrame check before save
- Environment variable warning for unresolved Telegram bot token

**Changes:**
- NotificationData enhanced with `top_jobs_overall` and `total_jobs_in_db` fields
- Precompiled regex for MarkdownV2 escaping (performance)
- Docker memory limits added to all services (reverted in v3.0.1)

**Removed:**
- Unused imports in scheduler.py, main.py, search_jobs.py

### v2.5.4 (2026-01-01)

**Features:**
- Database cleanup feature (`database.cleanup_enabled`, `database.cleanup_days`)
- Chunked Telegram messages (10 jobs per message) to avoid 4096 char limit

**Changes:**
- Score recalculation moved to startup only (not every iteration)
- Improved documentation with ASCII architecture diagrams

### v2.5.3 (2025-12-31)

**Features:**
- Score recalculation on startup for existing jobs
- `recalculate_all_scores()` function in database.py

### v2.5.2 (2025-12-31)

**Fixes:**
- Telegram MarkdownV2 URL escaping

### v2.5.1 (2025-12-31)

**Fixes:**
- Docker build: removed non-existent templates/ directory

### v2.5.0 (2025-12-31)

**Critical Fixes:**
- Missing `self.logger` in database.py
- Async/sync bridge in notifier.py
- Job ID hash increased to 64 characters

**Features:**
- Comprehensive input validation
- Health check script
- 60+ test suite

### v2.4.0 (2025-12-31)

**Breaking Changes:**
- Scoring system is now fully config-driven
- Removed all hardcoded keywords and categories

### v2.3.0 (2025-12-28)

**Fixes:**
- Scheduler retry calculation bug
- SQL error handling
- Thread safety improvements
- Race condition in deduplication

### v2.2.0 (2025-12-27)

**Features:**
- Fuzzy post-filtering with rapidfuzz
- Configurable throttling with jitter

### v2.1.0 (2025-12-27)

**Features:**
- Per-site throttling configuration
- `country_indeed` option

### v2.0.0 (2025-12-23)

**Features:**
- Automated scheduling with APScheduler
- Telegram notifications
- Unified entry point (main.py)

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

*Last Updated: 2026-04-15*
