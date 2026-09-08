"""Board scraping through JobSpy: every query, for every location, per job type."""

from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from openings.logger import ProgressLogger, get_logger, log_section
from openings.models import SourceRunStats, generate_job_id
from openings.scoring import fuzzy_post_filter
from openings.sources.base import (
    CANONICAL_COLUMNS,
    SourceResult,
    empty_frame,
    frame_from_records,
    raw_json,
)

if TYPE_CHECKING:
    from openings.config import Config, JobSpyConfig

SOURCE_NAME = "jobspy"

# JobSpy column -> canonical column. Unlisted canonical columns are derived.
_COLUMN_MAP = {
    "title": "title",
    "company": "company",
    "location": "location",
    "job_url": "job_url",
    "description": "description",
    "date_posted": "date_posted",
    "job_type": "job_type",
    "is_remote": "is_remote",
    "job_level": "job_level",
    "min_amount": "min_amount",
    "max_amount": "max_amount",
    "currency": "currency",
    "interval": "salary_interval",
    "company_url": "company_url",
    "id": "external_id",
}


class _Throttle:
    """One global gate: JobSpy hits every configured site per call, so the
    slowest site's delay governs the pace."""

    def __init__(self, settings: JobSpyConfig):
        self.settings = settings
        self._lock = threading.Lock()
        self._last = 0.0
        throttling = settings.throttling
        delay = throttling.default_delay
        for site in settings.sites:
            delay = max(delay, throttling.site_delays.get(site, throttling.default_delay))
        self.delay = delay

    def wait(self) -> None:
        throttling = self.settings.throttling
        if not throttling.enabled:
            return
        with self._lock:
            jitter = self.delay * throttling.jitter
            target = self.delay + random.uniform(-jitter, jitter) if jitter else self.delay
            elapsed = time.time() - self._last
            if elapsed < target:
                time.sleep(target - elapsed)
            self._last = time.time()


def _scrape(
    settings: JobSpyConfig, query: str, location: str, job_type: str | None, user_agent: str | None
) -> pd.DataFrame:
    from jobspy import scrape_jobs

    return scrape_jobs(
        site_name=settings.sites,
        search_term=query,
        location=location,
        results_wanted=settings.results_wanted,
        hours_old=settings.hours_old,
        country_indeed=settings.country_indeed,
        distance=settings.distance,
        is_remote=settings.is_remote,
        job_type=job_type,
        easy_apply=settings.easy_apply,
        offset=settings.offset,
        enforce_annual_salary=settings.enforce_annual_salary,
        description_format=settings.description_format,
        verbose=settings.verbose,
        linkedin_fetch_description=settings.linkedin_fetch_description,
        linkedin_company_ids=settings.linkedin_company_ids,
        google_search_term=settings.google_search_term,
        proxies=settings.proxies,
        ca_cert=settings.ca_cert,
        user_agent=user_agent,
    )


def to_canonical(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename JobSpy columns into the canonical shape and keep the raw row."""
    if frame is None or frame.empty:
        return empty_frame()
    records = []
    for row in frame.to_dict("records"):
        record = {column: row.get(source) for source, column in _COLUMN_MAP.items()}
        record["source"] = str(row.get("site") or SOURCE_NAME).lower()
        record["raw_json"] = raw_json(row)
        records.append(record)
    return frame_from_records(records)


def search_single_query(
    config: Config, query: str, location: str
) -> tuple[pd.DataFrame | None, str | None]:
    """Run one query at one location across every configured job type."""
    settings = config.sources.jobspy
    logger = get_logger("jobspy")
    job_types: list[str | None] = list(settings.job_types) or [None]

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(settings.retry.max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry.base_delay, exp_base=settings.retry.backoff_factor
        ),
        reraise=True,
    )
    def attempt(job_type: str | None) -> pd.DataFrame:
        return _scrape(settings, query, location, job_type, config.sources.user_agent)

    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for job_type in job_types:
        try:
            result = attempt(job_type)
        except Exception as exc:  # noqa: BLE001 - every failure is reported per task
            message = f"{type(exc).__name__}: {exc}"
            logger.warning("Query failed: %s @ %s [%s]: %s", query, location, job_type, message)
            errors.append(message)
            continue
        if result is not None and len(result) > 0:
            frames.append(result)

    if not frames:
        return None, "; ".join(dict.fromkeys(errors)) if errors else None

    combined = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0].copy()
    ids = combined.apply(
        lambda row: generate_job_id(
            str(row.get("title", "")), str(row.get("company", "")), str(row.get("location", ""))
        ),
        axis=1,
    )
    combined = combined.loc[~ids.duplicated()].copy()
    combined = fuzzy_post_filter(combined, query, location, settings)
    if combined.empty:
        return None, None
    return combined, None


def run_jobspy(config: Config) -> SourceResult:
    """Every query at every location, throttled, in a bounded thread pool."""
    settings = config.sources.jobspy
    logger = get_logger("jobspy")
    stats = SourceRunStats(name=SOURCE_NAME)

    queries = settings.all_queries
    tasks = [(query, location) for location in settings.locations for query in queries]
    stats.tasks = len(tasks)
    if not tasks:
        logger.info("JobSpy: no queries configured, skipping")
        return SourceResult(stats=stats)

    log_section(logger, "JOBSPY")
    logger.info(
        "Tasks: %d (%d queries x %d locations x %d job types) on %s",
        len(tasks),
        len(queries),
        len(settings.locations),
        max(1, len(settings.job_types)),
        ", ".join(settings.sites),
    )
    throttle = _Throttle(settings)
    if settings.throttling.enabled:
        estimate = len(tasks) * max(1, len(settings.job_types)) * throttle.delay
        logger.info(
            "Throttle %.1fs (jitter %.0f%%), lower bound %.0f minutes",
            throttle.delay,
            settings.throttling.jitter * 100,
            estimate / 60 / settings.parallel.max_workers,
        )

    progress = ProgressLogger(logger, len(tasks), "JobSpy")
    frames: list[pd.DataFrame] = []
    seen: set[str] = set()
    lock = threading.Lock()

    def task(query: str, location: str) -> tuple[pd.DataFrame | None, str | None]:
        throttle.wait()
        return search_single_query(config, query, location)

    with ThreadPoolExecutor(max_workers=settings.parallel.max_workers) as pool:
        futures = {
            pool.submit(task, query, location): (query, location) for query, location in tasks
        }
        for future in as_completed(futures):
            query, location = futures[future]
            try:
                frame, error = future.result()
            except Exception as exc:  # noqa: BLE001
                stats.failed += 1
                stats.errors.append(f"{query} @ {location}: {exc}")
                progress.update(success=False, message=f"ERROR: {query} @ {location}")
                continue
            if error:
                stats.failed += 1
                stats.errors.append(f"{query} @ {location}: {error}")
                progress.update(success=False, message=f"FAILED: {query} @ {location}")
                continue
            stats.succeeded += 1
            if frame is None or frame.empty:
                progress.update(success=True, message=f"No results: {query} @ {location}")
                continue
            keys = [
                generate_job_id(
                    str(r.get("title", "")), str(r.get("company", "")), str(r.get("location", ""))
                )
                for r in frame.to_dict("records")
            ]
            with lock:
                fresh = [i for i, key in enumerate(keys) if key not in seen]
                seen.update(keys[i] for i in fresh)
                if fresh:
                    frames.append(frame.iloc[fresh].copy())
            stats.rows += len(fresh)
            progress.update(success=True, message=f"{len(frame)} rows: {query} @ {location}")

    progress.summary()
    if not frames:
        return SourceResult(stats=stats)
    combined = to_canonical(pd.concat(frames, ignore_index=True))
    stats.rows = len(combined)
    return SourceResult(stats=stats, frame=combined[list(CANONICAL_COLUMNS)])
