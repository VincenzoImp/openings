"""Lever Postings API: ``api.lever.co/v0/postings/{slug}?mode=json``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import html_to_markdown, http_get_json, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig

API = "https://api.lever.co/v0/postings/{slug}"

_WORKPLACE_REMOTE = {"remote"}


def _description(job: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if job.get("description"):
        parts.append(html_to_markdown(job["description"]) or "")
    for block in job.get("lists") or []:
        heading = block.get("text")
        content = html_to_markdown(block.get("content"))
        if heading:
            parts.append(f"## {heading}")
        if content:
            parts.append(content)
    if job.get("additional"):
        parts.append(html_to_markdown(job["additional"]) or "")
    text = "\n\n".join(part for part in parts if part).strip()
    return text or job.get("descriptionPlain") or None


def fetch(
    company: CompanySourceConfig, user_agent: str | None, timeout: float
) -> list[dict[str, Any]]:
    payload = http_get_json(
        API.format(slug=company.slug),
        user_agent=user_agent,
        timeout=timeout,
        params={"mode": "json"},
    )
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    records: list[dict[str, Any]] = []
    for job in payload or []:
        categories = job.get("categories") or {}
        location = categories.get("location") or ""
        if categories.get("allLocations"):
            location = ", ".join(categories["allLocations"])
        salary = job.get("salaryRange") or {}
        workplace = str(job.get("workplaceType") or "").lower()
        records.append(
            {
                "title": job.get("text") or "",
                "company": company.name,
                "location": location,
                "source": "lever",
                "external_id": job.get("id"),
                "job_url": job.get("hostedUrl") or job.get("applyUrl"),
                "description": _description(job),
                "date_posted": to_date(job.get("createdAt")),
                "job_type": categories.get("commitment"),
                "is_remote": True if workplace in _WORKPLACE_REMOTE else None,
                "job_level": categories.get("level"),
                "min_amount": salary.get("min"),
                "max_amount": salary.get("max"),
                "currency": salary.get("currency"),
                "salary_interval": salary.get("interval"),
                "company_url": f"https://jobs.lever.co/{company.slug}",
                "raw_json": raw_json(job),
            }
        )
    return records
