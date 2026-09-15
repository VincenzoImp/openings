"""Workable widget API: ``apply.workable.com/api/v1/widget/accounts/{slug}``.

One request returns the whole board with the copy included, so unlike the other
detail-carrying boards this needs no second fetch per posting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import remote_flag, html_to_markdown, http_get_json, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

API = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


def _location(job: dict[str, Any]) -> str:
    parts = [job.get("city"), job.get("state"), job.get("country")]
    text = ", ".join(str(part) for part in parts if part)
    if job.get("telecommuting"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


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
        params={"details": "true"},
    )
    records: list[dict[str, Any]] = []
    for job in payload.get("jobs") or []:
        records.append(
            {
                "title": job.get("title") or "",
                "company": company.name,
                "location": _location(job),
                "source": "workable",
                "external_id": job.get("shortcode"),
                "job_url": job.get("url") or job.get("shortlink"),
                "description": html_to_markdown(job.get("description")),
                "date_posted": to_date(job.get("published_on") or job.get("created_at")),
                "job_type": job.get("employment_type") or None,
                "is_remote": remote_flag(job.get("telecommuting")),
                "job_level": job.get("experience") or None,
                "company_url": f"https://apply.workable.com/{company.slug}",
                "raw_json": raw_json(job),
            }
        )
    return records
