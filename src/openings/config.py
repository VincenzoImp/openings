"""Configuration for Openings.

One YAML file owns intake and scoring. The loader is strict: an unknown key
anywhere in the file fails startup, so configuration drift is visible instead
of silently ignored. Secrets accept ``$ENV_VAR`` indirection.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

logger = logging.getLogger("openings.config")

# Repository root, used for local-development defaults.
BASE_DIR = Path(__file__).resolve().parents[2]

KNOWN_ATS = ("greenhouse", "lever", "ashby", "smartrecruiters")


def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("OPENINGS_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return BASE_DIR


DATA_DIR = _resolve_data_dir()
CONFIG_FILE = Path(os.environ.get("OPENINGS_CONFIG", DATA_DIR / "config" / "settings.yaml"))


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


class ConfigError(ValueError):
    """Raised for any invalid configuration."""


def _section(data: dict[str, Any], name: str, allowed: set[str], *, path: str = "") -> dict:
    """Return a mapping section, rejecting unknown keys."""
    value = data.get(name)
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError(f"{path or name} must be a mapping")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"Unsupported configuration key: {path or name}.{unknown[0]}")
    return value


def _int_min(value: Any, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer, got {value!r}")
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    return value


def _float_min(value: Any, name: str, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number, got {value!r}")
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    return float(value)


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false, got {value!r}")
    return value


def _str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string, got {value!r}")
    return value


def _str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{name} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def _secret(value: Any, name: str) -> str:
    """Resolve ``$ENV_VAR`` indirection for a secret-bearing string."""
    text = _str(value, name)
    if text.startswith("$"):
        return os.environ.get(text[1:], "")
    return text


def _optional(value: Any, cast, name: str):
    return None if value is None else cast(value, name)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


@dataclass
class ProfileConfig:
    """Informational only: shown in the banner and the dashboard."""

    name: str = ""
    headline: str = ""
    target: str = ""


@dataclass
class ThrottlingConfig:
    enabled: bool = True
    default_delay: float = 2.0
    site_delays: dict[str, float] = field(default_factory=dict)
    jitter: float = 0.3
    rate_limit_cooldown: float = 60.0


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 3.0
    backoff_factor: float = 2.0


@dataclass
class ParallelConfig:
    max_workers: int = 3


@dataclass
class PostFilterConfig:
    enabled: bool = True
    min_similarity: int = 80
    check_query_terms: bool = True
    check_location: bool = True


@dataclass
class JobSpyConfig:
    """Board scraping through the JobSpy library."""

    enabled: bool = True
    sites: list[str] = field(default_factory=lambda: ["linkedin"])
    locations: list[str] = field(default_factory=lambda: ["Remote"])
    queries: dict[str, list[str]] = field(default_factory=dict)
    job_types: list[str] = field(default_factory=lambda: ["fulltime"])
    hours_old: int = 72
    results_wanted: int = 50
    distance: int = 50
    is_remote: bool = False
    easy_apply: bool | None = None
    offset: int = 0
    country_indeed: str = "USA"
    enforce_annual_salary: bool = True
    description_format: str = "markdown"
    verbose: int = 1
    linkedin_fetch_description: bool = True
    linkedin_company_ids: list[int] | None = None
    google_search_term: str | None = None
    proxies: list[str] | None = None
    ca_cert: str | None = None
    throttling: ThrottlingConfig = field(default_factory=ThrottlingConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    post_filter: PostFilterConfig = field(default_factory=PostFilterConfig)

    @property
    def all_queries(self) -> list[str]:
        """Every query across categories, deduplicated, in file order."""
        seen: dict[str, None] = {}
        for terms in self.queries.values():
            for term in terms:
                seen.setdefault(term, None)
        return list(seen)


@dataclass
class CompanySourceConfig:
    """A named employer whose ATS exposes a public postings feed."""

    name: str
    ats: str
    slug: str
    locations: list[str] = field(default_factory=list)


@dataclass
class FeedSourceConfig:
    """An RSS or Atom feed of postings."""

    name: str
    url: str
    locations: list[str] = field(default_factory=list)


@dataclass
class AdzunaConfig:
    enabled: bool = False
    country: str = ""
    queries: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    app_id: str = ""
    app_key: str = ""
    results_per_page: int = 50
    max_pages: int = 2
    max_days_old: int = 7


@dataclass
class SourcesConfig:
    jobspy: JobSpyConfig = field(default_factory=JobSpyConfig)
    companies: list[CompanySourceConfig] = field(default_factory=list)
    feeds: list[FeedSourceConfig] = field(default_factory=list)
    adzuna: AdzunaConfig = field(default_factory=AdzunaConfig)
    user_agent: str | None = None
    timeout_seconds: float = 30.0


@dataclass
class ScoringConfig:
    save_threshold: int = 0
    notify_threshold: int = 20
    weights: dict[str, int] = field(default_factory=dict)
    keywords: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SchedulerConfig:
    interval_hours: int = 12
    run_on_startup: bool = True
    retry_on_failure: bool = True
    retry_delay_minutes: int = 30
    max_retries: int = 3


@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_ids: list[str] = field(default_factory=list)
    send_summary: bool = True
    max_jobs: int = 20
    jobs_per_chunk: int = 10


@dataclass
class NotificationsConfig:
    enabled: bool = False
    telegram: TelegramConfig = field(default_factory=TelegramConfig)


@dataclass
class RetentionConfig:
    max_age_days: int = 30
    purge_blacklist_after_days: int = 90


@dataclass
class AttachmentsConfig:
    max_size_mb: int = 20


@dataclass
class VectorSearchConfig:
    enabled: bool = True
    embed_on_save: bool = True
    default_results: int = 20
    backfill_on_startup: bool = True
    batch_size: int = 100
    sync_interval_minutes: int = 30


@dataclass
class LoggingConfig:
    level: str = "INFO"
    max_size_mb: int = 10
    backup_count: int = 5
    timezone: str = "UTC"


@dataclass
class Config:
    """Everything the YAML file configures, plus derived filesystem paths."""

    profile: ProfileConfig = field(default_factory=ProfileConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    attachments: AttachmentsConfig = field(default_factory=AttachmentsConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    data_dir: Path = field(default_factory=lambda: DATA_DIR)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "db" / "openings.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "openings.log"

    @property
    def attachments_dir(self) -> Path:
        return self.data_dir / "attachments"


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_profile(data: dict) -> ProfileConfig:
    section = _section(data, "profile", {"name", "headline", "target"})
    return ProfileConfig(
        name=_str(section.get("name", ""), "profile.name"),
        headline=_str(section.get("headline", ""), "profile.headline"),
        target=_str(section.get("target", ""), "profile.target"),
    )


def _parse_throttling(data: dict) -> ThrottlingConfig:
    section = _section(
        data,
        "throttling",
        {"enabled", "default_delay", "site_delays", "jitter", "rate_limit_cooldown"},
        path="sources.jobspy.throttling",
    )
    raw_delays = section.get("site_delays") or {}
    if not isinstance(raw_delays, dict):
        raise ConfigError("sources.jobspy.throttling.site_delays must be a mapping")
    site_delays = {
        str(site).lower(): _float_min(delay, f"site_delays.{site}", 0.0)
        for site, delay in raw_delays.items()
    }
    jitter = _float_min(section.get("jitter", 0.3), "throttling.jitter", 0.0)
    if jitter > 1.0:
        raise ConfigError("throttling.jitter must be between 0.0 and 1.0")
    return ThrottlingConfig(
        enabled=_bool(section.get("enabled", True), "throttling.enabled"),
        default_delay=_float_min(
            section.get("default_delay", 2.0), "throttling.default_delay", 0.0
        ),
        site_delays=site_delays,
        jitter=jitter,
        rate_limit_cooldown=_float_min(
            section.get("rate_limit_cooldown", 60.0),
            "throttling.rate_limit_cooldown",
            0.0,
        ),
    )


def _parse_retry(data: dict) -> RetryConfig:
    section = _section(
        data,
        "retry",
        {"max_attempts", "base_delay", "backoff_factor"},
        path="sources.jobspy.retry",
    )
    return RetryConfig(
        max_attempts=_int_min(section.get("max_attempts", 3), "retry.max_attempts", 1),
        base_delay=_float_min(section.get("base_delay", 3.0), "retry.base_delay", 0.0),
        backoff_factor=_float_min(section.get("backoff_factor", 2.0), "retry.backoff_factor", 1.0),
    )


def _parse_parallel(data: dict) -> ParallelConfig:
    section = _section(data, "parallel", {"max_workers"}, path="sources.jobspy.parallel")
    return ParallelConfig(
        max_workers=_int_min(section.get("max_workers", 3), "parallel.max_workers", 1)
    )


def _parse_post_filter(data: dict) -> PostFilterConfig:
    section = _section(
        data,
        "post_filter",
        {"enabled", "min_similarity", "check_query_terms", "check_location"},
        path="sources.jobspy.post_filter",
    )
    similarity = _int_min(section.get("min_similarity", 80), "post_filter.min_similarity", 0)
    if similarity > 100:
        raise ConfigError("post_filter.min_similarity must be between 0 and 100")
    return PostFilterConfig(
        enabled=_bool(section.get("enabled", True), "post_filter.enabled"),
        min_similarity=similarity,
        check_query_terms=_bool(
            section.get("check_query_terms", True), "post_filter.check_query_terms"
        ),
        check_location=_bool(section.get("check_location", True), "post_filter.check_location"),
    )


def _parse_queries(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("sources.jobspy.queries must be a mapping of category to list")
    queries: dict[str, list[str]] = {}
    for category, terms in value.items():
        queries[str(category)] = _str_list(terms, f"sources.jobspy.queries.{category}")
    return queries


def _parse_jobspy(data: dict) -> JobSpyConfig:
    allowed = {
        "enabled",
        "sites",
        "locations",
        "queries",
        "job_types",
        "hours_old",
        "results_wanted",
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
        "throttling",
        "retry",
        "parallel",
        "post_filter",
    }
    section = _section(data, "jobspy", allowed, path="sources.jobspy")
    description_format = _str(
        section.get("description_format", "markdown"), "sources.jobspy.description_format"
    )
    if description_format not in {"markdown", "html", "plain"}:
        raise ConfigError("sources.jobspy.description_format must be markdown, html or plain")
    company_ids = section.get("linkedin_company_ids")
    if company_ids is not None:
        if not isinstance(company_ids, list) or not all(
            isinstance(item, int) for item in company_ids
        ):
            raise ConfigError("sources.jobspy.linkedin_company_ids must be a list of integers")
    verbose = _int_min(section.get("verbose", 1), "sources.jobspy.verbose", 0)
    if verbose > 2:
        raise ConfigError("sources.jobspy.verbose must be 0, 1 or 2")
    return JobSpyConfig(
        enabled=_bool(section.get("enabled", True), "sources.jobspy.enabled"),
        sites=[
            site.lower()
            for site in _str_list(section.get("sites", ["linkedin"]), "sources.jobspy.sites")
        ],
        locations=_str_list(section.get("locations", ["Remote"]), "sources.jobspy.locations"),
        queries=_parse_queries(section.get("queries")),
        job_types=_str_list(section.get("job_types", ["fulltime"]), "sources.jobspy.job_types"),
        hours_old=_int_min(section.get("hours_old", 72), "sources.jobspy.hours_old", 1),
        results_wanted=_int_min(
            section.get("results_wanted", 50), "sources.jobspy.results_wanted", 1
        ),
        distance=_int_min(section.get("distance", 50), "sources.jobspy.distance", 0),
        is_remote=_bool(section.get("is_remote", False), "sources.jobspy.is_remote"),
        easy_apply=_optional(section.get("easy_apply"), _bool, "sources.jobspy.easy_apply"),
        offset=_int_min(section.get("offset", 0), "sources.jobspy.offset", 0),
        country_indeed=_str(section.get("country_indeed", "USA"), "sources.jobspy.country_indeed"),
        enforce_annual_salary=_bool(
            section.get("enforce_annual_salary", True), "sources.jobspy.enforce_annual_salary"
        ),
        description_format=description_format,
        verbose=verbose,
        linkedin_fetch_description=_bool(
            section.get("linkedin_fetch_description", True),
            "sources.jobspy.linkedin_fetch_description",
        ),
        linkedin_company_ids=company_ids,
        google_search_term=_optional(
            section.get("google_search_term"), _str, "sources.jobspy.google_search_term"
        ),
        proxies=(
            None
            if section.get("proxies") is None
            else _str_list(section.get("proxies"), "sources.jobspy.proxies")
        ),
        ca_cert=_optional(section.get("ca_cert"), _str, "sources.jobspy.ca_cert"),
        throttling=_parse_throttling(section),
        retry=_parse_retry(section),
        parallel=_parse_parallel(section),
        post_filter=_parse_post_filter(section),
    )


def _parse_companies(value: Any) -> list[CompanySourceConfig]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("sources.companies must be a list")
    companies: list[CompanySourceConfig] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(value):
        path = f"sources.companies[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{path} must be a mapping")
        unknown = sorted(set(item) - {"name", "ats", "slug", "locations"})
        if unknown:
            raise ConfigError(f"Unsupported configuration key: {path}.{unknown[0]}")
        for required in ("name", "ats", "slug"):
            if not item.get(required):
                raise ConfigError(f"{path}.{required} is required")
        ats = _str(item["ats"], f"{path}.ats").lower()
        if ats not in KNOWN_ATS:
            raise ConfigError(f"{path}.ats must be one of {', '.join(KNOWN_ATS)}, got {ats!r}")
        slug = _str(item["slug"], f"{path}.slug").strip()
        key = (ats, slug.lower())
        if key in seen:
            raise ConfigError(f"{path} duplicates an earlier company ({ats}:{slug})")
        seen.add(key)
        companies.append(
            CompanySourceConfig(
                name=_str(item["name"], f"{path}.name").strip(),
                ats=ats,
                slug=slug,
                locations=_str_list(item.get("locations"), f"{path}.locations"),
            )
        )
    return companies


def _parse_feeds(value: Any) -> list[FeedSourceConfig]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("sources.feeds must be a list")
    feeds: list[FeedSourceConfig] = []
    for index, item in enumerate(value):
        path = f"sources.feeds[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{path} must be a mapping")
        unknown = sorted(set(item) - {"name", "url", "locations"})
        if unknown:
            raise ConfigError(f"Unsupported configuration key: {path}.{unknown[0]}")
        for required in ("name", "url"):
            if not item.get(required):
                raise ConfigError(f"{path}.{required} is required")
        url = _str(item["url"], f"{path}.url").strip()
        if not url.startswith(("http://", "https://")):
            raise ConfigError(f"{path}.url must be an http(s) URL")
        feeds.append(
            FeedSourceConfig(
                name=_str(item["name"], f"{path}.name").strip(),
                url=url,
                locations=_str_list(item.get("locations"), f"{path}.locations"),
            )
        )
    return feeds


def _parse_adzuna(data: dict) -> AdzunaConfig:
    section = _section(
        data,
        "adzuna",
        {
            "enabled",
            "country",
            "queries",
            "locations",
            "app_id",
            "app_key",
            "results_per_page",
            "max_pages",
            "max_days_old",
        },
        path="sources.adzuna",
    )
    enabled = _bool(section.get("enabled", False), "sources.adzuna.enabled")
    config = AdzunaConfig(
        enabled=enabled,
        country=_str(section.get("country", ""), "sources.adzuna.country").strip().lower(),
        queries=_str_list(section.get("queries"), "sources.adzuna.queries"),
        locations=_str_list(section.get("locations"), "sources.adzuna.locations"),
        app_id=_secret(section.get("app_id", ""), "sources.adzuna.app_id"),
        app_key=_secret(section.get("app_key", ""), "sources.adzuna.app_key"),
        results_per_page=_int_min(
            section.get("results_per_page", 50), "sources.adzuna.results_per_page", 1
        ),
        max_pages=_int_min(section.get("max_pages", 2), "sources.adzuna.max_pages", 1),
        max_days_old=_int_min(section.get("max_days_old", 7), "sources.adzuna.max_days_old", 1),
    )
    if enabled:
        if not config.country:
            raise ConfigError("sources.adzuna.country is required when adzuna is enabled")
        if not config.queries:
            raise ConfigError("sources.adzuna.queries is required when adzuna is enabled")
        if not config.app_id or not config.app_key:
            raise ConfigError(
                "sources.adzuna.app_id and app_key are required when adzuna is enabled"
            )
    return config


def _parse_sources(data: dict) -> SourcesConfig:
    section = _section(
        data,
        "sources",
        {"jobspy", "companies", "feeds", "adzuna", "user_agent", "timeout_seconds"},
    )
    return SourcesConfig(
        jobspy=_parse_jobspy(section),
        companies=_parse_companies(section.get("companies")),
        feeds=_parse_feeds(section.get("feeds")),
        adzuna=_parse_adzuna(section),
        user_agent=_optional(section.get("user_agent"), _str, "sources.user_agent"),
        timeout_seconds=_float_min(
            section.get("timeout_seconds", 30.0), "sources.timeout_seconds", 1.0
        ),
    )


def _parse_scoring(data: dict) -> ScoringConfig:
    section = _section(
        data, "scoring", {"save_threshold", "notify_threshold", "weights", "keywords"}
    )
    raw_weights = section.get("weights") or {}
    raw_keywords = section.get("keywords") or {}
    if not isinstance(raw_weights, dict):
        raise ConfigError("scoring.weights must be a mapping")
    if not isinstance(raw_keywords, dict):
        raise ConfigError("scoring.keywords must be a mapping")
    weights: dict[str, int] = {}
    for category, weight in raw_weights.items():
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise ConfigError(f"scoring.weights.{category} must be an integer")
        weights[str(category)] = weight
    keywords: dict[str, list[str]] = {
        str(category): [term.lower() for term in _str_list(terms, f"scoring.keywords.{category}")]
        for category, terms in raw_keywords.items()
    }
    for category in keywords:
        if category not in weights:
            raise ConfigError(
                f"scoring.keywords.{category} has no matching entry in scoring.weights"
            )
    save_threshold = section.get("save_threshold", 0)
    notify_threshold = section.get("notify_threshold", 20)
    for name, value in (("save_threshold", save_threshold), ("notify_threshold", notify_threshold)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"scoring.{name} must be an integer")
    if notify_threshold < save_threshold:
        raise ConfigError(
            "scoring.notify_threshold must be greater than or equal to save_threshold"
        )
    return ScoringConfig(
        save_threshold=save_threshold,
        notify_threshold=notify_threshold,
        weights=weights,
        keywords=keywords,
    )


def _parse_scheduler(data: dict) -> SchedulerConfig:
    section = _section(
        data,
        "scheduler",
        {
            "interval_hours",
            "run_on_startup",
            "retry_on_failure",
            "retry_delay_minutes",
            "max_retries",
        },
    )
    return SchedulerConfig(
        interval_hours=_int_min(section.get("interval_hours", 12), "scheduler.interval_hours", 1),
        run_on_startup=_bool(section.get("run_on_startup", True), "scheduler.run_on_startup"),
        retry_on_failure=_bool(section.get("retry_on_failure", True), "scheduler.retry_on_failure"),
        retry_delay_minutes=_int_min(
            section.get("retry_delay_minutes", 30), "scheduler.retry_delay_minutes", 1
        ),
        max_retries=_int_min(section.get("max_retries", 3), "scheduler.max_retries", 0),
    )


def _parse_notifications(data: dict) -> NotificationsConfig:
    section = _section(data, "notifications", {"enabled", "telegram"})
    telegram = _section(
        section,
        "telegram",
        {"enabled", "bot_token", "chat_ids", "send_summary", "max_jobs", "jobs_per_chunk"},
        path="notifications.telegram",
    )
    jobs_per_chunk = _int_min(
        telegram.get("jobs_per_chunk", 10), "notifications.telegram.jobs_per_chunk", 1
    )
    if jobs_per_chunk > 15:
        raise ConfigError("notifications.telegram.jobs_per_chunk must be at most 15")
    chat_ids = telegram.get("chat_ids") or []
    if not isinstance(chat_ids, list):
        raise ConfigError("notifications.telegram.chat_ids must be a list")
    return NotificationsConfig(
        enabled=_bool(section.get("enabled", False), "notifications.enabled"),
        telegram=TelegramConfig(
            enabled=_bool(telegram.get("enabled", False), "notifications.telegram.enabled"),
            bot_token=_secret(telegram.get("bot_token", ""), "notifications.telegram.bot_token"),
            chat_ids=[str(chat_id).strip() for chat_id in chat_ids if str(chat_id).strip()],
            send_summary=_bool(
                telegram.get("send_summary", True), "notifications.telegram.send_summary"
            ),
            max_jobs=_int_min(telegram.get("max_jobs", 20), "notifications.telegram.max_jobs", 1),
            jobs_per_chunk=jobs_per_chunk,
        ),
    )


def _parse_retention(data: dict) -> RetentionConfig:
    section = _section(data, "retention", {"max_age_days", "purge_blacklist_after_days"})
    return RetentionConfig(
        max_age_days=_int_min(section.get("max_age_days", 30), "retention.max_age_days", 1),
        purge_blacklist_after_days=_int_min(
            section.get("purge_blacklist_after_days", 90),
            "retention.purge_blacklist_after_days",
            1,
        ),
    )


def _parse_attachments(data: dict) -> AttachmentsConfig:
    section = _section(data, "attachments", {"max_size_mb"})
    return AttachmentsConfig(
        max_size_mb=_int_min(section.get("max_size_mb", 20), "attachments.max_size_mb", 1)
    )


def _parse_vector_search(data: dict) -> VectorSearchConfig:
    section = _section(
        data,
        "vector_search",
        {
            "enabled",
            "embed_on_save",
            "default_results",
            "backfill_on_startup",
            "batch_size",
            "sync_interval_minutes",
        },
    )
    return VectorSearchConfig(
        enabled=_bool(section.get("enabled", True), "vector_search.enabled"),
        embed_on_save=_bool(section.get("embed_on_save", True), "vector_search.embed_on_save"),
        default_results=_int_min(
            section.get("default_results", 20), "vector_search.default_results", 1
        ),
        backfill_on_startup=_bool(
            section.get("backfill_on_startup", True), "vector_search.backfill_on_startup"
        ),
        batch_size=_int_min(section.get("batch_size", 100), "vector_search.batch_size", 1),
        sync_interval_minutes=_int_min(
            section.get("sync_interval_minutes", 30), "vector_search.sync_interval_minutes", 1
        ),
    )


def _parse_logging(data: dict) -> LoggingConfig:
    section = _section(data, "logging", {"level", "max_size_mb", "backup_count", "timezone"})
    level = _str(section.get("level", "INFO"), "logging.level").upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError(f"logging.level must be a standard level name, got {level!r}")
    timezone = _str(section.get("timezone", "UTC"), "logging.timezone")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"logging.timezone is not a known IANA zone: {timezone!r}") from exc
    return LoggingConfig(
        level=level,
        max_size_mb=_int_min(section.get("max_size_mb", 10), "logging.max_size_mb", 1),
        backup_count=_int_min(section.get("backup_count", 5), "logging.backup_count", 0),
        timezone=timezone,
    )


TOP_LEVEL_KEYS = {
    "profile",
    "sources",
    "scoring",
    "scheduler",
    "notifications",
    "retention",
    "attachments",
    "vector_search",
    "logging",
}


def parse_config(data: dict[str, Any] | None, *, data_dir: Path | None = None) -> Config:
    """Build a :class:`Config` from a parsed YAML mapping."""
    data = data or {}
    if not isinstance(data, dict):
        raise ConfigError("settings.yaml must contain a mapping at the top level")
    unknown = sorted(set(data) - TOP_LEVEL_KEYS)
    if unknown:
        raise ConfigError(f"Unsupported configuration key: {unknown[0]}")
    return Config(
        profile=_parse_profile(data),
        sources=_parse_sources(data),
        scoring=_parse_scoring(data),
        scheduler=_parse_scheduler(data),
        notifications=_parse_notifications(data),
        retention=_parse_retention(data),
        attachments=_parse_attachments(data),
        vector_search=_parse_vector_search(data),
        logging=_parse_logging(data),
        data_dir=data_dir or DATA_DIR,
    )


def load_config(path: Path | None = None) -> Config:
    """Load and validate the settings file."""
    config_path = path or CONFIG_FILE
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    return parse_config(data)


_config: Config | None = None
_config_lock = threading.Lock()


def get_config() -> Config:
    """Return the process-wide configuration, loading it on first use."""
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = load_config()
    return _config


def reload_config() -> Config:
    """Re-read the settings file and replace the process-wide configuration."""
    global _config
    with _config_lock:
        _config = load_config()
        return _config


def set_config(config: Config | None) -> None:
    """Replace the process-wide configuration (tests and embedding callers)."""
    global _config
    with _config_lock:
        _config = config
