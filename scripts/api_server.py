"""REST API server for the Job Search Tool.

Thin FastAPI adapter over the shared job_service layer. Designed for scripts,
automations, and external tools that need programmatic access to the job
database.

Run: ``python api_server.py`` (listens on port 8502).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from job_service import (
    close_db,
    filter_jobs,
    get_db,
    get_vs,
    logger,
    record_to_dict,
    sort_jobs_by_date,
    sort_jobs_by_score,
)

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
# Application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    db = get_db()
    vs = get_vs()
    logger.info(
        "API server ready | %d jobs | vector store %s",
        db.get_job_count(),
        "available" if vs else "unavailable",
    )
    yield
    close_db()


app = FastAPI(
    title="Job Search Tool API",
    version="7.1.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", jobs_count=get_db().get_job_count())


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
    filtered = filter_jobs(
        get_db().get_all_jobs(),
        min_score=min_score,
        max_score=max_score,
        site=site,
        company=company,
        bookmarked=bookmarked,
        applied=applied,
    )
    if sort == "score":
        sort_jobs_by_score(filtered)
    else:
        sort_jobs_by_date(filtered)

    page = filtered[offset : offset + limit]
    return [JobResponse(**record_to_dict(j)) for j in page]


@app.get("/jobs/search/semantic", response_model=list[SemanticResultResponse])
def search_semantic(
    q: str = Query(..., min_length=1),
    n_results: int = Query(20, ge=1, le=200),
    min_score: int | None = None,
    site: str | None = None,
) -> list[SemanticResultResponse]:
    vs = get_vs()
    if vs is None:
        raise HTTPException(status_code=503, detail="Vector store not available")
    results = vs.search(query=q, n_results=n_results, min_score=min_score, site=site)  # type: ignore[union-attr]
    return [
        SemanticResultResponse(
            job_id=r.job_id,
            title=r.metadata.get("title"),
            company=r.metadata.get("company"),
            location=r.metadata.get("location"),
            similarity=round(r.similarity, 4),
            relevance_score=r.metadata.get("relevance_score"),
            site=r.metadata.get("site"),
            job_url=r.metadata.get("job_url"),
        )
        for r in results
    ]


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    record = get_db().get_job_by_id(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**record_to_dict(record))


@app.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    return StatsResponse(**get_db().get_statistics())


@app.get("/distribution")
def get_distribution(
    bin_size: int = Query(5, ge=1, le=100),
) -> list[list[int]]:
    return [list(pair) for pair in get_db().get_score_distribution(bin_size)]


@app.post("/jobs/{job_id}/bookmark", response_model=JobResponse)
def toggle_bookmark(job_id: str) -> JobResponse:
    db = get_db()
    try:
        db.toggle_bookmark(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    record = db.get_job_by_id(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**record_to_dict(record))


@app.post("/jobs/{job_id}/apply", response_model=JobResponse)
def toggle_apply(job_id: str) -> JobResponse:
    db = get_db()
    try:
        db.toggle_applied(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    record = db.get_job_by_id(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**record_to_dict(record))


@app.delete("/jobs/{job_id}", response_model=DeleteResponse)
def delete_job(job_id: str) -> DeleteResponse:
    return DeleteResponse(deleted=get_db().blacklist_job(job_id))


@app.delete("/jobs/below-score/{score}", response_model=BulkDeleteResponse)
def delete_below_score(score: int) -> BulkDeleteResponse:
    return BulkDeleteResponse(deleted_count=get_db().delete_jobs_below_score(score))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8502)
