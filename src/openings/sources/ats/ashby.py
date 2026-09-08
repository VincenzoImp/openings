"""Ashby Posting API: ``api.ashbyhq.com/posting-api/job-board/{slug}``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import html_to_markdown, http_get_json, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch(
    company: CompanySourceConfig, user_agent: str | None, timeout: float
) -> list[dict[str, Any]]:
    payload = http_get_json(
        API.format(slug=company.slug),
        user_agent=user_agent,
        timeout=timeout,
        params={"includeCompensation": "true"},
    )
    records: list[dict[str, Any]] = []
    for job in payload.get("jobs", []) or []:
        locations = [job.get("location") or ""]
        locations += [
            item.get("location")
            for item in job.get("secondaryLocations") or []
            if item.get("location")
        ]
        location = ", ".join(item for item in locations if item)
        compensation = job.get("compensation") or {}
        summary = compensation.get("compensationTierSummary") or compensation.get(
            "scrapeableCompensationSalarySummary"
        )
        description = html_to_markdown(job.get("descriptionHtml")) or job.get("descriptionPlain")
        if summary and description:
            description = f"**Compensation:** {summary}\n\n{description}"
        records.append(
            {
                "title": job.get("title") or "",
                "company": company.name,
                "location": location,
                "source": "ashby",
                "external_id": job.get("id"),
                "job_url": job.get("jobUrl") or job.get("applyUrl"),
                "description": description,
                "date_posted": to_date(job.get("publishedAt")),
                "job_type": job.get("employmentType"),
                "is_remote": bool(job.get("isRemote")) if job.get("isRemote") is not None else None,
                "company_url": f"https://jobs.ashbyhq.com/{company.slug}",
                "raw_json": raw_json(job),
            }
        )
    return records
