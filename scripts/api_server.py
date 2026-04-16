"""REST API server for the Job Search Tool.

Thin CRUD wrapper over JobDatabase and JobVectorStore. Designed for scripts,
automations, and external tools that need programmatic access to the job
database.

Run: ``python api_server.py`` (listens on port 8502).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import JobDatabase
from logger import get_logger
from models import JobDBRecord

if TYPE_CHECKING:
    from vector_store import JobVectorStore

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("JOB_SEARCH_DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "db" / "jobs.db"
CHROMA_PATH = DATA_DIR / "chroma"

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    job_url: str | None = None
    site: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    description: str | None = None
    date_posted: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    company_url: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    relevance_score: int = 0
    applied: bool = False
    bookmarked: bool = False


class HealthResponse(BaseModel):
    status: str
    jobs_count: int


class StatsResponse(BaseModel):
    total_jobs: int
    seen_today: int
    new_today: int
    applied: int
    blacklisted: int
    avg_relevance_score: float


class DeleteResponse(BaseModel):
    deleted: bool


class BulkDeleteResponse(BaseModel):
    deleted_count: int


class SemanticResultResponse(BaseModel):
    job_id: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    similarity: float
    relevance_score: int | None = None
    site: str | None = None
    job_url: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

logger = get_logger("api")

_db: JobDatabase | None = None
_vs: JobVectorStore | None = None


def _record_to_response(record: JobDBRecord) -> JobResponse:
    """Convert a frozen dataclass to the Pydantic response model."""
    d = asdict(record)  # type: ignore[arg-type]
    # Stringify dates for JSON serialisation
    for key in ("date_posted", "first_seen", "last_seen"):
        val = d.get(key)
        if val is not None and hasattr(val, "isoformat"):
            d[key] = val.isoformat()
    return JobResponse(**d)


def _semantic_to_response(sr: object) -> SemanticResultResponse:
    meta = getattr(sr, "metadata", None) or {}
    return SemanticResultResponse(
        job_id=getattr(sr, "job_id", ""),
        title=meta.get("title"),
        company=meta.get("company"),
        location=meta.get("location"),
        similarity=round(getattr(sr, "similarity", 0.0), 4),
        relevance_score=meta.get("relevance_score"),
        site=meta.get("site"),
        job_url=meta.get("job_url"),
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _db, _vs
    logger.info("API server starting | DB: %s | Chroma: %s", DB_PATH, CHROMA_PATH)
    _db = JobDatabase(DB_PATH)
    try:
        from vector_store import get_vector_store

        _vs = get_vector_store(CHROMA_PATH)
    except Exception as exc:
        logger.warning("Vector store unavailable: %s", exc)
        _vs = None
    yield
    if _db is not None:
        _db.close()


app = FastAPI(
    title="Job Search Tool API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_db() -> JobDatabase:
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _db


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db = _get_db()
    return HealthResponse(status="ok", jobs_count=db.get_job_count())


@app.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_score: int | None = None,
    max_score: int | None = None,
    site: str | None = None,
    company: str | None = None,
    bookmarked: bool | None = None,
    applied: bool | None = None,
    sort: str = Query("score", pattern="^(score|date)$"),
) -> list[JobResponse]:
    db = _get_db()
    all_jobs = db.get_all_jobs()

    # Filter
    filtered = all_jobs
    if min_score is not None:
        filtered = [j for j in filtered if j.relevance_score >= min_score]
    if max_score is not None:
        filtered = [j for j in filtered if j.relevance_score <= max_score]
    if site is not None:
        site_lower = site.lower()
        filtered = [j for j in filtered if (j.site or "").lower() == site_lower]
    if company is not None:
        company_lower = company.lower()
        filtered = [j for j in filtered if company_lower in (j.company or "").lower()]
    if bookmarked is not None:
        filtered = [j for j in filtered if j.bookmarked == bookmarked]
    if applied is not None:
        filtered = [j for j in filtered if j.applied == applied]

    # Sort
    if sort == "score":
        filtered.sort(key=lambda j: j.relevance_score, reverse=True)
    else:
        filtered.sort(
            key=lambda j: (
                (j.date_posted or j.first_seen).isoformat()
                if (j.date_posted or j.first_seen)
                else ""
            ),
            reverse=True,
        )

    # Paginate
    page = filtered[offset : offset + limit]
    return [_record_to_response(j) for j in page]


@app.get("/jobs/search/semantic", response_model=list[SemanticResultResponse])
def search_semantic(
    q: str = Query(..., min_length=1),
    n_results: int = Query(20, ge=1, le=200),
    min_score: int | None = None,
    site: str | None = None,
) -> list[SemanticResultResponse]:
    if _vs is None:
        raise HTTPException(status_code=503, detail="Vector store not available")
    results = _vs.search(query=q, n_results=n_results, min_score=min_score, site=site)  # type: ignore[union-attr]
    return [_semantic_to_response(r) for r in results]


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    db = _get_db()
    record = db.get_job_by_id(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _record_to_response(record)


@app.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    db = _get_db()
    stats = db.get_statistics()
    return StatsResponse(**stats)


@app.get("/distribution")
def get_distribution(
    bin_size: int = Query(5, ge=1, le=100),
) -> list[list[int]]:
    db = _get_db()
    return [list(pair) for pair in db.get_score_distribution(bin_size)]


@app.post("/jobs/{job_id}/bookmark", response_model=JobResponse)
def toggle_bookmark(job_id: str) -> JobResponse:
    db = _get_db()
    try:
        db.toggle_bookmark(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    record = db.get_job_by_id(job_id)
    assert record is not None
    return _record_to_response(record)


@app.post("/jobs/{job_id}/apply", response_model=JobResponse)
def toggle_apply(job_id: str) -> JobResponse:
    db = _get_db()
    try:
        db.toggle_applied(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    record = db.get_job_by_id(job_id)
    assert record is not None
    return _record_to_response(record)


@app.delete("/jobs/{job_id}", response_model=DeleteResponse)
def delete_job(job_id: str) -> DeleteResponse:
    db = _get_db()
    deleted = db.blacklist_job(job_id)
    return DeleteResponse(deleted=deleted)


@app.delete("/jobs/below-score/{score}", response_model=BulkDeleteResponse)
def delete_below_score(score: int) -> BulkDeleteResponse:
    db = _get_db()
    count = db.delete_jobs_below_score(score)
    return BulkDeleteResponse(deleted_count=count)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8502)
