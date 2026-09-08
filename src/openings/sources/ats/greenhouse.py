"""Greenhouse Job Board API: ``boards-api.greenhouse.io/v1/boards/{slug}/jobs``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import html_to_markdown, http_get_json, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    payload = http_get_json(
        API.format(slug=company.slug),
        user_agent=user_agent,
        timeout=timeout,
        params={"content": "true"},
    )
    records: list[dict[str, Any]] = []
    for job in payload.get("jobs", []) or []:
        location = (job.get("location") or {}).get("name") or ""
        offices = [office.get("name") for office in job.get("offices") or [] if office.get("name")]
        if not location and offices:
            location = ", ".join(offices)
        records.append(
            {
                "title": job.get("title") or "",
                "company": company.name,
                "location": location,
                "source": "greenhouse",
                "external_id": str(job.get("id")) if job.get("id") is not None else None,
                "job_url": job.get("absolute_url"),
                "description": html_to_markdown(job.get("content")),
                "date_posted": to_date(job.get("first_published") or job.get("updated_at")),
                "is_remote": "remote" in location.lower() or None,
                "company_url": f"https://boards.greenhouse.io/{company.slug}",
                "raw_json": raw_json(job),
            }
        )
    return records
