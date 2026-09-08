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
from openings.db import JOB_SORTS, SORT_DIRECTIONS, JobQuery
from openings.models import POSTING_FIELDS, AttachmentKind, JobStatus, NoteKind
from openings.settings_reference import get_settings_reference as read_settings_reference
from openings.web.service import get_service

DEFAULT_ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
DEFAULT_ALLOWED_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
MAX_INLINE_ATTACHMENT = 5 * 1024 * 1024


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(message: str) -> str:
    return _json({"success": False, "message": message})


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


def _statuses(values: list[str] | None) -> tuple[str, ...]:
    return tuple(_status(value).value for value in values or [])


def _query(**kwargs: Any) -> JobQuery:
    sort = kwargs.pop("sort", "score")
    direction = kwargs.pop("direction", None)
    return JobQuery(
        **kwargs,
        sort=sort if sort in JOB_SORTS else "score",
        direction=direction if direction in SORT_DIRECTIONS else None,
    )


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
    locations: list[str] | None = None,
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
    status_changed_from: str | None = None,
    status_changed_to: str | None = None,
    has_attachments: bool | None = None,
    without_labels: bool | None = None,
    text: str | None = None,
    sort: str = "score",
    direction: str | None = None,
) -> str:
    """List job summaries with filters and pagination. Without ``statuses`` every
    status except blacklisted is returned. ``statuses`` accepts new, shortlisted,
    applied, interviewing, offer, rejected, withdrawn, blacklisted. ``text`` also
    searches notes. ``sort``: score, date, first_seen, updated, company, title,
    salary; ``direction``: asc or desc."""
    try:
        query = _query(
            limit=limit,
            offset=offset,
            statuses=_statuses(statuses),
            sources=tuple(sources or ()),
            labels=tuple(labels or ()),
            company=company,
            location=location,
            locations=tuple(locations or ()),
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
            status_changed_from=status_changed_from,
            status_changed_to=status_changed_to,
            has_attachments=has_attachments,
            without_labels=without_labels,
            text=text,
            sort=sort,
            direction=direction,
        )
    except ValueError as exc:
        return _error(str(exc))
    return _json(get_service().list_jobs(query).to_dict())


def get_job(
    job_id: str, include_raw: bool = False, max_description_chars: int | None = None
) -> str:
    """Full job: posting, score breakdown, postings, labels, notes, attachments,
    timeline. ``include_raw`` adds the source payload; ``max_description_chars``
    truncates long descriptions."""
    detail = get_service().get_job_detail(job_id)
    if detail is None:
        return _error(f"Job not found: {job_id}")
    return _json(
        detail.to_dict(include_raw=include_raw, max_description_chars=max_description_chars)
    )


def search_similar(
    query: str | None = None,
    job_id: str | None = None,
    n_results: int = 10,
    min_score: int | None = None,
    source: str | None = None,
    statuses: list[str] | None = None,
) -> str:
    """Semantic search over stored jobs: closest to ``query`` text, or to an
    existing ``job_id``."""
    if not query and not job_id:
        return _error("query or job_id is required")
    try:
        results = get_service().search_similar(
            query,
            job_id=job_id,
            n_results=n_results,
            min_score=min_score,
            source=source,
            statuses=_statuses(statuses),
        )
    except VectorStoreUnavailableError as exc:
        return _error(str(exc))
    except ValueError as exc:
        return _error(str(exc))
    return _json([result.to_dict() for result in results])


def get_statistics() -> str:
    """Totals, counts by status, today's new rows, average score, blacklist size."""
    return _json(get_service().get_statistics())


def get_score_distribution(bin_size: int = 5) -> str:
    """Score histogram as [bin_start, count] pairs."""
    return _json(get_service().get_score_distribution(bin_size))


def get_facets(limit: int = 50, q: str | None = None) -> str:
    """Distinct values with counts for statuses, sources, companies, locations,
    job types, labels. ``q`` filters values by substring."""
    return _json(get_service().get_facets(limit=limit, q=q))


def list_labels() -> str:
    """Every label with its job count."""
    return _json(get_service().get_facets(limit=1000)["labels"])


def list_blacklist(
    limit: int = 100,
    offset: int = 0,
    text: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> str:
    """Blacklisted jobs with filters and pagination."""
    query = _query(
        limit=limit,
        offset=offset,
        statuses=(JobStatus.BLACKLISTED.value,),
        text=text,
        company=company,
        location=location,
        sort="updated",
    )
    return _json(get_service().list_jobs(query).to_dict())


def list_sources() -> str:
    """Configured sources with the number of active jobs each one produced and
    what happened to each in the last run."""
    return _json([source.to_dict() for source in get_service().list_sources()])


def list_runs(limit: int = 20) -> str:
    """Recent collection runs: timing, per-source counts, failures, whether one is running."""
    service = get_service()
    return _json(
        {
            "status": service.run_status(),
            "runs": [run.to_dict() for run in service.list_runs(limit)],
        }
    )


def list_attachments(
    kind: str | None = None, statuses: list[str] | None = None, limit: int = 100, offset: int = 0
) -> str:
    """Attachments across jobs, newest first, with the job title and company."""
    try:
        attachment_kind = AttachmentKind(kind.strip().lower()) if kind else None
        clean = _statuses(statuses)
    except ValueError as exc:
        return _error(str(exc))
    entries, total = get_service().list_attachments(
        kind=attachment_kind, statuses=clean, limit=limit, offset=offset
    )
    return _json(
        {
            "items": [entry.to_dict() for entry in entries],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


def get_attachment(job_id: str, attachment_id: int) -> str:
    """A stored file as base64 with its metadata (files up to 5 MB)."""
    found = get_service().get_attachment_file(job_id, attachment_id)
    if found is None:
        return _error("Attachment not found")
    attachment, path = found
    if attachment.size_bytes > MAX_INLINE_ATTACHMENT:
        return _error("Attachment larger than 5 MB; download it through the REST API")
    data = attachment.to_dict()
    data["content_base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return _json({"success": True, "attachment": data})


def get_settings() -> str:
    """Profile, thresholds, sources and runtime facts from the live configuration."""
    return _json(get_service().settings_summary())


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
    given status (default shortlisted, so retention never removes it). A
    posting already stored (same URL or same title, company and location) is
    updated with the fields given and keeps its status."""
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
        return _error(str(exc))
    return _json(get_service().add_job(command).to_dict())


def update_job(job_id: str, **fields: Any) -> str:
    """Edit posting fields: title, company, location, job_url, description,
    date_posted, job_type, is_remote, job_level, min_amount, max_amount,
    currency, salary_interval, company_url. The job is rescored."""
    changes = {key: value for key, value in fields.items() if key in POSTING_FIELDS}
    if not changes:
        return _error(f"No editable field given; allowed: {', '.join(POSTING_FIELDS)}")
    updated = get_service().update_job(job_id, changes)
    if updated is None:
        return _error(f"Job not found: {job_id}")
    return _json({"success": True, "job": updated.to_dict()})


def set_status(job_ids: list[str], status: str, note: str | None = None) -> str:
    """Move jobs to a status: new, shortlisted, applied, interviewing, offer,
    rejected, withdrawn, blacklisted. ``note`` lands on the timeline."""
    try:
        target = _status(status)
    except ValueError as exc:
        return _error(str(exc))
    return _json(get_service().set_status(job_ids, target, note).to_dict())


def add_labels(job_ids: list[str], labels: list[str]) -> str:
    """Attach free-form labels to jobs."""
    return _json(get_service().add_labels(job_ids, labels).to_dict())


def remove_labels(job_ids: list[str], labels: list[str]) -> str:
    """Detach labels from jobs."""
    return _json(get_service().remove_labels(job_ids, labels).to_dict())


def rename_label(old: str, new: str) -> str:
    """Rename a label on every job that carries it."""
    return _json(get_service().rename_label(old, new).to_dict())


def add_note(job_id: str, body: str, kind: str = "note", title: str | None = None) -> str:
    """Add a note (kind ``note``) or a form question and answer (kind ``qa``:
    question in ``title``, answer in ``body``)."""
    try:
        note_kind = NoteKind(kind.strip().lower())
        note = get_service().add_note(job_id, note_kind, body, title)
    except ValueError as exc:
        return _error(str(exc))
    if note is None:
        return _error(f"Job not found: {job_id}")
    return _json({"success": True, "note": note.to_dict()})


def update_note(
    job_id: str,
    note_id: int,
    body: str | None = None,
    title: str | None = None,
    kind: str | None = None,
) -> str:
    """Edit a note or answer in place."""
    try:
        note_kind = NoteKind(kind.strip().lower()) if kind else None
        note = get_service().update_note(job_id, note_id, body=body, title=title, kind=note_kind)
    except ValueError as exc:
        return _error(str(exc))
    if note is None:
        return _error("Note not found")
    return _json({"success": True, "note": note.to_dict()})


def delete_note(job_id: str, note_id: int) -> str:
    """Remove a note."""
    ok = get_service().delete_note(job_id, note_id)
    return _json({"success": ok, "message": None if ok else "Note not found"})


def add_attachment(
    job_id: str, filename: str, content_base64: str, kind: str = "other", note: str | None = None
) -> str:
    """Store a file for a job. ``kind`` is cv, cover_letter, form_answers or other."""
    try:
        attachment_kind = AttachmentKind(kind.strip().lower())
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        return _error(f"Invalid input: {exc}")
    try:
        attachment = get_service().add_attachment(
            job_id, kind=attachment_kind, filename=filename, content=content, note=note
        )
    except (AttachmentTooLarge, ValueError) as exc:
        return _error(str(exc))
    if attachment is None:
        return _error(f"Job not found: {job_id}")
    return _json({"success": True, "attachment": attachment.to_dict()})


def update_attachment(
    job_id: str,
    attachment_id: int,
    kind: str | None = None,
    note: str | None = None,
    filename: str | None = None,
) -> str:
    """Change an attachment's kind, note or display name."""
    try:
        attachment_kind = AttachmentKind(kind.strip().lower()) if kind else None
    except ValueError as exc:
        return _error(str(exc))
    attachment = get_service().update_attachment(
        job_id, attachment_id, kind=attachment_kind, note=note, filename=filename
    )
    if attachment is None:
        return _error("Attachment not found")
    return _json({"success": True, "attachment": attachment.to_dict()})


def delete_attachment(job_id: str, attachment_id: int) -> str:
    """Remove a stored file."""
    ok = get_service().delete_attachment(job_id, attachment_id)
    return _json({"success": ok, "message": None if ok else "Attachment not found"})


def blacklist_jobs(job_ids: list[str], note: str | None = None) -> str:
    """Hide jobs everywhere and block them from being ingested again. Their
    notes, attachments and timeline are kept; ``unblacklist_jobs`` restores them."""
    return _json(get_service().blacklist_jobs(job_ids, note).to_dict())


def unblacklist_jobs(job_ids: list[str]) -> str:
    """Restore blacklisted jobs to the status they held before."""
    return _json(get_service().unblacklist_jobs(job_ids).to_dict())


def delete_jobs(job_ids: list[str]) -> str:
    """Delete jobs permanently, with their notes and attachments."""
    return _json(get_service().delete_jobs(job_ids).to_dict())


def merge_jobs(primary_id: str, other_ids: list[str]) -> str:
    """Fold duplicate jobs into ``primary_id``: their postings, notes,
    attachments, labels and timeline move over and the duplicates disappear."""
    return _json(get_service().merge_jobs(primary_id, other_ids).to_dict())


def run_now() -> str:
    """Ask the scheduler to collect as soon as possible (within about 30 seconds)."""
    return _json(get_service().request_run())


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
    """Export selected or filtered jobs. ``limit=0`` exports every match. The
    result is an envelope with ``content`` (CSV text or a JSON array), ``format``,
    ``row_count`` and ``total``."""
    fmt: Literal["csv", "json"] = "json" if format == "json" else "csv"
    service = get_service()
    try:
        if job_ids is not None:
            exported = service.export_jobs(job_ids=job_ids, fmt=fmt)
        else:
            exported = service.export_jobs(
                query=_query(
                    limit=limit,
                    offset=offset,
                    statuses=_statuses(statuses),
                    sources=tuple(sources or ()),
                    labels=tuple(labels or ()),
                    company=company,
                    location=location,
                    min_score=min_score,
                    max_score=max_score,
                    text=text,
                    sort=sort,
                ),
                fmt=fmt,
            )
    except ValueError as exc:
        return _error(str(exc))
    text_content = exported.content.decode("utf-8")
    return _json(
        {
            "format": fmt,
            "content": json.loads(text_content) if fmt == "json" else text_content,
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
    list_labels,
    list_blacklist,
    list_sources,
    list_runs,
    list_attachments,
    get_attachment,
    get_settings,
    get_settings_reference,
    add_job,
    update_job,
    set_status,
    add_labels,
    remove_labels,
    rename_label,
    add_note,
    update_note,
    delete_note,
    add_attachment,
    update_attachment,
    delete_attachment,
    blacklist_jobs,
    unblacklist_jobs,
    delete_jobs,
    merge_jobs,
    run_now,
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
