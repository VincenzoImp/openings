"""Workday CXS API: ``{host}/wday/cxs/{tenant}/{site}/jobs``.

Workday is where the Swiss corporates and several of the large technology
employers publish, and it is the only supported board that needs a POST: the
listing is a search request, paged by offset. The slug carries the whole board
address, ``host/site`` (for example ``abb.wd3.myworkdayjobs.com/External_Career_Page``),
because the tenant, the datacenter number and the site name all vary
independently and cannot be derived from a company name.

The listing has no description, so an unstored posting is fetched once more
through its ``externalPath``, capped like the other detail-fetching adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import (
    SourceError,
    html_to_markdown,
    http_get_json,
    http_post_json,
    location_allowed,
    raw_json,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

PAGE_SIZE = 20
MAX_LISTING = 200
MAX_DETAILS = 60


def _board(slug: str) -> tuple[str, str, str]:
    """Split ``host/site`` into the API base, the tenant and the public base."""
    cleaned = slug.strip().strip("/")
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    host, _, site = cleaned.partition("/")
    site = site.strip("/")
    if not host or not site:
        raise SourceError(f"workday slug must be 'host/site', got {slug!r}")
    tenant = host.split(".", 1)[0]
    return f"https://{host}/wday/cxs/{tenant}/{site}", tenant, f"https://{host}/{site}"


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    api, _tenant, public = _board(company.slug)

    listing: list[dict[str, Any]] = []
    offset = 0
    while offset < MAX_LISTING:
        payload = http_post_json(
            f"{api}/jobs",
            user_agent=user_agent,
            timeout=timeout,
            body={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
        )
        page = payload.get("jobPostings") or []
        listing.extend(page)
        offset += PAGE_SIZE
        if not page or offset >= int(payload.get("total") or 0):
            break

    kept = [
        job
        for job in listing
        if location_allowed(job.get("locationsText") or "", company.locations)
    ]
    ids = [str(job.get("externalPath")) for job in kept if job.get("externalPath")]
    already_stored = known(ids) if known else set()

    records: list[dict[str, Any]] = []
    details_fetched = 0
    for job in kept:
        path = job.get("externalPath") or ""
        external_id = str(path) if path else None
        info: dict[str, Any] = {}
        if path and external_id not in already_stored and details_fetched < MAX_DETAILS:
            details_fetched += 1
            try:
                detail = http_get_json(f"{api}{path}", user_agent=user_agent, timeout=timeout)
                info = detail.get("jobPostingInfo") or {}
            except SourceError:
                info = {}
        location = info.get("location") or job.get("locationsText") or ""
        records.append(
            {
                "title": job.get("title") or info.get("title") or "",
                "company": company.name,
                "location": location,
                "source": "workday",
                "external_id": external_id,
                "job_url": info.get("externalUrl") or f"{public}/job{path}",
                "description": html_to_markdown(info.get("jobDescription")),
                "date_posted": to_date(info.get("startDate")),
                "job_type": info.get("timeType") or None,
                "is_remote": True if "remote" in location.lower() else None,
                "company_url": public,
                "raw_json": raw_json({"listing": job, "detail": info} if info else job),
            }
        )
    return records
