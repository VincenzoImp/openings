"""Postings handed to the tool by a person or an agent, one at a time."""

from __future__ import annotations

from typing import Any

from openings.models import SOURCE_MANUAL
from openings.sources.base import normalize_job_type, raw_json


def record_from_fields(
    *,
    title: str,
    company: str,
    location: str,
    job_url: str | None = None,
    description: str | None = None,
    date_posted: Any = None,
    job_type: str | None = None,
    is_remote: bool | None = None,
    job_level: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    currency: str | None = None,
    salary_interval: str | None = None,
    company_url: str | None = None,
    source: str | None = None,
    external_id: str | None = None,
    raw: Any = None,
) -> dict[str, Any]:
    """Canonical record for a posting supplied field by field."""
    fields = {
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "source": (source or SOURCE_MANUAL).strip().lower(),
        "external_id": external_id,
        "job_url": job_url,
        "description": description,
        "date_posted": date_posted,
        "job_type": normalize_job_type(job_type),
        "is_remote": is_remote,
        "job_level": job_level,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "currency": currency,
        "salary_interval": salary_interval,
        "company_url": company_url,
    }
    fields["raw_json"] = raw_json(raw if raw is not None else fields)
    return fields
