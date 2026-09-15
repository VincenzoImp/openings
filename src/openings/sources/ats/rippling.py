"""Rippling ATS board: ``api.rippling.com/platform/api/ats/v1/board/{slug}/jobs``.

The listing carries title, location and department only, so an unstored posting
is fetched once more by uuid, capped like the other detail-fetching adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import (
    SourceError,
    html_to_markdown,
    http_get_json,
    location_kept,
    raw_json,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

API = "https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
MAX_DETAILS = 80


def _location(job: dict[str, Any], detail: dict[str, Any]) -> str:
    places = detail.get("workLocations") or []
    if places:
        return ", ".join(str(place) for place in places if place)
    return (job.get("workLocation") or {}).get("label") or ""


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    base = API.format(slug=company.slug)
    listing = http_get_json(base, user_agent=user_agent, timeout=timeout) or []

    kept = [
        job
        for job in listing
        if location_kept((job.get("workLocation") or {}).get("label") or "", company.locations)
    ]
    ids = [str(job["uuid"]) for job in kept if job.get("uuid")]
    already_stored = known(ids) if known else set()

    records: list[dict[str, Any]] = []
    details_fetched = 0
    for job in kept:
        uuid = job.get("uuid")
        detail: dict[str, Any] = {}
        if uuid and str(uuid) not in already_stored and details_fetched < MAX_DETAILS:
            details_fetched += 1
            try:
                detail = http_get_json(f"{base}/{uuid}", user_agent=user_agent, timeout=timeout)
            except SourceError:
                detail = {}
        description = detail.get("description")
        if isinstance(description, dict):
            description = "\n\n".join(str(part) for part in description.values() if part)
        employment = detail.get("employmentType") or {}
        records.append(
            {
                "title": job.get("name") or "",
                "company": company.name,
                "location": _location(job, detail),
                "source": "rippling",
                "external_id": str(uuid) if uuid else None,
                "job_url": job.get("url"),
                "description": html_to_markdown(description),
                "date_posted": to_date(detail.get("createdOn")),
                "job_type": employment.get("id") or employment.get("label") or None,
                "company_url": f"https://ats.rippling.com/{company.slug}/jobs",
                "raw_json": raw_json({**job, **detail} if detail else job),
            }
        )
    return records
