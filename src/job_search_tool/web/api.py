"""REST API routes for the unified web server."""

from __future__ import annotations

from dataclasses import asdict
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from job_search_tool.application.jobs import JobApplicationService
from job_search_tool.application.models import (
    CleanupPreview,
    JobCommandResult,
    JobListQuery,
)
from job_search_tool.config import get_config
from job_search_tool.job_service import get_db, get_vs, record_to_dict


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


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    limit: int
    offset: int


class BookmarkRequest(BaseModel):
    bookmarked: bool


class AppliedRequest(BaseModel):
    applied: bool


class BlacklistRequest(BaseModel):
    job_ids: list[str]


class JobCommandResponse(BaseModel):
    success: bool
    affected_count: int = 0
    job_id: str | None = None
    bookmarked: bool | None = None
    applied: bool | None = None
    message: str | None = None


class CleanupResponse(BaseModel):
    deleted_below_score: int
    deleted_stale: int
    purged_blacklist: int
    protected_bookmarked: int
    protected_applied: int
    total_deleted: int


class StatsResponse(BaseModel):
    total_jobs: int
    seen_today: int
    new_today: int
    applied: int
    blacklisted: int
    avg_relevance_score: float


class SemanticResultResponse(BaseModel):
    job_id: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    similarity: float
    relevance_score: int | None = None
    site: str | None = None
    job_url: str | None = None


class DashboardAuthResponse(BaseModel):
    token_required: bool


def _configured_api_token() -> str:
    return os.environ.get("JOB_SEARCH_API_TOKEN", "").strip()


def _token_matches(candidate: str | None, expected: str) -> bool:
    if not candidate:
        return False
    return hmac.compare_digest(candidate, expected)


def require_api_token(
    authorization: str | None = Header(default=None),
    x_job_search_token: str | None = Header(
        default=None,
        alias="X-Job-Search-Token",
    ),
) -> None:
    """Require a bearer token only when JOB_SEARCH_API_TOKEN is configured."""
    token = _configured_api_token()
    if not token:
        return

    bearer_token = None
    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization.removeprefix("Bearer ").strip()

    if _token_matches(bearer_token, token) or _token_matches(x_job_search_token, token):
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _service() -> JobApplicationService:
    return JobApplicationService(get_db())


def _command_response(result: JobCommandResult) -> JobCommandResponse:
    return JobCommandResponse(**asdict(result))


def _cleanup_response(cleanup: CleanupPreview) -> CleanupResponse:
    return CleanupResponse(**asdict(cleanup), total_deleted=cleanup.total_deleted)


public_router = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])


@public_router.get("/dashboard/auth", response_model=DashboardAuthResponse)
def get_dashboard_auth() -> DashboardAuthResponse:
    return DashboardAuthResponse(token_required=bool(_configured_api_token()))


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_score: int | None = None,
    max_score: int | None = None,
    site: str | None = None,
    company: str | None = None,
    bookmarked: bool | None = None,
    applied: bool | None = None,
    remote: bool | None = None,
    job_type: str | None = None,
    text: str | None = None,
    sort: str = Query("score", pattern="^(score|date)$"),
) -> JobListResponse:
    result = _service().list_jobs(
        JobListQuery(
            limit=limit,
            offset=offset,
            min_score=min_score,
            max_score=max_score,
            site=site,
            company=company,
            bookmarked=bookmarked,
            applied=applied,
            remote=remote,
            job_type=job_type,
            text=text,
            sort="date" if sort == "date" else "score",
        )
    )
    return JobListResponse(
        items=[JobResponse(**record_to_dict(job)) for job in result.jobs],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    record = _service().get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**record_to_dict(record))


@router.get("/jobs/search/semantic", response_model=list[SemanticResultResponse])
def search_semantic(
    q: str = Query(..., min_length=1),
    n_results: int = Query(20, ge=1, le=200),
    min_score: int | None = None,
    site: str | None = None,
) -> list[SemanticResultResponse]:
    vs = get_vs()
    if vs is None:
        raise HTTPException(status_code=503, detail="Vector store not available")

    results = vs.search(query=q, n_results=n_results, min_score=min_score, site=site)
    return [
        SemanticResultResponse(
            job_id=result.job_id,
            title=result.metadata.get("title"),
            company=result.metadata.get("company"),
            location=result.metadata.get("location"),
            similarity=round(result.similarity, 4),
            relevance_score=result.metadata.get("relevance_score"),
            site=result.metadata.get("site"),
            job_url=result.metadata.get("job_url"),
        )
        for result in results
    ]


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    return StatsResponse(**get_db().get_statistics())


@router.get("/distribution")
def get_distribution(bin_size: int = Query(5, ge=1, le=100)) -> list[list[int]]:
    return [list(pair) for pair in get_db().get_score_distribution(bin_size)]


@router.put("/jobs/{job_id}/bookmark", response_model=JobCommandResponse)
def set_bookmark(job_id: str, payload: BookmarkRequest) -> JobCommandResponse:
    result = _service().set_bookmarked(job_id, payload.bookmarked)
    if not result.success:
        raise HTTPException(status_code=404, detail="Job not found")
    return _command_response(result)


@router.put("/jobs/{job_id}/applied", response_model=JobCommandResponse)
def set_applied(job_id: str, payload: AppliedRequest) -> JobCommandResponse:
    result = _service().set_applied(job_id, payload.applied)
    if not result.success:
        raise HTTPException(status_code=404, detail="Job not found")
    return _command_response(result)


@router.post("/jobs/blacklist", response_model=JobCommandResponse)
def blacklist_jobs(payload: BlacklistRequest) -> JobCommandResponse:
    result = _service().blacklist_jobs(payload.job_ids)
    return _command_response(result)


@router.get("/cleanup/preview", response_model=CleanupResponse)
def preview_cleanup() -> CleanupResponse:
    return _cleanup_response(_service().preview_cleanup(get_config()))


@router.post("/cleanup/run", response_model=CleanupResponse)
def run_cleanup() -> CleanupResponse:
    return _cleanup_response(_service().run_cleanup(get_config()))
