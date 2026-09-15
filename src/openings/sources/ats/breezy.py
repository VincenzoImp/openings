"""BreezyHR public board: ``https://{slug}.breezy.hr/json``.

One request returns the whole board. Note the limitation, which is Breezy's and
not this adapter's: the public feed carries no description at any documented
parameter, and the posting page itself is a client-rendered application with no
server-side copy to read. Postings therefore arrive with title, company,
location, salary and URL but no body, so they are scored on the title alone.
That is worth knowing before configuring a Breezy board with a high
``save_threshold``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import http_get_json, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

API = "https://{slug}.breezy.hr/json"


def _location(posting: dict[str, Any]) -> str:
    place = posting.get("location") or {}
    if place.get("name"):
        text = str(place["name"])
    else:
        parts = [
            place.get("city"),
            (place.get("state") or {}).get("name"),
            (place.get("country") or {}).get("name"),
        ]
        text = ", ".join(str(part) for part in parts if part)
    if place.get("is_remote"):
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
        params={"full": "true"},
    )
    records: list[dict[str, Any]] = []
    for posting in payload or []:
        place = posting.get("location") or {}
        records.append(
            {
                "title": posting.get("name") or "",
                "company": (posting.get("company") or {}).get("name") or company.name,
                "location": _location(posting),
                "source": "breezy",
                "external_id": posting.get("id"),
                "job_url": posting.get("url"),
                "description": None,
                "date_posted": to_date(posting.get("published_date")),
                "job_type": (posting.get("type") or {}).get("name"),
                "is_remote": bool(place.get("is_remote")) or None,
                "company_url": f"https://{company.slug}.breezy.hr/",
                "raw_json": raw_json(posting),
            }
        )
    return records
