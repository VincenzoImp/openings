"""Run every configured source and merge the rows into one canonical frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from openings.logger import get_logger, log_section
from openings.models import SourceRunStats, generate_job_id
from openings.sources import rss
from openings.sources.adzuna import run_adzuna
from openings.sources.ats import FETCHERS
from openings.sources.base import (
    CANONICAL_COLUMNS,
    SourceError,
    SourceResult,
    empty_frame,
    frame_from_records,
    location_allowed,
)
from openings.sources.jobspy import run_jobspy

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig, Config, FeedSourceConfig


@dataclass
class CollectResult:
    frame: pd.DataFrame = field(default_factory=empty_frame)
    stats: list[SourceRunStats] = field(default_factory=list)
    total_found: int = 0

    @property
    def unique_found(self) -> int:
        return len(self.frame)

    @property
    def errors(self) -> list[str]:
        return [f"{stat.name}: {error}" for stat in self.stats for error in stat.errors]


def fetch_company(company: CompanySourceConfig, config: Config) -> SourceResult:
    stats = SourceRunStats(name=f"{company.ats}:{company.slug}", tasks=1)
    fetcher = FETCHERS[company.ats]
    try:
        records = fetcher(company, config.sources.user_agent, config.sources.timeout_seconds)
    except SourceError as exc:
        stats.failed = 1
        stats.errors.append(str(exc))
        return SourceResult(stats=stats)
    kept = [
        record for record in records if location_allowed(record.get("location"), company.locations)
    ]
    stats.succeeded = 1
    stats.rows = len(kept)
    return SourceResult(stats=stats, frame=frame_from_records(kept))


def fetch_feed(feed: FeedSourceConfig, config: Config) -> SourceResult:
    stats = SourceRunStats(name=f"rss:{feed.name}", tasks=1)
    try:
        records = rss.fetch(feed, config.sources.user_agent, config.sources.timeout_seconds)
    except SourceError as exc:
        stats.failed = 1
        stats.errors.append(str(exc))
        return SourceResult(stats=stats)
    kept = [
        record
        for record in records
        if not record.get("location") or location_allowed(record.get("location"), feed.locations)
    ]
    stats.succeeded = 1
    stats.rows = len(kept)
    return SourceResult(stats=stats, frame=frame_from_records(kept))


def _dedupe(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    ids = frame.apply(
        lambda row: generate_job_id(
            str(row.get("title") or ""),
            str(row.get("company") or ""),
            str(row.get("location") or ""),
        ),
        axis=1,
    )
    return frame.loc[~ids.duplicated()].copy()


def collect_all(config: Config) -> CollectResult:
    """Sources run in order: boards, companies, feeds, Adzuna. Failures are
    isolated per source and per company; a broken feed costs nothing but a
    line in the run summary."""
    logger = get_logger("collect")
    log_section(logger, "COLLECTING")
    results: list[SourceResult] = []

    if config.sources.jobspy.enabled:
        results.append(run_jobspy(config))
    for company in config.sources.companies:
        result = fetch_company(company, config)
        results.append(result)
        logger.info(
            "Company %s (%s): %d rows%s",
            company.name,
            company.ats,
            result.stats.rows,
            f", error: {result.stats.errors[0]}" if result.stats.errors else "",
        )
    for feed in config.sources.feeds:
        result = fetch_feed(feed, config)
        results.append(result)
        logger.info(
            "Feed %s: %d rows%s",
            feed.name,
            result.stats.rows,
            f", error: {result.stats.errors[0]}" if result.stats.errors else "",
        )
    if config.sources.adzuna.enabled:
        results.append(run_adzuna(config))

    frames = [
        result.frame for result in results if result.frame is not None and not result.frame.empty
    ]
    total_found = sum(len(frame) for frame in frames)
    if frames:
        combined = pd.concat(frames, ignore_index=True)[list(CANONICAL_COLUMNS)]
        combined = combined[combined["title"].astype(str).str.strip() != ""]
        combined = _dedupe(combined)
    else:
        combined = empty_frame()
    logger.info("Collected %d rows, %d unique", total_found, len(combined))
    return CollectResult(
        frame=combined, stats=[result.stats for result in results], total_found=total_found
    )
