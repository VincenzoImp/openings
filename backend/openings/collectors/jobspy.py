"""Typed, bounded saved searches using the attributed JobSpy 1.4.1 subset."""

from __future__ import annotations

from typing import Literal
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .._vendor.jobspy.model import Country, DescriptionFormat, JobType, ScraperInput, Site
from ..errors import DomainError

SEARCH_PROVIDERS = ("linkedin", "indeed", "glassdoor")


class JobSpyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=300)
    location: str = Field(default="", max_length=300)
    country: str = Field(default="usa", max_length=100)
    providers: list[Literal["linkedin", "indeed", "glassdoor"]] = Field(
        default_factory=lambda: list(SEARCH_PROVIDERS), min_length=1, max_length=3
    )
    results_wanted: int = Field(default=20, ge=1, le=50)
    hours_old: int = Field(default=72, ge=1, le=24 * 365)
    is_remote: bool = False
    job_type: (
        Literal[
            "fulltime",
            "parttime",
            "contract",
            "temporary",
            "internship",
            "perdiem",
            "other",
            "volunteer",
        ]
        | None
    ) = None

    @field_validator("query")
    @classmethod
    def clean_query(cls, value):
        if not value.strip():
            raise ValueError("Enter one explicit search query.")
        return value.strip()

    @field_validator("country")
    @classmethod
    def valid_country(cls, value):
        return Country(value).value

    @field_validator("providers")
    @classmethod
    def unique_providers(cls, value):
        return list(dict.fromkeys(value))


def request_estimate(config, preview=False):
    cfg = JobSpyConfig.model_validate(config)
    count = min(cfg.results_wanted, 3) if preview else cfg.results_wanted
    providers = []
    for provider in cfg.providers:
        if provider == "linkedin":
            minimum, maximum = 1, (count + 9) // 10 + count
        elif provider == "glassdoor":
            minimum, maximum = 1, 2 + (count + 24) // 25
        else:
            minimum = maximum = 1
        providers.append({"id": provider, "min": minimum, "max": maximum})
    return {
        "total": sum(value["max"] for value in providers),
        "providers": providers,
        "note": "Estimate excludes redirects and transport errors; shared request spacing and server cooldowns apply.",
    }


def collect(config, provider, budget, *, preview=False, source=None):
    cfg = JobSpyConfig.model_validate(config)
    if provider not in cfg.providers:
        raise DomainError(422, "source_provider", "This provider is not part of the saved search.")
    # Loading only the configured provider avoids dataframe and unrelated portal code.
    if provider == "linkedin":
        from .._vendor.jobspy.linkedin import LinkedIn

        cls = LinkedIn
    elif provider == "indeed":
        from .._vendor.jobspy.indeed import Indeed

        cls = Indeed
    else:
        from .._vendor.jobspy.glassdoor import Glassdoor

        cls = Glassdoor
    source = source or {}
    scraper = cls(transport=budget)
    scraper.checkpoint = source.setdefault("checkpoint", {}) if not preview else {}
    scraper.on_checkpoint = source.get("on_checkpoint") if not preview else None
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    scraper.known_postings = {
        key: value
        for key, value in (source.get("known_postings") or {}).items()
        if (source.get("detail_checked") or {}).get(key, "") > cutoff
    }
    scraper_input = ScraperInput(
        site_name=[Site(provider)],
        search_term=cfg.query,
        location=cfg.location or None,
        country_indeed=Country(cfg.country),
        is_remote=cfg.is_remote,
        job_type=JobType(cfg.job_type) if cfg.job_type else None,
        results_wanted=min(cfg.results_wanted, 3) if preview else cfg.results_wanted,
        hours_old=cfg.hours_old,
        fetch_description=True,
        description_format=DescriptionFormat.PLAIN,
    )
    try:
        rows = scraper.scrape(scraper_input)
    finally:
        session = getattr(scraper, "session", None)
        if session is not None:
            session.close()
    items = []
    for row in rows:
        raw = row.model_dump(mode="json")
        description = row.description or ""
        complete = (
            any(character.isalnum() for character in description) and len(description) <= 200000
        )
        if cfg.is_remote and row.is_remote is False:
            continue
        if cfg.job_type and row.job_type and JobType(cfg.job_type) not in row.job_type:
            continue
        items.append(
            {
                "title": row.title[:400],
                "company": (row.company or "")[:300],
                "location": row.location.display_location()[:500] if row.location else "",
                "url": row.job_url,
                "posting": description[:200000],
                "source_key": f"{provider}:{row.id or row.job_url}",
                "metadata": {
                    "source": provider,
                    "collector": "jobspy",
                    "collector_version": "1.4.1",
                    "is_remote": row.is_remote,
                    "job_type": row.job_type[0].value if row.job_type else None,
                    "job_types": [value.value for value in row.job_type] if row.job_type else [],
                    "date_posted": raw.get("date_posted"),
                    "salary": {
                        key: raw[key]
                        for key in ("interval", "min_amount", "max_amount", "currency")
                        if raw.get(key) is not None
                    },
                    "external_id": row.id,
                    "description_complete": complete,
                    "description_status": "complete"
                    if complete
                    else "truncated"
                    if len(description) > 200000
                    else "pending"
                    if scraper.checkpoint.get("pending_details")
                    else "unavailable",
                },
                "raw": raw,
            }
        )
    source.setdefault("detail_checks", {}).update(
        {
            item["source_key"]: datetime.now(timezone.utc).isoformat(timespec="microseconds")
            for item in items
            if item["posting"] and item["source_key"] not in scraper.known_postings
        }
    )
    if source.get("on_item"):
        source["streamed"] = True
        for item in items:
            source["on_item"](item)
    if scraper.checkpoint.get("complete"):
        scraper.checkpoint["unavailable_descriptions"] = sum(
            not item["metadata"]["description_complete"] for item in items
        )
        scraper.checkpoint.pop("jobs", None)
        scraper.checkpoint.pop("detail_attempts", None)
        if scraper.on_checkpoint:
            scraper.on_checkpoint(scraper.checkpoint)
    diagnostic = budget.diagnostics()
    if scraper.error and budget.blocked is None:
        diagnostic.update(state="error", message=scraper.error[:500])
    if scraper.warnings:
        diagnostic["warnings"] = scraper.warnings
        if not items and diagnostic["state"] == "ok":
            diagnostic.update(state="warning", message="; ".join(scraper.warnings)[:500])
    # A challenge or schema error must not appear as a successful empty search.
    if diagnostic["state"] == "error":
        raise DomainError(
            403 if scraper.error_code == "provider_access" else 502,
            scraper.error_code or "provider_response",
            f"{provider}: {diagnostic['message']}",
            diagnostic,
        )
    return items, diagnostic
