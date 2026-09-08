"""REST routes under ``/api``."""

from __future__ import annotations

import hmac
import os
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from openings.application.attachments import AttachmentTooLarge
from openings.application.jobs import VectorStoreUnavailableError
from openings.application.models import AddJobCommand
from openings.database import JOB_SORTS, BlacklistQuery, JobQuery
from openings.models import AttachmentKind, JobStatus, NoteKind
from openings.web.service import get_service

TOKEN_HEADER = "X-Openings-Token"


def api_token() -> str:
    return os.environ.get("OPENINGS_API_TOKEN", "").strip()


def require_token(
    authorization: str | None = Header(default=None),
    x_openings_token: str | None = Header(default=None, alias=TOKEN_HEADER),
) -> None:
    expected = api_token()
    if not expected:
        return
    presented = x_openings_token or ""
    if not presented and authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    if not presented or not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


public_router = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class JobIds(BaseModel):
    job_ids: list[str] = Field(min_length=1)


class StatusRequest(JobIds):
    status: JobStatus
    note: str | None = None


class LabelsRequest(JobIds):
    labels: list[str] = Field(min_length=1)


class AddJobRequest(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = ""
    job_url: str | None = None
    description: str | None = None
    date_posted: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    salary_interval: str | None = None
    company_url: str | None = None
    source: str | None = None
    external_id: str | None = None
    status: JobStatus = JobStatus.SHORTLISTED
    labels: list[str] = Field(default_factory=list)
    note: str | None = None


class NoteRequest(BaseModel):
    kind: NoteKind = NoteKind.NOTE
    title: str | None = None
    body: str = Field(min_length=1)


class PurgeRequest(BaseModel):
    older_than_days: int | None = Field(default=None, ge=0)


class ScoreRequest(BaseModel):
    score: int


class DaysRequest(BaseModel):
    days: int = Field(ge=1)


class ExportRequest(BaseModel):
    format: Literal["csv", "json"] = "csv"
    job_ids: list[str] | None = None
    filters: dict[str, Any] | None = None


def _job_query(
    limit: int = Query(50, ge=0, le=1000),
    offset: int = Query(0, ge=0),
    status: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    label: list[str] | None = Query(None),
    company: str | None = None,
    location: str | None = None,
    locations: list[str] | None = Query(None),
    job_type: list[str] | None = Query(None),
    remote: bool | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    min_salary: float | None = None,
    max_salary: float | None = None,
    date_posted_from: str | None = None,
    date_posted_to: str | None = None,
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    last_seen_from: str | None = None,
    last_seen_to: str | None = None,
    text: str | None = None,
    sort: str = Query("score"),
) -> JobQuery:
    if sort not in JOB_SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {', '.join(JOB_SORTS)}")
    return JobQuery(
        limit=limit or 1,
        offset=offset,
        statuses=tuple(status or ()),
        sources=tuple(source or ()),
        labels=tuple(label or ()),
        company=company,
        location=location,
        locations=tuple(locations or ()),
        job_types=tuple(job_type or ()),
        remote=remote,
        min_score=min_score,
        max_score=max_score,
        min_salary=min_salary,
        max_salary=max_salary,
        date_posted_from=date_posted_from,
        date_posted_to=date_posted_to,
        first_seen_from=first_seen_from,
        first_seen_to=first_seen_to,
        last_seen_from=last_seen_from,
        last_seen_to=last_seen_to,
        text=text,
        sort=sort,
    )


def _query_from_dict(filters: dict[str, Any] | None) -> JobQuery:
    filters = dict(filters or {})
    tuples = {"statuses", "sources", "labels", "locations", "job_types"}
    allowed = set(JobQuery.__dataclass_fields__)
    cleaned: dict[str, Any] = {}
    for key, value in filters.items():
        if key not in allowed:
            raise HTTPException(status_code=422, detail=f"Unknown filter: {key}")
        cleaned[key] = tuple(value) if key in tuples and value is not None else value
    query = JobQuery(**cleaned)
    if query.sort not in JOB_SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {', '.join(JOB_SORTS)}")
    return query


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@public_router.get("/dashboard/auth")
def dashboard_auth() -> dict[str, bool]:
    return {"token_required": bool(api_token())}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@router.get("/jobs")
def list_jobs(query: JobQuery = Depends(_job_query)) -> dict[str, Any]:
    return get_service().list_jobs(query).to_dict()


@router.post("/jobs", status_code=201)
def add_job(payload: AddJobRequest) -> dict[str, Any]:
    command = AddJobCommand(
        **{**payload.model_dump(exclude={"labels"}), "labels": tuple(payload.labels)}
    )
    result = get_service().add_job(command)
    if not result.success:
        raise HTTPException(status_code=409, detail=result.message)
    return result.to_dict()


@router.get("/jobs/facets")
def facets() -> dict[str, Any]:
    return get_service().get_facets()


@router.get("/jobs/search/semantic")
def semantic_search(
    q: str = Query(min_length=1),
    n_results: int = Query(10, ge=1, le=100),
    min_score: int | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    try:
        results = get_service().search_similar(
            q, n_results=n_results, min_score=min_score, source=source
        )
    except VectorStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [result.to_dict() for result in results]


@router.post("/jobs/status")
def set_status(payload: StatusRequest) -> dict[str, Any]:
    return get_service().set_status(payload.job_ids, payload.status, payload.note).to_dict()


@router.post("/jobs/labels")
def add_labels(payload: LabelsRequest) -> dict[str, Any]:
    return get_service().add_labels(payload.job_ids, payload.labels).to_dict()


@router.post("/jobs/labels/remove")
def remove_labels(payload: LabelsRequest) -> dict[str, Any]:
    return get_service().remove_labels(payload.job_ids, payload.labels).to_dict()


@router.post("/jobs/delete")
def delete_jobs(payload: JobIds) -> dict[str, Any]:
    return get_service().delete_jobs(payload.job_ids).to_dict()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    detail = get_service().get_job_detail(job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return detail.to_dict()


@router.post("/jobs/{job_id}/notes", status_code=201)
def add_note(job_id: str, payload: NoteRequest) -> dict[str, Any]:
    note = get_service().add_note(job_id, payload.kind, payload.body, payload.title)
    if note is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return note.to_dict()


@router.delete("/jobs/{job_id}/notes/{note_id}")
def delete_note(job_id: str, note_id: int) -> dict[str, Any]:
    if not get_service().delete_note(job_id, note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": True}


@router.post("/jobs/{job_id}/attachments", status_code=201)
async def upload_attachment(
    job_id: str,
    file: UploadFile = File(...),
    kind: AttachmentKind = Form(AttachmentKind.OTHER),
    note: str | None = Form(None),
) -> dict[str, Any]:
    content = await file.read()
    try:
        attachment = get_service().add_attachment(
            job_id, kind=kind, filename=file.filename or "attachment", content=content, note=note
        )
    except AttachmentTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if attachment is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return attachment.to_dict()


@router.get("/jobs/{job_id}/attachments/{attachment_id}")
def download_attachment(job_id: str, attachment_id: int) -> FileResponse:
    found = get_service().get_attachment_file(job_id, attachment_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    attachment, path = found
    return FileResponse(path, filename=attachment.filename)


@router.delete("/jobs/{job_id}/attachments/{attachment_id}")
def delete_attachment(job_id: str, attachment_id: int) -> dict[str, Any]:
    if not get_service().delete_attachment(job_id, attachment_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------


@router.get("/blacklist")
def list_blacklist(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    text: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    entries, total = get_service().list_blacklist(
        BlacklistQuery(limit=limit, offset=offset, text=text, company=company, location=location)
    )
    return {
        "items": [entry.to_dict() for entry in entries],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/blacklist")
def blacklist_jobs(payload: JobIds) -> dict[str, Any]:
    return get_service().blacklist_jobs(payload.job_ids).to_dict()


@router.post("/blacklist/remove")
def unblacklist_jobs(payload: JobIds) -> dict[str, Any]:
    return get_service().unblacklist_jobs(payload.job_ids).to_dict()


@router.post("/blacklist/purge")
def purge_blacklist(payload: PurgeRequest) -> dict[str, Any]:
    return get_service().purge_blacklist(payload.older_than_days).to_dict()


# ---------------------------------------------------------------------------
# Sources, runs, statistics
# ---------------------------------------------------------------------------


@router.get("/sources")
def list_sources() -> list[dict[str, Any]]:
    return [source.to_dict() for source in get_service().list_sources()]


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=200)) -> list[dict[str, Any]]:
    return [run.to_dict() for run in get_service().list_runs(limit)]


@router.get("/stats")
def statistics() -> dict[str, Any]:
    return get_service().get_statistics()


@router.get("/distribution")
def distribution(bin_size: int = Query(5, ge=1, le=100)) -> list[list[int]]:
    return get_service().get_score_distribution(bin_size)


# ---------------------------------------------------------------------------
# Export and cleanup
# ---------------------------------------------------------------------------


def _export_response(result) -> Response:
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Openings-Export-Rows": str(result.row_count),
            "X-Openings-Export-Total": str(result.total),
        },
    )


@router.get("/export/jobs")
def export_jobs(
    format: Literal["csv", "json"] = "csv", query: JobQuery = Depends(_job_query)
) -> Response:
    return _export_response(get_service().export_jobs(query=query, fmt=format))


@router.post("/export/jobs")
def export_selected(payload: ExportRequest) -> Response:
    service = get_service()
    if payload.job_ids is not None:
        result = service.export_jobs(job_ids=payload.job_ids, fmt=payload.format)
    else:
        result = service.export_jobs(query=_query_from_dict(payload.filters), fmt=payload.format)
    return _export_response(result)


@router.get("/cleanup/preview")
def cleanup_preview() -> dict[str, int]:
    return get_service().preview_cleanup().to_dict()


@router.post("/cleanup/run")
def cleanup_run() -> dict[str, int]:
    return get_service().run_cleanup().to_dict()


@router.post("/cleanup/delete-below-score")
def cleanup_below_score(payload: ScoreRequest) -> dict[str, Any]:
    return get_service().delete_below_score(payload.score).to_dict()


@router.post("/cleanup/delete-stale")
def cleanup_stale(payload: DaysRequest) -> dict[str, Any]:
    return get_service().delete_stale(payload.days).to_dict()


@router.post("/cleanup/purge-blacklist")
def cleanup_purge_blacklist(payload: PurgeRequest) -> dict[str, Any]:
    return get_service().purge_blacklist(payload.older_than_days).to_dict()
