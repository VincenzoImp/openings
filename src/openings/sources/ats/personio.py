"""Personio career-site feed: ``https://{slug}.jobs.personio.de/xml``.

Personio is the board most small and mid-size employers in the German-speaking
market use. The feed is public and unauthenticated but it must be switched on
per tenant (Settings > Recruiting > Career page), so a tenant that has never
enabled it answers with the career site's HTML rather than XML; that surfaces
as a SourceError instead of an empty company.

The schema is Personio's own (``<workzag-jobs>`` of ``<position>`` elements),
documented at https://developer.personio.de/docs/retrieving-open-job-positions,
not RSS, so ``feedparser`` does not apply. The whole description ships inline:
no detail fetch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree

from openings.sources.base import (
    html_to_markdown,
    http_get_xml,
    location_kept,
    raw_json,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

BASE = "https://{slug}.jobs.personio.de"
SCHEDULE_TO_JOB_TYPE = {"full-time": "fulltime", "part-time": "parttime"}


def _text(node: ElementTree.Element, tag: str) -> str:
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _description(position: ElementTree.Element) -> str | None:
    """Personio splits the advert into named blocks; keep their own headings."""
    parts: list[str] = []
    for item in position.iterfind("./jobDescriptions/jobDescription"):
        name = _text(item, "name")
        body = html_to_markdown(_text(item, "value"))
        if body:
            parts.append(f"## {name}\n\n{body}" if name else body)
    return "\n\n".join(parts) or None


def _location(position: ElementTree.Element) -> str:
    parts = [_text(position, "office"), _text(position, "subcompany")]
    return ", ".join(part for part in parts if part)


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    base = BASE.format(slug=company.slug)
    root = http_get_xml(
        f"{base}/xml", user_agent=user_agent, timeout=timeout, params={"language": "en"}
    )

    records: list[dict[str, Any]] = []
    for position in root.iterfind("position"):
        location = _location(position)
        if not location_kept(location, company.locations):
            continue
        position_id = _text(position, "id")
        schedule = _text(position, "schedule")
        records.append(
            {
                "title": _text(position, "name"),
                "company": company.name,
                "location": location,
                "source": "personio",
                "external_id": position_id or None,
                "job_url": f"{base}/job/{position_id}" if position_id else None,
                "description": _description(position),
                "date_posted": to_date(_text(position, "createdAt")),
                "job_type": SCHEDULE_TO_JOB_TYPE.get(schedule)
                or _text(position, "employmentType")
                or None,
                "job_level": _text(position, "seniority") or None,
                "company_url": base,
                "raw_json": raw_json(
                    {child.tag: (child.text or "").strip() for child in position if child.text}
                ),
            }
        )
    return records
