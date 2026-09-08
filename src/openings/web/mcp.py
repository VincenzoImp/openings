"""MCP tools mounted at ``/mcp`` by the web server.

Tool names mirror the REST commands; both call the same application service.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from openings.application.attachments import AttachmentTooLarge
from openings.application.jobs import VectorStoreUnavailableError
from openings.application.models import AddJobCommand
from openings.database import JOB_SORTS, BlacklistQuery, JobQuery
from openings.models import AttachmentKind, JobStatus, NoteKind
from openings.settings_reference import get_settings_reference as read_settings_reference
from openings.web.service import get_service

DEFAULT_ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
DEFAULT_ALLOWED_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _env_csv(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def get_transport_security_settings() -> TransportSecuritySettings:
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(
            dict.fromkeys(DEFAULT_ALLOWED_HOSTS + _env_csv("OPENINGS_WEB_ALLOWED_HOSTS"))
        ),
        allowed_origins=list(
            dict.fromkeys(DEFAULT_ALLOWED_ORIGINS + _env_csv("OPENINGS_WEB_ALLOWED_ORIGINS"))
        ),
    )


def _status(value: str) -> JobStatus:
    try:
        return JobStatus(value.strip().lower())
    except ValueError as exc:
        raise ValueError(f"status must be one of {', '.join(s.value for s in JobStatus)}") from exc


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


def list_jobs(
    limit: int = 20,
    offset: int = 0,
    statuses: list[str] | None = None,
    sources: list[str] | None = None,
    labels: list[str] | None = None,
    company: str | None = None,
    location: str | None = None,
    job_types: list[str] | None = None,
    remote: bool | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    min_salary: float | None = None,
    max_salary: float | None = None,
    date_posted_from: str | None = None,
    date_posted_to: str | None = None,
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    text: str | None = None,
    sort: str = "score",
) -> str:
    """List job summaries with filters and pagination. ``statuses`` accepts
    new, shortlisted, applied, interviewing, offer, rejected, withdrawn.
    ``sort`` accepts score, date, first_seen, updated, company, title, salary."""
    query = JobQuery(
        limit=limit,
        offset=offset,
        statuses=tuple(statuses or ()),
        sources=tuple(sources or ()),
        labels=tuple(labels or ()),
        company=company,
        location=location,
        job_types=tuple(job_types or ()),
        remote=remote,
        min_score=min_score,
        max_score=max_score,
        min_salary=min_salary,
        max_salary=max_salary,
        date_posted_from=date_posted_from,
        date_posted_to=date_posted_to,
        first_seen_from=first_seen_from,
        first_seen_to=first_seen_to,
        text=text,
        sort=sort if sort in JOB_SORTS else "score",
    )
    return _json(get_service().list_jobs(query).to_dict())


def get_job(job_id: str) -> str:
    """Full job: posting, score breakdown, labels, notes, attachments, timeline."""
    detail = get_service().get_job_detail(job_id)
    if detail is None:
        return _json({"error": f"Job not found: {job_id}"})
    return _json(detail.to_dict())


def search_similar(
    query: str, n_results: int = 10, min_score: int | None = None, source: str | None = None
) -> str:
    """Semantic search over stored jobs (local embeddings)."""
    try:
        results = get_service().search_similar(
            query, n_results=n_results, min_score=min_score, source=source
        )
    except VectorStoreUnavailableError:
        return _json({"error": "Vector store not available"})
    return _json([result.to_dict() for result in results])


def get_statistics() -> str:
    """Totals, counts by status, today's new rows, average score, blacklist size."""
    return _json(get_service().get_statistics())


def get_score_distribution(bin_size: int = 5) -> str:
    """Score histogram as [bin_start, count] pairs."""
    return _json(get_service().get_score_distribution(bin_size))


def get_facets() -> str:
    """Distinct values with counts for statuses, sources, companies, locations, job types, labels."""
    return _json(get_service().get_facets())


def list_blacklist(
    limit: int = 100,
    offset: int = 0,
    text: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> str:
    """Blacklist entries with filters and pagination."""
    entries, total = get_service().list_blacklist(
        BlacklistQuery(limit=limit, offset=offset, text=text, company=company, location=location)
    )
    return _json(
        {
            "items": [entry.to_dict() for entry in entries],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


def list_sources() -> str:
    """Configured sources with the number of active jobs each one produced."""
    return _json([source.to_dict() for source in get_service().list_sources()])


def list_runs(limit: int = 20) -> str:
    """Recent collection runs: timing, per-source counts, failures."""
    return _json([run.to_dict() for run in get_service().list_runs(limit)])


def get_settings_reference() -> str:
    """The annotated settings.yaml reference."""
    return read_settings_reference()


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


def add_job(
    title: str,
    company: str,
    location: str = "",
    job_url: str | None = None,
    description: str | None = None,
    date_posted: str | None = None,
    job_type: str | None = None,
    is_remote: bool | None = None,
    job_level: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    currency: str | None = None,
    salary_interval: str | None = None,
    company_url: str | None = None,
    source: str | None = None,
    external_id: str | None = None,
    status: str = "shortlisted",
    labels: list[str] | None = None,
    note: str | None = None,
) -> str:
    """Add a posting by hand. The caller supplies the fields it digested from
    the page; the job is scored with the live configuration and lands in the
    given status (default shortlisted, so retention never removes it)."""
    try:
        command = AddJobCommand(
            title=title,
            company=company,
            location=location,
            job_url=job_url,
            description=description,
            date_posted=date_posted,
            job_type=job_type,
            is_remote=is_remote,
            job_level=job_level,
            min_amount=min_amount,
            max_amount=max_amount,
            currency=currency,
            salary_interval=salary_interval,
            company_url=company_url,
            source=source,
            external_id=external_id,
            status=_status(status),
            labels=tuple(labels or ()),
            note=note,
        )
    except ValueError as exc:
        return _json({"success": False, "message": str(exc)})
    return _json(get_service().add_job(command).to_dict())


def set_status(job_ids: list[str], status: str, note: str | None = None) -> str:
    """Move jobs to a status: new, shortlisted, applied, interviewing, offer, rejected, withdrawn."""
    try:
        target = _status(status)
    except ValueError as exc:
        return _json({"success": False, "message": str(exc)})
    return _json(get_service().set_status(job_ids, target, note).to_dict())


def add_labels(job_ids: list[str], labels: list[str]) -> str:
    """Attach free-form labels to jobs."""
    return _json(get_service().add_labels(job_ids, labels).to_dict())


def remove_labels(job_ids: list[str], labels: list[str]) -> str:
    """Detach labels from jobs."""
    return _json(get_service().remove_labels(job_ids, labels).to_dict())


def add_note(job_id: str, body: str, kind: str = "note", title: str | None = None) -> str:
    """Add a note (kind ``note``) or a form question and answer (kind ``qa``:
    question in ``title``, answer in ``body``)."""
    try:
        note_kind = NoteKind(kind.strip().lower())
        note = get_service().add_note(job_id, note_kind, body, title)
    except ValueError as exc:
        return _json({"success": False, "message": str(exc)})
    if note is None:
        return _json({"success": False, "message": f"Job not found: {job_id}"})
    return _json({"success": True, "note": note.to_dict()})


def add_attachment(
    job_id: str, filename: str, content_base64: str, kind: str = "other", note: str | None = None
) -> str:
    """Store a file for a job. ``kind`` is cv, cover_letter, form_answers or other."""
    try:
        attachment_kind = AttachmentKind(kind.strip().lower())
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        return _json({"success": False, "message": f"Invalid input: {exc}"})
    try:
        attachment = get_service().add_attachment(
            job_id, kind=attachment_kind, filename=filename, content=content, note=note
        )
    except (AttachmentTooLarge, ValueError) as exc:
        return _json({"success": False, "message": str(exc)})
    if attachment is None:
        return _json({"success": False, "message": f"Job not found: {job_id}"})
    return _json({"success": True, "attachment": attachment.to_dict()})


def delete_attachment(job_id: str, attachment_id: int) -> str:
    """Remove a stored file."""
    ok = get_service().delete_attachment(job_id, attachment_id)
    return _json({"success": ok, "message": None if ok else "Attachment not found"})


def blacklist_jobs(job_ids: list[str]) -> str:
    """Delete jobs and block them from being ingested again."""
    return _json(get_service().blacklist_jobs(job_ids).to_dict())


def unblacklist_jobs(job_ids: list[str]) -> str:
    """Lift the suppression; the job returns only if a source finds it again."""
    return _json(get_service().unblacklist_jobs(job_ids).to_dict())


def delete_jobs(job_ids: list[str]) -> str:
    """Delete jobs permanently without blacklisting them."""
    return _json(get_service().delete_jobs(job_ids).to_dict())


def preview_cleanup() -> str:
    """What the configured retention would remove, without removing it."""
    return _json(get_service().preview_cleanup().to_dict())


def run_cleanup() -> str:
    """Apply the configured retention now. Only ``new`` jobs can be removed."""
    return _json(get_service().run_cleanup().to_dict())


def export_jobs(
    format: str = "csv",
    job_ids: list[str] | None = None,
    limit: int = 1000,
    offset: int = 0,
    statuses: list[str] | None = None,
    sources: list[str] | None = None,
    labels: list[str] | None = None,
    company: str | None = None,
    location: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    text: str | None = None,
    sort: str = "score",
) -> str:
    """Export selected or filtered jobs. ``limit=0`` exports every match."""
    fmt: Literal["csv", "json"] = "json" if format == "json" else "csv"
    service = get_service()
    if job_ids is not None:
        exported = service.export_jobs(job_ids=job_ids, fmt=fmt)
    else:
        exported = service.export_jobs(
            query=JobQuery(
                limit=limit,
                offset=offset,
                statuses=tuple(statuses or ()),
                sources=tuple(sources or ()),
                labels=tuple(labels or ()),
                company=company,
                location=location,
                min_score=min_score,
                max_score=max_score,
                text=text,
                sort=sort if sort in JOB_SORTS else "score",
            ),
            fmt=fmt,
        )
    if fmt == "json":
        return exported.content.decode("utf-8")
    return _json(
        {
            "content": exported.content.decode("utf-8"),
            "media_type": exported.media_type,
            "filename": exported.filename,
            "row_count": exported.row_count,
            "total": exported.total,
        }
    )


TOOLS = (
    list_jobs,
    get_job,
    search_similar,
    get_statistics,
    get_score_distribution,
    get_facets,
    list_blacklist,
    list_sources,
    list_runs,
    get_settings_reference,
    add_job,
    set_status,
    add_labels,
    remove_labels,
    add_note,
    add_attachment,
    delete_attachment,
    blacklist_jobs,
    unblacklist_jobs,
    delete_jobs,
    preview_cleanup,
    run_cleanup,
    export_jobs,
)


def create_mcp_server() -> FastMCP:
    server = FastMCP(
        "openings",
        streamable_http_path="/",
        transport_security=get_transport_security_settings(),
    )
    for tool in TOOLS:
        server.tool()(tool)
    return server


def create_mcp_app() -> Starlette:
    return create_mcp_server().streamable_http_app()
