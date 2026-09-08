"""SmartRecruiters Posting API: ``api.smartrecruiters.com/v1/companies/{slug}/postings``.

The listing carries no description; a posting not yet stored is fetched once
more through its ``ref`` URL, capped so a large board cannot turn one run
into hundreds of requests. Known postings are emitted without a detail
fetch: the database keeps their description and refreshes ``last_seen``.
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

API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE_SIZE = 100
MAX_LISTING = 500
MAX_DETAILS = 100


def _location_text(location: dict[str, Any] | None) -> str:
    location = location or {}
    parts = [location.get("city"), location.get("region"), location.get("country")]
    text = ", ".join(str(part) for part in parts if part)
    if location.get("remote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _details_description(detail: dict[str, Any]) -> str | None:
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    parts: list[str] = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        section = sections.get(key) or {}
        text = html_to_markdown(section.get("text"))
        if text:
            title = section.get("title") or key
            parts.append(f"## {title}\n\n{text}")
    return "\n\n".join(parts) or None


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    listing: list[dict[str, Any]] = []
    offset = 0
    while offset < MAX_LISTING:
        payload = http_get_json(
            API.format(slug=company.slug),
            user_agent=user_agent,
            timeout=timeout,
            params={"limit": PAGE_SIZE, "offset": offset},
        )
        content = payload.get("content") or []
        listing.extend(content)
        total = int(payload.get("totalFound") or 0)
        offset += PAGE_SIZE
        if not content or offset >= total:
            break

    kept = [
        posting
        for posting in listing
        if location_allowed(_location_text(posting.get("location")), company.locations)
    ]
    ids = [str(posting["id"]) for posting in kept if posting.get("id") is not None]
    already_stored = known(ids) if known else set()

    records: list[dict[str, Any]] = []
    details_fetched = 0
    for posting in kept:
        posting_id = posting.get("id")
        external_id = str(posting_id) if posting_id is not None else None
        description = None
        ref = posting.get("ref")
        if ref and external_id not in already_stored and details_fetched < MAX_DETAILS:
            details_fetched += 1
            try:
                description = _details_description(
                    http_get_json(ref, user_agent=user_agent, timeout=timeout)
                )
            except SourceError:
                description = None
        records.append(
            {
                "title": posting.get("name") or "",
                "company": company.name,
                "location": _location_text(posting.get("location")),
                "source": "smartrecruiters",
                "external_id": external_id,
                "job_url": f"https://jobs.smartrecruiters.com/{company.slug}/{posting_id}",
                "description": description,
                "date_posted": to_date(posting.get("releasedDate")),
                "job_type": (posting.get("typeOfEmployment") or {}).get("label"),
                "is_remote": bool((posting.get("location") or {}).get("remote")) or None,
                "job_level": (posting.get("experienceLevel") or {}).get("label"),
                "company_url": f"https://careers.smartrecruiters.com/{company.slug}",
                "raw_json": raw_json(posting),
            }
        )
    return records
