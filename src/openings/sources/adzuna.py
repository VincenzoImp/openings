"""Adzuna search API: ``api.adzuna.com/v1/api/jobs/{country}/search/{page}``.

Optional and keyed. Adzuna returns a description snippet rather than the full
posting, so scoring has less text to work with than with other sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.models import SourceRunStats
from openings.sources.base import (
    SourceError,
    SourceResult,
    frame_from_records,
    http_get_json,
    location_allowed,
    raw_json,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import Config

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
SOURCE_NAME = "adzuna"


def _record(result: dict[str, Any]) -> dict[str, Any]:
    location = (result.get("location") or {}).get("display_name") or ""
    contract_time = result.get("contract_time")
    job_type = None
    if contract_time == "full_time":
        job_type = "fulltime"
    elif contract_time == "part_time":
        job_type = "parttime"
    if result.get("contract_type") == "contract":
        job_type = "contract"
    return {
        "title": result.get("title") or "",
        "company": (result.get("company") or {}).get("display_name") or "",
        "location": location,
        "source": SOURCE_NAME,
        "external_id": str(result.get("id")) if result.get("id") is not None else None,
        "job_url": result.get("redirect_url"),
        "description": result.get("description"),
        "date_posted": to_date(result.get("created")),
        "job_type": job_type,
        "min_amount": result.get("salary_min"),
        "max_amount": result.get("salary_max"),
        "raw_json": raw_json(result),
    }


def run_adzuna(config: Config) -> SourceResult:
    settings = config.sources.adzuna
    stats = SourceRunStats(name=SOURCE_NAME)
    if not settings.enabled:
        return SourceResult(stats=stats)

    locations = settings.locations or [""]
    records: list[dict[str, Any]] = []
    for query in settings.queries:
        for where in locations:
            stats.tasks += 1
            try:
                for page in range(1, settings.max_pages + 1):
                    params = {
                        "app_id": settings.app_id,
                        "app_key": settings.app_key,
                        "what": query,
                        "results_per_page": settings.results_per_page,
                        "max_days_old": settings.max_days_old,
                        "content-type": "application/json",
                    }
                    if where:
                        params["where"] = where
                    payload = http_get_json(
                        API.format(country=settings.country, page=page),
                        user_agent=config.sources.user_agent,
                        timeout=config.sources.timeout_seconds,
                        params=params,
                    )
                    results = payload.get("results") or []
                    for result in results:
                        record = _record(result)
                        if location_allowed(record["location"], settings.locations):
                            records.append(record)
                    if len(results) < settings.results_per_page:
                        break
                stats.succeeded += 1
            except SourceError as exc:
                stats.failed += 1
                stats.errors.append(f"{query} @ {where or 'anywhere'}: {exc}")
    frame = frame_from_records(records)
    stats.rows = len(frame)
    return SourceResult(stats=stats, frame=frame)
