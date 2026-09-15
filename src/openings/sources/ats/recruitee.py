"""Recruitee careers-site API: ``https://{slug}.recruitee.com/api/offers/``.

Public and unauthenticated, and unusually generous: the list response already
carries the full description, so one request covers a whole board.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import remote_flag, html_to_markdown, http_get_json, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

API = "https://{slug}.recruitee.com/api/offers/"


def _location(offer: dict[str, Any]) -> str:
    text = offer.get("location") or ", ".join(
        str(part) for part in (offer.get("city"), offer.get("country")) if part
    )
    if offer.get("remote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    payload = http_get_json(API.format(slug=company.slug), user_agent=user_agent, timeout=timeout)
    records: list[dict[str, Any]] = []
    for offer in payload.get("offers") or []:
        description = html_to_markdown(offer.get("description"))
        requirements = html_to_markdown(offer.get("requirements"))
        if requirements:
            description = f"{description}\n\n## Requirements\n\n{requirements}".strip()
        offer_id = offer.get("id")
        records.append(
            {
                "title": offer.get("title") or "",
                "company": offer.get("company_name") or company.name,
                "location": _location(offer),
                "source": "recruitee",
                "external_id": str(offer_id) if offer_id is not None else None,
                "job_url": offer.get("careers_url") or offer.get("careers_apply_url"),
                "description": description or None,
                "date_posted": to_date(offer.get("published_at") or offer.get("created_at")),
                "job_type": offer.get("employment_type_code") or offer.get("employment_type"),
                "is_remote": remote_flag(offer.get("remote")),
                "job_level": offer.get("experience") or None,
                "company_url": f"https://{company.slug}.recruitee.com/",
                "raw_json": raw_json(offer),
            }
        )
    return records
