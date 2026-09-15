"""join.com company boards, read from the page's embedded ``__NEXT_DATA__``.

join.com is the board most Swiss and German small and mid-size employers use,
and it publishes no documented JSON API. It does ship its own state to the
browser as a JSON blob inside the page, which is what this reads: the company
page carries the job list, and each job page carries the copy. That is a
scrape, so it is written to fail softly and to be obvious when join.com changes
its page shape, rather than to pretend it is a contract.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from openings.sources.base import (
    SourceError,
    html_to_markdown,
    http_get,
    location_kept,
    raw_json,
    remote_flag,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig
    from openings.sources.ats import KnownIds

BASE = "https://join.com/companies/{slug}"
NEXT_DATA = re.compile(r'id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', re.DOTALL)
MAX_DETAILS = 60


def _next_data(html: str, url: str) -> dict[str, Any]:
    match = NEXT_DATA.search(html)
    if not match:
        raise SourceError(f"{url}: no __NEXT_DATA__ payload; join.com page shape changed")
    try:
        payload = json.loads(match.group(1))
    except ValueError as exc:
        raise SourceError(f"{url}: __NEXT_DATA__ is not JSON") from exc
    state = ((payload.get("props") or {}).get("pageProps") or {}).get("initialState")
    if not isinstance(state, dict):
        raise SourceError(f"{url}: __NEXT_DATA__ carries no initialState")
    return state


def _location(job: dict[str, Any]) -> str:
    city = job.get("city") or {}
    parts = [city.get("cityName"), city.get("regionName"), city.get("countryName")]
    text = ", ".join(str(part) for part in parts if part)
    if (job.get("workplaceType") or "").upper() == "REMOTE":
        text = f"{text} (Remote)" if text else "Remote"
    return text


def _description(job: dict[str, Any]) -> str | None:
    """Prefer join.com's own sections; they are what the advert actually shows."""
    sections = [
        ("", job.get("intro")),
        ("## Tasks", job.get("tasks")),
        ("## Requirements", job.get("requirements")),
        ("## Benefits", job.get("benefits")),
    ]
    parts = []
    for heading, body in sections:
        text = html_to_markdown(body)
        if text:
            parts.append(f"{heading}\n\n{text}".strip())
    if parts:
        return "\n\n".join(parts)
    return html_to_markdown(job.get("description"))


def fetch(
    company: CompanySourceConfig,
    user_agent: str | None,
    timeout: float,
    known: KnownIds | None = None,
) -> list[dict[str, Any]]:
    url = BASE.format(slug=company.slug)
    state = _next_data(
        http_get(url, user_agent=user_agent, timeout=timeout, headers={"Accept": "text/html"}).text,
        url,
    )
    listing = (state.get("jobs") or {}).get("items") or []

    kept = [job for job in listing if location_kept(_location(job), company.locations)]
    ids = [str(job["id"]) for job in kept if job.get("id") is not None]
    already_stored = known(ids) if known else set()

    records: list[dict[str, Any]] = []
    details_fetched = 0
    for job in kept:
        job_id = job.get("id")
        external_id = str(job_id) if job_id is not None else None
        id_param = job.get("idParam") or ""
        # No shared fallback: every row pointing at the company page would
        # give them all one posting key. None lets posting_key use the id.
        job_url = f"{url}/{id_param}" if id_param else None
        detail: dict[str, Any] = {}
        if job_url and external_id not in already_stored and details_fetched < MAX_DETAILS:
            details_fetched += 1
            try:
                page = _next_data(
                    http_get(
                        job_url,
                        user_agent=user_agent,
                        timeout=timeout,
                        headers={"Accept": "text/html"},
                    ).text,
                    job_url,
                )
                detail = page.get("job") or {}
            except SourceError:
                detail = {}
        merged = {**job, **detail}
        employment = merged.get("employmentType") or {}
        records.append(
            {
                "title": merged.get("title") or "",
                "company": company.name,
                "location": _location(merged),
                "source": "joincom",
                "external_id": external_id,
                "job_url": job_url,
                "description": _description(merged) if detail else None,
                "date_posted": to_date(merged.get("createdAt")),
                "job_type": employment.get("googleType") or employment.get("name"),
                "is_remote": remote_flag((merged.get("workplaceType") or "").upper() == "REMOTE"),
                "company_url": url,
                "raw_json": raw_json(merged),
            }
        )
    return records
