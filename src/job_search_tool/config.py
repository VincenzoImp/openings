"""
Configuration loader for Job Search Tool.

Loads settings from YAML configuration file with fallback to defaults.
Provides type-safe access to all configuration values.
"""

from __future__ import annotations

import logging
import os
import random
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("job_search.config")


def _require_mapping(value: Any, section: str) -> dict[str, Any]:
    """Return a section mapping or raise a clear configuration error."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{section} must be a mapping")
    return value


def _get_section(data: dict[str, Any], section: str) -> dict[str, Any]:
    """Return a named config section as a mapping."""
    return _require_mapping(data.get(section, {}), section)


def _reject_unknown_keys(
    section: str,
    values: dict[str, Any],
    allowed: set[str],
) -> None:
    """Fail fast when settings.yaml contains unsupported keys."""
    unknown = sorted(set(values) - allowed)
    if unknown:
        key = f"{section}.{unknown[0]}" if section else unknown[0]
        raise ValueError(f"Unsupported configuration key: {key}")


def _validate_positive_int(value: int, name: str, default: int) -> int:
    """
    Validate that a value is a positive integer.

    Args:
        value: The value to validate.
        name: Parameter name for error messages.
        default: Default value (unused, but documents intent).

    Returns:
        The validated value.

    Raises:
        ValueError: If value is less than 1.
    """
    if value < 1:
        raise ValueError(f"{name} must be at least 1, got {value}")
    return value


# Repository root. Used for local-development defaults and bundled templates.
BASE_DIR = Path(__file__).resolve().parents[2]


def _resolve_data_dir() -> Path:
    """Resolve the persistent data directory.

    Precedence:
      1. ``JOB_SEARCH_DATA_DIR`` environment variable (set to ``/data`` inside the
         Docker image).
      2. Repository root, preserving the historical layout for local development.
    """
    env_dir = os.environ.get("JOB_SEARCH_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return BASE_DIR


# Root of all persistent state: config, database, vector store, results, logs.
# Every filesystem-facing path in this module is resolved relative to DATA_DIR.
DATA_DIR = _resolve_data_dir()

# User-editable configuration file. Env override is accepted for tests and advanced users.
CONFIG_FILE = Path(
    os.environ.get("JOB_SEARCH_CONFIG", DATA_DIR / "config" / "settings.yaml")
)


@dataclass
class SearchConfig:
    """Search-related configuration."""

    # Core search parameters
    results_wanted: int = 50
    hours_old: int = 720
    job_types: list[str] = field(default_factory=lambda: ["fulltime"])
    sites: list[str] = field(
        default_factory=lambda: ["indeed", "linkedin", "glassdoor"]
    )
    locations: list[str] = field(
        default_factory=lambda: [
            "Remote",
        ]
    )

    # JobSpy core parameters
    distance: int = 50  # Search radius in miles
    is_remote: bool = False  # Filter for remote-only jobs
    easy_apply: bool | None = None  # Filter for easy apply jobs
    offset: int = 0  # Start search from offset
    country_indeed: str = "USA"  # Country for Indeed domain (USA, UK, Germany, etc.)

    # Output format parameters
    enforce_annual_salary: bool = True  # Convert all salaries to yearly
    description_format: str = "markdown"  # markdown, html, or plain
    verbose: int = 1  # 0=errors, 1=warnings, 2=all logs

    # LinkedIn-specific parameters
    linkedin_fetch_description: bool = True  # Fetch full descriptions (slower)
    linkedin_company_ids: list[int] | None = None  # Filter by company IDs

    # Google Jobs-specific parameters
    google_search_term: str | None = None  # Special syntax for Google Jobs

    # Network/Proxy parameters
    proxies: list[str] | None = None  # Proxy list for rate limiting
    ca_cert: str | None = None  # CA certificate for proxies
    user_agent: str | None = None  # Custom user agent


@dataclass
class ScoringConfig:
    """Relevance scoring configuration.

    Two thresholds carve the DB score range into three zones:
      score < save_threshold            → dropped, never enters the DB
      save_threshold ≤ score < notify   → saved, visible in dashboard, no ping
      score ≥ notify_threshold          → saved AND triggers notifications

    ``notify_threshold`` must be ≥ ``save_threshold`` (enforced at load time).
    """

    save_threshold: int = 0
    notify_threshold: int = 20
    weights: dict[str, int] = field(
        default_factory=lambda: {
            "primary_skills": 20,
            "secondary_skills": 15,
            "technologies": 12,
            "seniority": 10,
            "company_type": 8,
            "remote": 5,
            "locations": 5,
        }
    )
    keywords: dict[str, list[str]] = field(
        default_factory=lambda: {
            "primary_skills": [
                "software engineer",
                "backend",
                "full-stack",
                "fullstack",
                "developer",
                "programmer",
            ],
            "secondary_skills": [
                "data",
                "cloud",
                "devops",
                "api",
                "microservices",
            ],
            "technologies": [
                "python",
                "javascript",
                "typescript",
                "react",
                "node.js",
                "nodejs",
                "postgresql",
                "docker",
                "kubernetes",
                "aws",
                "gcp",
                "azure",
            ],
            "seniority": [
                "senior",
                "staff",
                "lead",
                "principal",
                "architect",
            ],
            "company_type": [
                "startup",
                "tech",
                "fintech",
                "saas",
            ],
            "remote": [
                "remote",
                "work from home",
                "wfh",
                "distributed",
                "hybrid",
            ],
            "locations": [],  # User should customize in settings.yaml
        }
    )


@dataclass
class ParallelConfig:
    """Parallelism configuration."""

    max_workers: int = 3  # Conservative default to reduce rate limit risk


@dataclass
class RetryConfig:
    """Retry configuration for handling rate limits."""

    max_attempts: int = 3
    base_delay: float = 3.0  # More time between retries for rate limit recovery
    backoff_factor: float = 2.0


@dataclass
class ThrottlingConfig:
    """Throttling configuration for rate limit prevention."""

    enabled: bool = True
    default_delay: float = 2.0  # Safer default to prevent blocks
    site_delays: dict[str, float] = field(
        default_factory=lambda: {
            "linkedin": 4.0,  # LinkedIn is very aggressive with rate limiting
            "indeed": 1.5,
            "glassdoor": 2.0,
            "google": 2.5,
            "ziprecruiter": 2.0,
        }
    )
    jitter: float = 0.3
    rate_limit_cooldown: float = 60.0  # More time for rate limit recovery

    def get_delay(self, site: str) -> float:
        """Get delay for a specific site with jitter applied."""
        base_delay = self.site_delays.get(site.lower(), self.default_delay)
        if self.jitter > 0:
            jitter_amount = base_delay * self.jitter
            return base_delay + random.uniform(-jitter_amount, jitter_amount)
        return base_delay


@dataclass
class PostFilterConfig:
    """Post-filtering configuration for validating search results."""

    enabled: bool = True  # Enable fuzzy post-filtering
    min_similarity: int = 80  # Minimum similarity score (0-100) for fuzzy match
    check_query_terms: bool = True  # Verify all query terms are present in results
    check_location: bool = True  # Verify location matches configured locations


@dataclass
class LoggingConfig:
    """Logging configuration.

    The log file path is fixed at ``{DATA_DIR}/logs/search.log`` — use
    ``JOB_SEARCH_DATA_DIR`` to move it.
    """

    level: str = "INFO"
    max_size_mb: int = 10
    backup_count: int = 5
    timezone: str = (
        "UTC"  # Timezone for log timestamps (e.g., "Europe/Zurich", "America/New_York")
    )


@dataclass
class RetentionConfig:
    """Automatic retention rules applied at every boot via reconciliation.

    Bookmarked and applied jobs are always protected — this is hardcoded in
    the SQL layer, not configurable here.
    """

    max_age_days: int = 30
    purge_blacklist_after_days: int = 90


@dataclass
class DatabaseConfig:
    """Database configuration."""

    retention: RetentionConfig = field(default_factory=RetentionConfig)


@dataclass
class ProfileConfig:
    """User profile information for display."""

    name: str = "Your Name"
    current_position: str = "Current Role @ Company"
    visiting_position: str = ""
    research_focus: str = ""
    publication: str = ""
    grant: str = ""
    skills: str = "Python, JavaScript, React, PostgreSQL"
    target: str = "Senior Software Engineer, Tech Lead"


@dataclass
class VectorSearchConfig:
    """Vector search configuration for semantic job search.

    Storage lives at ``{DATA_DIR}/chroma``; the model is always ChromaDB's
    bundled ONNX embedder (``all-MiniLM-L6-v2``). No tunables are exposed for
    either — use ``JOB_SEARCH_DATA_DIR`` to relocate.
    """

    enabled: bool = True
    embed_on_save: bool = True
    default_results: int = 20
    backfill_on_startup: bool = True
    batch_size: int = 100
    # Cadence for the scheduler's periodic stale-embedding cleanup. The
    # scheduler process is the sole writer to the on-disk Chroma index (the
    # web process only reads it — see docs/architecture notes on vector
    # store ownership), so deletions made from the dashboard are cleaned up
    # here rather than immediately from the web process.
    sync_interval_minutes: int = 30


@dataclass
class SchedulerConfig:
    """Scheduler configuration for automated periodic execution.

    The operating mode (continuous scheduler vs single-shot) is chosen by the
    CLI subcommand in ``main.py`` (``scheduler`` / ``once``), so no ``enabled``
    toggle lives here — the knobs below only tune the continuous loop.
    """

    interval_hours: int = 24  # Run every N hours
    run_on_startup: bool = True  # Execute immediately on startup
    retry_on_failure: bool = True  # Retry if search fails
    retry_delay_minutes: int = 30  # Wait time before retry
    max_retries: int = 3  # Maximum consecutive retries before giving up (0 = unlimited)


@dataclass
class TelegramConfig:
    """Telegram notification configuration.

    The "which jobs to notify about" decision lives in ``scoring.notify_threshold``
    and is applied upstream, not here. This class only configures channel UX.
    """

    enabled: bool = False
    bot_token: str = ""  # From @BotFather
    chat_ids: list[str] = field(default_factory=list)  # Recipients
    send_summary: bool = True  # Send run summary
    max_jobs_in_message: int = 20
    jobs_per_chunk: int = 10  # Telegram has a 4096 char limit per message
    include_top_overall: bool = True
    max_top_overall: int = 10


@dataclass
class NotificationsConfig:
    """Notifications configuration."""

    enabled: bool = False
    telegram: TelegramConfig = field(default_factory=TelegramConfig)


@dataclass
class Config:
    """Main configuration class containing all settings."""

    search: SearchConfig = field(default_factory=SearchConfig)
    queries: dict[str, list[str]] = field(default_factory=dict)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    throttling: ThrottlingConfig = field(default_factory=ThrottlingConfig)
    post_filter: PostFilterConfig = field(default_factory=PostFilterConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)

    @property
    def data_dir(self) -> Path:
        """Root of all persistent state (alias of the module-level ``DATA_DIR``)."""
        return DATA_DIR

    @property
    def config_dir(self) -> Path:
        """Directory holding ``settings.yaml``."""
        return DATA_DIR / "config"

    @property
    def database_path(self) -> Path:
        """Absolute path to the SQLite database file."""
        return DATA_DIR / "db" / "jobs.db"

    @property
    def chroma_path(self) -> Path:
        """ChromaDB persistence directory."""
        return DATA_DIR / "chroma"

    @property
    def logs_dir(self) -> Path:
        """Directory where log files are written."""
        return DATA_DIR / "logs"

    @property
    def log_path(self) -> Path:
        """Absolute path to the main log file."""
        return self.logs_dir / "search.log"

    def get_all_queries(self) -> list[str]:
        """Get flattened list of all search queries."""
        all_queries = []
        for category_queries in self.queries.values():
            all_queries.extend(category_queries)
        return all_queries


def _load_yaml() -> dict[str, Any]:
    """Load YAML configuration file."""
    if not CONFIG_FILE.exists():
        return {}

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_VALID_DESCRIPTION_FORMATS = {"markdown", "html", "plain"}


def _validate_description_format(fmt: str) -> str:
    """Validate description_format value."""
    if fmt not in _VALID_DESCRIPTION_FORMATS:
        raise ValueError(
            f"description_format must be one of {_VALID_DESCRIPTION_FORMATS}, got '{fmt}'"
        )
    return fmt


def _parse_search_config(data: dict[str, Any]) -> SearchConfig:
    """Parse search configuration from dict with validation."""
    search_data = _get_section(data, "search")
    _reject_unknown_keys(
        "search",
        search_data,
        {
            "results_wanted",
            "hours_old",
            "job_types",
            "sites",
            "locations",
            "distance",
            "is_remote",
            "easy_apply",
            "offset",
            "country_indeed",
            "enforce_annual_salary",
            "description_format",
            "verbose",
            "linkedin_fetch_description",
            "linkedin_company_ids",
            "google_search_term",
            "proxies",
            "ca_cert",
            "user_agent",
        },
    )

    # Validate numeric values
    results_wanted = search_data.get("results_wanted", 50)
    if results_wanted <= 0:
        raise ValueError(f"results_wanted must be positive, got {results_wanted}")

    hours_old = search_data.get("hours_old", 720)
    if hours_old < 0:
        raise ValueError(f"hours_old cannot be negative, got {hours_old}")

    distance = search_data.get("distance", 50)
    if distance <= 0:
        raise ValueError(f"distance must be positive, got {distance}")

    offset = search_data.get("offset", 0)
    if offset < 0:
        raise ValueError(f"offset cannot be negative, got {offset}")

    verbose = search_data.get("verbose", 1)
    if verbose not in [0, 1, 2]:
        raise ValueError(f"verbose must be 0, 1, or 2, got {verbose}")

    return SearchConfig(
        # Core search parameters
        results_wanted=results_wanted,
        hours_old=hours_old,
        job_types=search_data.get("job_types", ["fulltime"]),
        sites=search_data.get("sites", ["indeed", "linkedin", "glassdoor"]),
        locations=search_data.get(
            "locations",
            ["Remote"],
        ),
        # JobSpy core parameters
        distance=distance,
        is_remote=search_data.get("is_remote", False),
        easy_apply=search_data.get("easy_apply"),
        offset=offset,
        country_indeed=search_data.get("country_indeed", "USA"),
        # Output format parameters
        enforce_annual_salary=search_data.get("enforce_annual_salary", True),
        description_format=_validate_description_format(
            search_data.get("description_format", "markdown")
        ),
        verbose=verbose,
        # LinkedIn-specific parameters
        linkedin_fetch_description=search_data.get("linkedin_fetch_description", True),
        linkedin_company_ids=search_data.get("linkedin_company_ids"),
        # Google Jobs-specific parameters
        google_search_term=search_data.get("google_search_term"),
        # Network/Proxy parameters
        proxies=search_data.get("proxies"),
        ca_cert=search_data.get("ca_cert"),
        user_agent=search_data.get("user_agent"),
    )


def _parse_scoring_config(data: dict[str, Any]) -> ScoringConfig:
    """Parse scoring configuration from dict."""
    scoring_data = _get_section(data, "scoring")
    _reject_unknown_keys(
        "scoring",
        scoring_data,
        {"save_threshold", "notify_threshold", "weights", "keywords"},
    )
    defaults = ScoringConfig()

    # Create new dicts by merging defaults with user config (no mutation)
    weights = {**defaults.weights}
    if "weights" in scoring_data:
        weights.update(scoring_data["weights"])

    keywords = {k: list(v) for k, v in defaults.keywords.items()}  # Deep copy
    if "keywords" in scoring_data:
        keywords.update(scoring_data["keywords"])

    save_threshold = int(scoring_data.get("save_threshold", defaults.save_threshold))
    notify_threshold = int(
        scoring_data.get("notify_threshold", defaults.notify_threshold)
    )

    return ScoringConfig(
        save_threshold=save_threshold,
        notify_threshold=notify_threshold,
        weights=weights,
        keywords=keywords,
    )


def _parse_parallel_config(data: dict[str, Any]) -> ParallelConfig:
    """Parse parallel configuration from dict with validation."""
    parallel_data = _get_section(data, "parallel")
    _reject_unknown_keys("parallel", parallel_data, {"max_workers"})

    max_workers = _validate_positive_int(
        parallel_data.get("max_workers", 3), "max_workers", 3
    )

    return ParallelConfig(
        max_workers=max_workers,
    )


def _parse_retry_config(data: dict[str, Any]) -> RetryConfig:
    """Parse retry configuration from dict with validation."""
    retry_data = _get_section(data, "retry")
    _reject_unknown_keys(
        "retry", retry_data, {"max_attempts", "base_delay", "backoff_factor"}
    )

    max_attempts = _validate_positive_int(
        retry_data.get("max_attempts", 3), "max_attempts", 3
    )

    base_delay = retry_data.get("base_delay", 3.0)
    if base_delay < 0:
        raise ValueError(f"base_delay cannot be negative, got {base_delay}")

    backoff_factor = retry_data.get("backoff_factor", 2.0)
    if backoff_factor < 1.0:
        raise ValueError(f"backoff_factor must be at least 1.0, got {backoff_factor}")

    return RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_factor=backoff_factor,
    )


def _parse_throttling_config(data: dict[str, Any]) -> ThrottlingConfig:
    """Parse throttling configuration from dict with validation."""
    throttling_data = _get_section(data, "throttling")
    _reject_unknown_keys(
        "throttling",
        throttling_data,
        {"enabled", "default_delay", "site_delays", "jitter", "rate_limit_cooldown"},
    )

    default_delay = throttling_data.get("default_delay", 2.0)
    if default_delay < 0:
        raise ValueError(f"default_delay cannot be negative, got {default_delay}")

    jitter = throttling_data.get("jitter", 0.3)
    if not 0 <= jitter <= 1.0:
        raise ValueError(f"jitter must be between 0 and 1.0, got {jitter}")

    rate_limit_cooldown = throttling_data.get("rate_limit_cooldown", 60.0)
    if rate_limit_cooldown < 0:
        raise ValueError(
            f"rate_limit_cooldown cannot be negative, got {rate_limit_cooldown}"
        )

    # Validate site_delays
    site_delays = throttling_data.get(
        "site_delays",
        {
            "linkedin": 4.0,
            "indeed": 1.5,
            "glassdoor": 2.0,
            "google": 2.5,
            "ziprecruiter": 2.0,
        },
    )
    for site, delay in site_delays.items():
        if delay < 0:
            raise ValueError(f"site_delays[{site}] cannot be negative, got {delay}")

    return ThrottlingConfig(
        enabled=throttling_data.get("enabled", True),
        default_delay=default_delay,
        site_delays=site_delays,
        jitter=jitter,
        rate_limit_cooldown=rate_limit_cooldown,
    )


def _parse_post_filter_config(data: dict[str, Any]) -> PostFilterConfig:
    """Parse post-filter configuration from dict with validation."""
    post_filter_data = _get_section(data, "post_filter")
    _reject_unknown_keys(
        "post_filter",
        post_filter_data,
        {"enabled", "min_similarity", "check_query_terms", "check_location"},
    )

    min_similarity = post_filter_data.get("min_similarity", 80)
    if not 0 <= min_similarity <= 100:
        raise ValueError(
            f"min_similarity must be between 0 and 100, got {min_similarity}"
        )

    return PostFilterConfig(
        enabled=post_filter_data.get("enabled", True),
        min_similarity=min_similarity,
        check_query_terms=post_filter_data.get("check_query_terms", True),
        check_location=post_filter_data.get("check_location", True),
    )


def _parse_logging_config(data: dict[str, Any]) -> LoggingConfig:
    """Parse logging configuration from dict with validation."""
    logging_data = _get_section(data, "logging")
    _reject_unknown_keys(
        "logging",
        logging_data,
        {"level", "max_size_mb", "backup_count", "timezone"},
    )

    max_size_mb = _validate_positive_int(
        logging_data.get("max_size_mb", 10), "max_size_mb", 10
    )

    backup_count = logging_data.get("backup_count", 5)
    if backup_count < 0:
        raise ValueError(f"backup_count cannot be negative, got {backup_count}")

    return LoggingConfig(
        level=logging_data.get("level", "INFO"),
        max_size_mb=max_size_mb,
        backup_count=backup_count,
        timezone=logging_data.get("timezone", "UTC"),
    )


def _parse_database_config(data: dict[str, Any]) -> DatabaseConfig:
    """Parse database configuration from dict with validation."""
    database_data = _get_section(data, "database")
    _reject_unknown_keys("database", database_data, {"retention"})

    retention_data = _require_mapping(
        database_data.get("retention", {}), "database.retention"
    )
    _reject_unknown_keys(
        "database.retention",
        retention_data,
        {"max_age_days", "purge_blacklist_after_days"},
    )
    max_age_days = _validate_positive_int(
        retention_data.get("max_age_days", 30), "retention.max_age_days", 30
    )
    purge_blacklist_after_days = _validate_positive_int(
        retention_data.get("purge_blacklist_after_days", 90),
        "retention.purge_blacklist_after_days",
        90,
    )

    return DatabaseConfig(
        retention=RetentionConfig(
            max_age_days=max_age_days,
            purge_blacklist_after_days=purge_blacklist_after_days,
        ),
    )


def _parse_profile_config(data: dict[str, Any]) -> ProfileConfig:
    """Parse profile configuration from dict."""
    profile_data = _get_section(data, "profile")
    _reject_unknown_keys(
        "profile",
        profile_data,
        {
            "name",
            "current_position",
            "visiting_position",
            "research_focus",
            "publication",
            "grant",
            "skills",
            "target",
        },
    )
    defaults = ProfileConfig()
    return ProfileConfig(
        name=profile_data.get("name", defaults.name),
        current_position=profile_data.get(
            "current_position", defaults.current_position
        ),
        visiting_position=profile_data.get(
            "visiting_position", defaults.visiting_position
        ),
        research_focus=profile_data.get("research_focus", defaults.research_focus),
        publication=profile_data.get("publication", defaults.publication),
        grant=profile_data.get("grant", defaults.grant),
        skills=profile_data.get("skills", defaults.skills),
        target=profile_data.get("target", defaults.target),
    )


def _parse_scheduler_config(data: dict[str, Any]) -> SchedulerConfig:
    """Parse scheduler configuration from dict with validation."""
    scheduler_data = _get_section(data, "scheduler")
    _reject_unknown_keys(
        "scheduler",
        scheduler_data,
        {
            "interval_hours",
            "run_on_startup",
            "retry_on_failure",
            "retry_delay_minutes",
            "max_retries",
        },
    )

    interval_hours = _validate_positive_int(
        scheduler_data.get("interval_hours", 24), "interval_hours", 24
    )

    retry_delay_minutes = scheduler_data.get("retry_delay_minutes", 30)
    if retry_delay_minutes < 0:
        raise ValueError(
            f"retry_delay_minutes cannot be negative, got {retry_delay_minutes}"
        )

    max_retries = scheduler_data.get("max_retries", 3)
    if max_retries < 0:
        raise ValueError(f"max_retries cannot be negative, got {max_retries}")

    return SchedulerConfig(
        interval_hours=interval_hours,
        run_on_startup=scheduler_data.get("run_on_startup", True),
        retry_on_failure=scheduler_data.get("retry_on_failure", True),
        retry_delay_minutes=retry_delay_minutes,
        max_retries=max_retries,
    )


def _parse_telegram_config(data: dict[str, Any]) -> TelegramConfig:
    """Parse Telegram configuration from dict with validation.

    Bot token can be specified in three ways (in order of precedence):
    1. Environment variable TELEGRAM_BOT_TOKEN
    2. Config value starting with $ to reference an env var (e.g., "$MY_TOKEN")
    3. Direct value in config file (not recommended for production)
    """
    telegram_data = _require_mapping(data.get("telegram", {}), "notifications.telegram")
    _reject_unknown_keys(
        "notifications.telegram",
        telegram_data,
        {
            "enabled",
            "bot_token",
            "chat_ids",
            "send_summary",
            "max_jobs_in_message",
            "jobs_per_chunk",
            "include_top_overall",
            "max_top_overall",
        },
    )

    max_jobs = _validate_positive_int(
        telegram_data.get("max_jobs_in_message", 20), "max_jobs_in_message", 20
    )

    jobs_per_chunk = _validate_positive_int(
        telegram_data.get("jobs_per_chunk", 10), "jobs_per_chunk", 10
    )
    if jobs_per_chunk > 15:
        raise ValueError(
            f"jobs_per_chunk must be at most 15 (Telegram 4096 char limit), got {jobs_per_chunk}"
        )

    max_top_overall = _validate_positive_int(
        telegram_data.get("max_top_overall", 10), "max_top_overall", 10
    )

    # Validate chat_ids format
    chat_ids = telegram_data.get("chat_ids", [])
    validated_chat_ids = []
    for chat_id in chat_ids:
        if chat_id:  # Skip empty values
            # Ensure it's a string (can be numeric string or with - prefix for groups)
            str_id = str(chat_id).strip()
            if str_id:
                validated_chat_ids.append(str_id)

    # Resolve bot_token with environment variable support
    bot_token = telegram_data.get("bot_token", "")

    # Priority 1: Check TELEGRAM_BOT_TOKEN env var
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if env_token:
        bot_token = env_token
    # Priority 2: If config value starts with $, resolve as env var
    elif bot_token.startswith("$"):
        env_var_name = bot_token.lstrip("$").strip("{}")
        resolved_token = os.environ.get(env_var_name, "")
        if not resolved_token:
            logger.warning(
                f"Environment variable '{env_var_name}' is not set. "
                "Telegram notifications will be disabled."
            )
        bot_token = resolved_token

    # Fail-fast: if Telegram is enabled but bot_token is empty, raise an error
    telegram_enabled = telegram_data.get("enabled", False)
    if telegram_enabled and not bot_token:
        raise ValueError(
            "Telegram notifications are enabled but bot_token is empty. "
            "Set the TELEGRAM_BOT_TOKEN environment variable or configure "
            "bot_token in settings.yaml."
        )

    return TelegramConfig(
        enabled=telegram_enabled,
        bot_token=bot_token,
        chat_ids=validated_chat_ids,
        send_summary=telegram_data.get("send_summary", True),
        max_jobs_in_message=max_jobs,
        jobs_per_chunk=jobs_per_chunk,
        include_top_overall=telegram_data.get("include_top_overall", True),
        max_top_overall=max_top_overall,
    )


def _parse_notifications_config(data: dict[str, Any]) -> NotificationsConfig:
    """Parse notifications configuration from dict."""
    notifications_data = _get_section(data, "notifications")
    _reject_unknown_keys("notifications", notifications_data, {"enabled", "telegram"})
    return NotificationsConfig(
        enabled=notifications_data.get("enabled", False),
        telegram=_parse_telegram_config(notifications_data),
    )


def _parse_vector_search_config(data: dict[str, Any]) -> VectorSearchConfig:
    """Parse vector search configuration from dict with validation."""
    vector_data = _get_section(data, "vector_search")
    _reject_unknown_keys(
        "vector_search",
        vector_data,
        {
            "enabled",
            "embed_on_save",
            "default_results",
            "backfill_on_startup",
            "batch_size",
            "sync_interval_minutes",
        },
    )

    default_results = _validate_positive_int(
        vector_data.get("default_results", 20), "default_results", 20
    )

    batch_size = _validate_positive_int(
        vector_data.get("batch_size", 100), "batch_size", 100
    )

    sync_interval_minutes = _validate_positive_int(
        vector_data.get("sync_interval_minutes", 30), "sync_interval_minutes", 30
    )

    return VectorSearchConfig(
        enabled=vector_data.get("enabled", True),
        embed_on_save=vector_data.get("embed_on_save", True),
        default_results=default_results,
        backfill_on_startup=vector_data.get("backfill_on_startup", True),
        batch_size=batch_size,
        sync_interval_minutes=sync_interval_minutes,
    )


def _parse_queries(data: dict[str, Any]) -> dict[str, list[str]]:
    """Parse search queries from dict.

    If no queries are provided in the configuration, returns generic defaults
    suitable for typical software engineering job searches.
    """
    queries_data = _get_section(data, "queries")
    if not queries_data:
        # Generic default queries for software engineering roles
        return {
            "software_engineering": [
                "software engineer",
                "backend engineer",
                "frontend developer",
                "full-stack developer",
                "software developer",
            ],
            "devops": [
                "devops engineer",
                "site reliability engineer",
                "cloud engineer",
                "platform engineer",
                "infrastructure engineer",
            ],
            "data": [
                "data engineer",
                "data scientist",
                "data analyst",
                "machine learning engineer",
            ],
            "technologies": [
                "Python developer",
                "JavaScript developer",
                "React developer",
                "Node.js developer",
            ],
            "senior": [
                "senior software engineer",
                "staff engineer",
                "tech lead",
            ],
            "entry_level": [
                "junior developer",
                "software engineer intern",
                "new grad software engineer",
            ],
        }
    return queries_data


def load_config() -> Config:
    """
    Load configuration from YAML file with fallback to defaults.

    Returns:
        Config object with all settings.
    """
    data = _require_mapping(_load_yaml(), "settings")
    _reject_unknown_keys(
        "",
        data,
        {
            "search",
            "queries",
            "scoring",
            "parallel",
            "retry",
            "throttling",
            "post_filter",
            "logging",
            "database",
            "profile",
            "scheduler",
            "notifications",
            "vector_search",
        },
    )

    config = Config(
        search=_parse_search_config(data),
        queries=_parse_queries(data),
        scoring=_parse_scoring_config(data),
        parallel=_parse_parallel_config(data),
        retry=_parse_retry_config(data),
        throttling=_parse_throttling_config(data),
        post_filter=_parse_post_filter_config(data),
        logging=_parse_logging_config(data),
        database=_parse_database_config(data),
        profile=_parse_profile_config(data),
        scheduler=_parse_scheduler_config(data),
        notifications=_parse_notifications_config(data),
        vector_search=_parse_vector_search_config(data),
    )

    # Cross-section validation: notify_threshold must be >= save_threshold
    if config.scoring.notify_threshold < config.scoring.save_threshold:
        raise ValueError(
            f"scoring.notify_threshold ({config.scoring.notify_threshold}) must be "
            f">= scoring.save_threshold ({config.scoring.save_threshold}): "
            "notifying about jobs that aren't saved is nonsensical."
        )

    # Cross-section validation: scoring weights vs keywords
    weight_keys = set(config.scoring.weights.keys())
    keyword_keys = set(config.scoring.keywords.keys())
    weights_without_keywords = weight_keys - keyword_keys
    keywords_without_weights = keyword_keys - weight_keys
    if weights_without_keywords:
        logger.warning(
            f"Scoring categories have weights but no keywords: {weights_without_keywords}. "
            "These categories will never match."
        )
    if keywords_without_weights:
        logger.warning(
            f"Scoring categories have keywords but no weights: {keywords_without_weights}. "
            "These categories will match but contribute 0 to the score."
        )

    # Warn if bot_token appears to be a raw token in the config file
    telegram = config.notifications.telegram
    if (
        telegram.enabled
        and telegram.bot_token
        and not telegram.bot_token.startswith("$")
        and not os.environ.get("TELEGRAM_BOT_TOKEN")
    ):
        # Check if the token looks like a real Telegram bot token (digits:alphanumeric)
        if re.match(r"^\d+:[A-Za-z0-9_-]+$", telegram.bot_token):
            logger.warning(
                "Telegram bot_token appears to be hardcoded in config file. "
                "Consider using environment variable TELEGRAM_BOT_TOKEN or $VAR_NAME syntax."
            )

    # Ensure persistent directories exist under DATA_DIR. The results/ tree
    # is created on-demand when the dashboard exports, not here.
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    config.chroma_path.mkdir(parents=True, exist_ok=True)
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    return config


# Singleton instance for easy access with thread-safe locking
_config: Config | None = None
_config_lock = threading.Lock()


def get_config() -> Config:
    """
    Get configuration singleton (thread-safe).

    Returns:
        Config object with all settings.
    """
    global _config
    if _config is None:
        with _config_lock:
            # Double-check pattern to avoid multiple loads
            if _config is None:
                _config = load_config()
    return _config


def reload_config() -> Config:
    """
    Force reload configuration from file (thread-safe).

    Returns:
        Fresh Config object.
    """
    global _config
    with _config_lock:
        _config = load_config()
    return _config
