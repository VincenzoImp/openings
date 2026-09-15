"""Oracle Cloud Recruiting: ``{host}/hcmRestApi/resources/latest/recruitingCE*``.

Oracle is where a large share of corporates publish. Like Workday it needs the
whole board address rather than a company name, because the pod, the region and
the site number vary independently: the slug is ``host/site``, for example
``eipb.fa.em2.oraclecloud.com/CX_5``.

The listing nests one level deeper than the other feeds (``items[0]
.requisitionList``) and carries no description, so an unstored posting is
fetched once more by id, capped like the other detail-fetching adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openings.sources.base import (
    SourceError,
    html_to_markdown,
    http_get_json,
    location_kept,
    raw_json,
    remote_flag,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

LIST_PATH = "/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
DETAIL_PATH = "/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
EXPAND = "requisitionList.secondaryLocations,flexFieldsFacet.values"
PAGE_SIZE = 50
MAX_LISTING = 200
MAX_DETAILS = 60


def _board(slug: str) -> tuple[str, str]:
    """Split ``host/site`` into the host and the site number."""
    cleaned = slug.strip().strip("/")
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    host, _, site = cleaned.partition("/")
    site = site.strip("/")
    if not host or not site:
        raise SourceError(f"oracle slug must be 'host/site', got {slug!r}")
    return host, site


def _location(job: dict[str, Any]) -> str:
    primary = job.get("PrimaryLocation") or ""
    extra = [
        item.get("Name")
        for item in job.get("secondaryLocations") or []
        if isinstance(item, dict) and item.get("Name")
    ]
    parts = [primary, *extra]
    text = ", ".join(str(part) for part in parts if part)
    if (job.get("WorkplaceTypeCode") or "").upper().endswith("REMOTE"):
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _description(detail: dict[str, Any]) -> str | None:
    parts = []
    for key in (
        "ExternalDescriptionStr",
        "ExternalResponsibilitiesStr",
        "ExternalQualificationsStr",
    ):
        text = html_to_markdown(detail.get(key))
        if text:
            parts.append(text)
    return "\n\n".join(parts) or None


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    host, site = _board(company.slug)
    list_url = f"https://{host}{LIST_PATH}"

    listing: list[dict[str, Any]] = []
    offset = 0
    while offset < MAX_LISTING:
        payload = http_get_json(
            list_url,
            user_agent=user_agent,
            timeout=timeout,
            params={
                "onlyData": "true",
                "expand": EXPAND,
                "finder": f"findReqs;siteNumber={site},limit={PAGE_SIZE},offset={offset}",
            },
        )
        items = payload.get("items") or [{}]
        page = items[0].get("requisitionList") or []
        listing.extend(page)
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE:
            break

    kept = [job for job in listing if location_kept(_location(job), company.locations)]
    ids = [str(job["Id"]) for job in kept if job.get("Id") is not None]
    already_stored = known(ids) if known else set()

    records: list[dict[str, Any]] = []
    details_fetched = 0
    for job in kept:
        job_id = job.get("Id")
        external_id = str(job_id) if job_id is not None else None
        detail: dict[str, Any] = {}
        if (
            job_id is not None
            and external_id not in already_stored
            and details_fetched < MAX_DETAILS
        ):
            details_fetched += 1
            try:
                payload = http_get_json(
                    f"https://{host}{DETAIL_PATH}",
                    user_agent=user_agent,
                    timeout=timeout,
                    params={
                        "onlyData": "true",
                        "expand": "all",
                        "finder": f'ById;Id="{job_id}",siteNumber={site}',
                    },
                )
                detail = (payload.get("items") or [{}])[0]
            except SourceError:
                detail = {}
        merged = {**job, **detail}
        location = _location(merged)
        records.append(
            {
                "title": merged.get("Title") or "",
                "company": company.name,
                "location": location,
                "source": "oracle",
                "external_id": external_id,
                "job_url": f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{job_id}",
                "description": _description(detail) if detail else None,
                "date_posted": to_date(
                    merged.get("PostedDate") or merged.get("ExternalPostedStartDate")
                ),
                "job_type": merged.get("JobSchedule") or merged.get("WorkerType") or None,
                "is_remote": remote_flag(location=location),
                "job_level": merged.get("JobLevel") or merged.get("ManagerLevel") or None,
                "company_url": f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}",
                "raw_json": raw_json(merged),
            }
        )
    return records
