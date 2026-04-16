"""Shared service layer for the Job Search Tool server frontends.

Provides DB/vector-store initialization, record serialization, and filtering
logic used by the dashboard, REST API, and MCP server. Each frontend is a
thin adapter that translates between this module and its framework.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from config import DATA_DIR
from database import JobDatabase
from logger import get_logger
from models import JobDBRecord

if TYPE_CHECKING:
    from vector_store import JobVectorStore

# ---------------------------------------------------------------------------
# Paths (derived from config.DATA_DIR — respects JOB_SEARCH_DATA_DIR env var)
# ---------------------------------------------------------------------------

DB_PATH = DATA_DIR / "db" / "jobs.db"
CHROMA_PATH = DATA_DIR / "chroma"

logger = get_logger("service")

# ---------------------------------------------------------------------------
# DB and vector store initialization
# ---------------------------------------------------------------------------

_db: JobDatabase | None = None
_vs: JobVectorStore | None = None
_vs_attempted: bool = False


def get_db() -> JobDatabase:
    """Return the shared JobDatabase singleton (created on first call)."""
    global _db
    if _db is None:
        _db = JobDatabase(DB_PATH)
    return _db


def get_vs() -> JobVectorStore | None:
    """Return the shared JobVectorStore singleton, or None if unavailable."""
    global _vs, _vs_attempted
    if not _vs_attempted:
        _vs_attempted = True
        try:
            from vector_store import get_vector_store

            _vs = get_vector_store(CHROMA_PATH)
        except Exception as exc:
            logger.warning("Vector store unavailable: %s", exc)
            _vs = None
    return _vs


def close_db() -> None:
    """Close the DB connection (for clean shutdown)."""
    global _db
    if _db is not None:
        _db.close()
        _db = None


def reset_singletons() -> None:
    """Reset all singletons (for testing)."""
    global _db, _vs, _vs_attempted
    _db = None
    _vs = None
    _vs_attempted = False


# ---------------------------------------------------------------------------
# Record serialization
# ---------------------------------------------------------------------------

_DATE_FIELDS = ("date_posted", "first_seen", "last_seen")


def record_to_dict(r: JobDBRecord) -> dict:
    """Full record with dates serialized to ISO strings."""
    d = asdict(r)  # type: ignore[arg-type]
    for key in _DATE_FIELDS:
        val = d.get(key)
        if val is not None and hasattr(val, "isoformat"):
            d[key] = val.isoformat()
    return d


def record_to_summary(r: JobDBRecord) -> dict:
    """Compact summary without description (for list views)."""
    return {
        "job_id": r.job_id,
        "title": r.title,
        "company": r.company,
        "location": r.location,
        "relevance_score": r.relevance_score,
        "site": r.site,
        "bookmarked": r.bookmarked,
        "applied": r.applied,
        "first_seen": r.first_seen.isoformat() if r.first_seen else None,
        "job_url": r.job_url,
    }


# ---------------------------------------------------------------------------
# Filtering and sorting
# ---------------------------------------------------------------------------


def filter_jobs(
    jobs: list[JobDBRecord],
    *,
    min_score: int | None = None,
    max_score: int | None = None,
    site: str | None = None,
    company: str | None = None,
    bookmarked: bool | None = None,
    applied: bool | None = None,
) -> list[JobDBRecord]:
    """Apply common filters to a list of job records."""
    result = jobs
    if min_score is not None:
        result = [j for j in result if j.relevance_score >= min_score]
    if max_score is not None:
        result = [j for j in result if j.relevance_score <= max_score]
    if site is not None:
        site_lower = site.lower()
        result = [j for j in result if (j.site or "").lower() == site_lower]
    if company is not None:
        company_lower = company.lower()
        result = [j for j in result if company_lower in (j.company or "").lower()]
    if bookmarked is not None:
        result = [j for j in result if j.bookmarked == bookmarked]
    if applied is not None:
        result = [j for j in result if j.applied == applied]
    return result


def sort_jobs_by_score(jobs: list[JobDBRecord]) -> list[JobDBRecord]:
    """Sort jobs by relevance score descending (in place for efficiency)."""
    jobs.sort(key=lambda j: j.relevance_score, reverse=True)
    return jobs


def sort_jobs_by_date(jobs: list[JobDBRecord]) -> list[JobDBRecord]:
    """Sort jobs by most recent date descending (in place for efficiency)."""
    jobs.sort(
        key=lambda j: (
            (j.date_posted or j.first_seen).isoformat()
            if (j.date_posted or j.first_seen)
            else ""
        ),
        reverse=True,
    )
    return jobs
