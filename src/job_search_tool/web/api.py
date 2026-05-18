"""REST API routes for the unified web server."""

from __future__ import annotations

from dataclasses import asdict
import hmac
import os
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from job_search_tool.application.jobs import (
    JobApplicationService,
    VectorStoreUnavailableError,
)
from job_search_tool.application.models import (
    BlacklistListQuery,
    CleanupPreview,
    JobExportFormat,
    JobCommandResult,
    JobListQuery,
    JobSort,
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


class JobIdsRequest(BaseModel):
    job_ids: list[str]


class BulkBookmarkRequest(JobIdsRequest):
    bookmarked: bool


class BulkAppliedRequest(JobIdsRequest):
    applied: bool


class BlacklistPurgeRequest(BaseModel):
    older_than_days: int | None = None


class CleanupBelowScoreRequest(BaseModel):
    score: int


class CleanupStaleRequest(BaseModel):
    days: int


class ExportJobsRequest(BaseModel):
    job_ids: list[str] | None = None
    format: str = "csv"


class JobCommandResponse(BaseModel):
    success: bool
    affected_count: int = 0
    job_ids: list[str] = Field(default_factory=list)
    bookmarked: bool | None = None
    applied: bool | None = None
    message: str | None = None


class BlacklistedJobResponse(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    blacklisted_at: str


class BlacklistListResponse(BaseModel):
    items: list[BlacklistedJobResponse]
    total: int
    limit: int
    offset: int


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
    return JobApplicationService(get_db(), vector_store_factory=get_vs)


def _command_response(result: JobCommandResult) -> JobCommandResponse:
    return JobCommandResponse(**asdict(result))


def _cleanup_response(cleanup: CleanupPreview) -> CleanupResponse:
    return CleanupResponse(**asdict(cleanup), total_deleted=cleanup.total_deleted)


def _sort_value(sort: str) -> JobSort:
    allowed = {"score", "date", "company", "title", "salary"}
    if sort not in allowed:
        raise HTTPException(status_code=422, detail="Invalid sort")
    return cast(JobSort, sort)


def _export_format(value: str) -> JobExportFormat:
    if value not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    return cast(JobExportFormat, value)


def _export_response(exported) -> Response:
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{exported.filename}"',
            "X-Job-Search-Export-Count": str(exported.row_count),
        },
    )


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
    sites: list[str] | None = Query(default=None),
    company: str | None = None,
    location: str | None = None,
    locations: list[str] | None = Query(default=None),
    bookmarked: bool | None = None,
    applied: bool | None = None,
    remote: bool | None = None,
    job_type: str | None = None,
    job_types: list[str] | None = Query(default=None),
    min_salary: float | None = None,
    max_salary: float | None = None,
    date_posted_from: str | None = None,
    date_posted_to: str | None = None,
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    last_seen_from: str | None = None,
    last_seen_to: str | None = None,
    text: str | None = None,
    sort: str = Query("score", pattern="^(score|date|company|title|salary)$"),
) -> JobListResponse:
    result = _service().list_jobs(
        JobListQuery(
            limit=limit,
            offset=offset,
            min_score=min_score,
            max_score=max_score,
            site=site,
            sites=sites,
            company=company,
            location=location,
            locations=locations,
            bookmarked=bookmarked,
            applied=applied,
            remote=remote,
            job_type=job_type,
            job_types=job_types,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted_from=date_posted_from,
            date_posted_to=date_posted_to,
            first_seen_from=first_seen_from,
            first_seen_to=first_seen_to,
            last_seen_from=last_seen_from,
            last_seen_to=last_seen_to,
            text=text,
            sort=_sort_value(sort),
        )
    )
    return JobListResponse(
        items=[JobResponse(**record_to_dict(job)) for job in result.jobs],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.get("/jobs/facets")
def get_job_facets() -> dict[str, list[dict[str, object]]]:
    return _service().get_facets()


@router.post("/jobs/bookmark", response_model=JobCommandResponse)
def set_bookmarks(payload: BulkBookmarkRequest) -> JobCommandResponse:
    return _command_response(
        _service().set_bookmarked(payload.job_ids, payload.bookmarked)
    )


@router.post("/jobs/applied", response_model=JobCommandResponse)
def set_applied_bulk(payload: BulkAppliedRequest) -> JobCommandResponse:
    return _command_response(_service().set_applied(payload.job_ids, payload.applied))


@router.post("/jobs/delete", response_model=JobCommandResponse)
def delete_jobs(payload: JobIdsRequest) -> JobCommandResponse:
    return _command_response(_service().delete_jobs(payload.job_ids))


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
    try:
        results = _service().search_similar(
            query=q,
            n_results=n_results,
            min_score=min_score,
            site=site,
        )
    except VectorStoreUnavailableError:
        raise HTTPException(status_code=503, detail="Vector store not available")
    return [
        SemanticResultResponse(
            job_id=result.job_id,
            title=result.title,
            company=result.company,
            location=result.location,
            similarity=round(result.similarity, 4),
            relevance_score=result.relevance_score,
            site=result.site,
            job_url=result.job_url,
        )
        for result in results
    ]


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    stats = _service().get_statistics()
    return StatsResponse(
        total_jobs=int(stats["total_jobs"]),
        seen_today=int(stats["seen_today"]),
        new_today=int(stats["new_today"]),
        applied=int(stats["applied"]),
        blacklisted=int(stats["blacklisted"]),
        avg_relevance_score=float(stats["avg_relevance_score"]),
    )


@router.get("/distribution")
def get_distribution(bin_size: int = Query(5, ge=1, le=100)) -> list[list[int]]:
    return [list(pair) for pair in _service().get_score_distribution(bin_size)]


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


@router.get("/blacklist", response_model=BlacklistListResponse)
def list_blacklisted_jobs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    text: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> BlacklistListResponse:
    result = _service().list_blacklisted_jobs(
        BlacklistListQuery(
            limit=limit,
            offset=offset,
            text=text,
            company=company,
            location=location,
        )
    )
    return BlacklistListResponse(
        items=[BlacklistedJobResponse(**asdict(item)) for item in result.items],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.post("/blacklist", response_model=JobCommandResponse)
def blacklist_jobs_bulk(payload: BlacklistRequest) -> JobCommandResponse:
    return _command_response(_service().blacklist_jobs(payload.job_ids))


@router.post("/blacklist/remove", response_model=JobCommandResponse)
def unblacklist_jobs(payload: JobIdsRequest) -> JobCommandResponse:
    return _command_response(_service().unblacklist_jobs(payload.job_ids))


@router.post("/blacklist/purge", response_model=JobCommandResponse)
def purge_blacklist(payload: BlacklistPurgeRequest) -> JobCommandResponse:
    return _command_response(_service().purge_blacklist(payload.older_than_days))


@router.get("/export/jobs")
def export_jobs(
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_score: int | None = None,
    max_score: int | None = None,
    site: str | None = None,
    sites: list[str] | None = Query(default=None),
    company: str | None = None,
    location: str | None = None,
    locations: list[str] | None = Query(default=None),
    bookmarked: bool | None = None,
    applied: bool | None = None,
    remote: bool | None = None,
    job_type: str | None = None,
    job_types: list[str] | None = Query(default=None),
    min_salary: float | None = None,
    max_salary: float | None = None,
    date_posted_from: str | None = None,
    date_posted_to: str | None = None,
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    last_seen_from: str | None = None,
    last_seen_to: str | None = None,
    text: str | None = None,
    sort: str = Query("score", pattern="^(score|date|company|title|salary)$"),
    format: str = Query("csv", pattern="^(csv|json)$"),
) -> Response:
    exported = _service().export_jobs(
        query=JobListQuery(
            limit=limit,
            offset=offset,
            min_score=min_score,
            max_score=max_score,
            site=site,
            sites=sites,
            company=company,
            location=location,
            locations=locations,
            bookmarked=bookmarked,
            applied=applied,
            remote=remote,
            job_type=job_type,
            job_types=job_types,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted_from=date_posted_from,
            date_posted_to=date_posted_to,
            first_seen_from=first_seen_from,
            first_seen_to=first_seen_to,
            last_seen_from=last_seen_from,
            last_seen_to=last_seen_to,
            text=text,
            sort=_sort_value(sort),
        ),
        fmt=_export_format(format),
    )
    return _export_response(exported)


@router.post("/export/jobs")
def export_selected_jobs(payload: ExportJobsRequest) -> Response:
    exported = _service().export_jobs(
        job_ids=payload.job_ids,
        fmt=_export_format(payload.format),
    )
    return _export_response(exported)


@router.post("/cleanup/delete-below-score", response_model=JobCommandResponse)
def delete_jobs_below_score(payload: CleanupBelowScoreRequest) -> JobCommandResponse:
    return _command_response(_service().delete_jobs_below_score(payload.score))


@router.post("/cleanup/delete-stale", response_model=JobCommandResponse)
def delete_stale_jobs(payload: CleanupStaleRequest) -> JobCommandResponse:
    return _command_response(_service().delete_stale_jobs(payload.days))


@router.post("/cleanup/purge-blacklist", response_model=JobCommandResponse)
def cleanup_purge_blacklist(payload: BlacklistPurgeRequest) -> JobCommandResponse:
    return _command_response(_service().purge_blacklist(payload.older_than_days))


@router.get("/cleanup/preview", response_model=CleanupResponse)
def preview_cleanup() -> CleanupResponse:
    return _cleanup_response(_service().preview_cleanup(get_config()))


@router.post("/cleanup/run", response_model=CleanupResponse)
def run_cleanup() -> CleanupResponse:
    return _cleanup_response(_service().run_cleanup(get_config()))
