"""JobCloud search API: ``https://{host}/api/v1/public/search``.

JobCloud runs several regional job boards from one engine (jobs.ch, jobup.ch),
so the host is configuration rather than a constant: pointing a second source at
a sibling domain costs no code. The API is public and unauthenticated but
undocumented, which is why every request shape here is conservative and every
loop is capped.

Two things make it worth a dedicated source. The search returns only a
truncated ``preview``, so the full copy needs a second request per posting,
capped and skipped for postings already stored. And it reports language
requirements structurally, as ``language_skills``, rather than leaving them
buried in the advert; that is turned into one canonical line at the top of the
description so a keyword category can match a stated fact instead of guessing
at phrasings. The line is deliberately language-agnostic: the tool states what
the employer asked for, and the operator decides which languages matter.

``locations`` is the board's own search parameter, not a post-filter. The board
already resolves a city to its commuting region, so filtering its answers again
by city name would discard exactly the neighbouring towns the operator asked
for by naming the city. The board is answered faster than it is polite to ask,
so requests are spaced.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from openings.models import SourceRunStats
from openings.sources.base import (
    SourceError,
    SourceResult,
    frame_from_records,
    html_to_markdown,
    http_get_json,
    raw_json,
    to_date,
)

if TYPE_CHECKING:
    from openings.config import Config
    from openings.sources.collect import KnownExternalIds

SEARCH = "https://{host}/api/v1/public/search"
DETAIL = "https://{host}/api/v1/public/search/job/{job_id}"
SOURCE_NAME = "jobcloud"

# Configuration is an input, not a promise. The board has thousands of result
# pages, so a generous max_pages in someone's settings file must not turn into
# thousands of requests per query per location.
MAX_ROWS = 100
MAX_PAGES = 20
MAX_DETAILS = 200

# The board answers HTTP 422 to a client that asks too quickly. A failed
# request is reported rather than swallowed, but a run that trips the limit
# collects nothing useful, so requests are spaced by default.
DELAY_SECONDS = 1.5

LANGUAGE_NAMES = {
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
}


def _language_line(document: dict[str, Any]) -> str | None:
    """One canonical line naming the languages the employer asked for.

    Keyword scoring otherwise has to guess at phrasings such as "gute
    Deutschkenntnisse"; this states the requirement the same way every time, so
    a category can match it exactly.
    """
    skills = document.get("language_skills") or []
    parts = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        code = str(skill.get("language") or "").lower()
        name = LANGUAGE_NAMES.get(code, code.upper() or "unknown")
        level = skill.get("level")
        parts.append(f"{name} (level {level})" if level is not None else name)
    return f"Required languages: {', '.join(parts)}" if parts else None


def _job_url(document: dict[str, Any], host: str) -> str | None:
    links = document.get("_links") or {}
    for key in ("detail_en", "detail_de", "detail_fr", "detail_it"):
        href = (links.get(key) or {}).get("href")
        if href:
            return href
    slug = document.get("slug")
    return f"https://{host}/en/vacancies/detail/{slug}/" if slug else None


def _record(document: dict[str, Any], host: str, detail: dict[str, Any] | None) -> dict[str, Any]:
    body = None
    if detail:
        body = html_to_markdown(detail.get("job_content") or detail.get("content")) or detail.get(
            "preview"
        )
    body = body or document.get("preview")
    language_line = _language_line(document)
    if language_line:
        body = f"{language_line}\n\n{body}" if body else language_line
    grades = document.get("employment_grades") or []
    return {
        "title": document.get("title") or "",
        "company": document.get("company_name") or "",
        "location": document.get("place") or "",
        "source": SOURCE_NAME,
        "external_id": document.get("job_id"),
        "job_url": _job_url(document, host),
        "description": body,
        "date_posted": to_date(
            document.get("publication_date") or document.get("initial_publication_date")
        ),
        "job_type": "fulltime" if grades and max(grades) >= 90 else None,
        "raw_json": raw_json(document),
    }


def run_jobcloud(config: Config, known: KnownExternalIds | None = None) -> SourceResult:
    settings = config.sources.jobcloud
    stats = SourceRunStats(name=SOURCE_NAME)
    if not settings.enabled:
        return SourceResult(stats=stats)

    locations = settings.locations or [""]
    rows = min(settings.rows, MAX_ROWS)
    pages = min(settings.max_pages, MAX_PAGES)
    detail_budget = min(settings.max_details, MAX_DETAILS)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    details_fetched = 0

    for query in settings.queries or [""]:
        for where in locations:
            stats.tasks += 1
            try:
                for page in range(1, pages + 1):
                    params: dict[str, Any] = {"rows": rows, "page": page}
                    if query:
                        params["query"] = query
                    if where:
                        params["location"] = where
                    time.sleep(DELAY_SECONDS)
                    payload = http_get_json(
                        SEARCH.format(host=settings.host),
                        user_agent=config.sources.user_agent,
                        timeout=config.sources.timeout_seconds,
                        params=params,
                    )
                    documents = payload.get("documents") or []
                    fresh = [
                        str(document.get("job_id") or "")
                        for document in documents
                        if document.get("job_id")
                    ]
                    already_stored = known(SOURCE_NAME, fresh) if known else set()
                    for document in documents:
                        job_id = str(document.get("job_id") or "")
                        if not job_id or job_id in seen:
                            continue
                        seen.add(job_id)
                        detail = None
                        if job_id not in already_stored and details_fetched < detail_budget:
                            details_fetched += 1
                            time.sleep(DELAY_SECONDS)
                            try:
                                detail = http_get_json(
                                    DETAIL.format(host=settings.host, job_id=job_id),
                                    user_agent=config.sources.user_agent,
                                    timeout=config.sources.timeout_seconds,
                                )
                            except SourceError:
                                detail = None
                        records.append(_record(document, settings.host, detail))
                    if len(documents) < rows:
                        break
                stats.succeeded += 1
            except SourceError as exc:
                stats.failed += 1
                stats.errors.append(f"{query or 'anything'} @ {where or 'anywhere'}: {exc}")

    frame = frame_from_records(records)
    stats.rows = len(frame)
    return SourceResult(stats=stats, frame=frame)
