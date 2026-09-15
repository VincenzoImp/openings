"""BambooHR careers board: ``{slug}.bamboohr.com/careers/list``.

The listing is JSON but carries no copy, so an unstored posting is fetched once
more through ``/careers/{id}/detail``, capped like the other detail-fetching
adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import (
    SourceError,
    html_to_markdown,
    http_get_json,
    location_allowed,
    raw_json,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

BASE = "https://{slug}.bamboohr.com"
MAX_DETAILS = 80


def _location(job: dict[str, Any]) -> str:
    place = job.get("location") or job.get("atsLocation") or {}
    parts = [place.get("city"), place.get("state"), place.get("country")]
    text = ", ".join(str(part) for part in parts if part)
    if job.get("isRemote") or (job.get("locationType") or "") == "remote":
        text = f"{text} (Remote)" if text else "Remote"
    return text


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    base = BASE.format(slug=company.slug)
    payload = http_get_json(f"{base}/careers/list", user_agent=user_agent, timeout=timeout)
    listing = payload.get("result") or []

    kept = [job for job in listing if location_allowed(_location(job), company.locations)]
    ids = [str(job["id"]) for job in kept if job.get("id") is not None]
    already_stored = known(ids) if known else set()

    records: list[dict[str, Any]] = []
    details_fetched = 0
    for job in kept:
        job_id = job.get("id")
        external_id = str(job_id) if job_id is not None else None
        opening: dict[str, Any] = {}
        if (
            job_id is not None
            and external_id not in already_stored
            and details_fetched < MAX_DETAILS
        ):
            details_fetched += 1
            try:
                detail = http_get_json(
                    f"{base}/careers/{job_id}/detail", user_agent=user_agent, timeout=timeout
                )
                opening = (detail.get("result") or {}).get("jobOpening") or {}
            except SourceError:
                opening = {}
        records.append(
            {
                "title": job.get("jobOpeningName") or opening.get("jobOpeningName") or "",
                "company": company.name,
                "location": _location(job),
                "source": "bamboohr",
                "external_id": external_id,
                "job_url": opening.get("jobOpeningShareUrl") or f"{base}/careers/{job_id}",
                "description": html_to_markdown(opening.get("description")),
                "date_posted": to_date(opening.get("datePosted") or opening.get("postedDate")),
                "job_type": job.get("employmentStatusLabel") or job.get("employmentType"),
                "is_remote": bool(job.get("isRemote")) or None,
                "company_url": f"{base}/careers",
                "raw_json": raw_json({**job, **opening} if opening else job),
            }
        )
    return records
