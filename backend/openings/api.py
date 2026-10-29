from fastapi import APIRouter, Query, Request
from typing import Annotated
from . import __version__
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
import os

from .models import (
    ApplicationInput,
    ApplicationPatch,
    JobInput,
    JobPatch,
    MergeInput,
    NoteInput,
    TriageInput,
    JobQuery,
    ApplicationQuery,
    PeriodQuery,
    JobBulk,
    NotePatch,
)


def register_core(router: APIRouter, workspace):
    @router.get("/workspace")
    def info(request: Request):
        return {
            "origin": os.environ.get("OPENINGS_PUBLIC_URL", str(request.base_url)).rstrip("/"),
            "name": "Openings",
            "version": __version__,
            "api_base": "/api/v1",
            "mcp_endpoint": "/mcp",
            "single_owner": True,
        }

    @router.get("/overview")
    def overview(value: Annotated[PeriodQuery, Query()]):
        return workspace.overview(**value.model_dump())

    @router.get("/jobs")
    def jobs(value: Annotated[JobQuery, Query()]):
        return workspace.list_jobs(**value.model_dump())

    @router.post("/jobs/bulk")
    def bulk_jobs(value: JobBulk):
        return workspace.bulk_jobs(value)

    @router.post("/jobs")
    async def ingest(value: JobInput):
        from .fetching import complete_input

        value = await complete_input(value, workspace.discovery)
        return workspace.ingest_job(value)

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str):
        return workspace.get_job(job_id)

    @router.patch("/jobs/{job_id}")
    def edit_job(job_id: str, value: JobPatch):
        return workspace.update_job(job_id, value)

    @router.post("/jobs/{job_id}/triage")
    def triage(job_id: str, value: TriageInput):
        return workspace.set_triage(job_id, value.triage, value.expected_version)

    @router.post("/jobs/{job_id}/merge")
    def merge(job_id: str, value: MergeInput):
        return workspace.merge_jobs(
            job_id, value.target_id, value.expected_version, value.target_version
        )

    @router.delete("/jobs/{job_id}")
    def forget(job_id: str):
        return workspace.forget_job(job_id)

    @router.get("/jobs/{job_id}/notes")
    def notes(job_id: str):
        return workspace.list_notes(job_id)

    @router.post("/jobs/{job_id}/notes")
    def note(job_id: str, value: NoteInput):
        return workspace.add_note(job_id, value)

    @router.delete("/notes/{note_id}")
    def remove_note(note_id: str):
        return workspace.delete_note(note_id)

    @router.get("/applications")
    def applications(value: Annotated[ApplicationQuery, Query()]):
        return workspace.list_applications(**value.model_dump())

    @router.get("/notes/{note_id}")
    def get_note(note_id: str):
        return workspace.get_note(note_id)

    @router.patch("/notes/{note_id}")
    def edit_note(note_id: str, value: NotePatch):
        return workspace.update_note(note_id, value)

    @router.delete("/applications/{application_id}")
    def delete_application(application_id: str, expected_version: int | None = None):
        return workspace.delete_application(application_id, expected_version)

    @router.post("/applications")
    def create_application(value: ApplicationInput):
        return workspace.create_application(value)

    @router.get("/applications/{application_id}")
    def get_application(application_id: str):
        return workspace.get_application(application_id)

    @router.patch("/applications/{application_id}")
    def edit_application(application_id: str, value: ApplicationPatch):
        return workspace.update_application(application_id, value)

    @router.get("/applications/{application_id}/events")
    def events(application_id: str):
        return workspace.application_events(application_id)


def register_core_mcp(mcp, workspace):
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def workspace_info(ctx: Context) -> dict:
        """Read workspace capabilities. Use REST transfer grants for file bytes."""
        request = ctx.request_context.request
        origin = os.environ.get("OPENINGS_PUBLIC_URL") or (
            str(request.base_url).rstrip("/") if request else None
        )
        return {
            "name": "Openings",
            "version": __version__,
            "origin": origin,
            "api_base": "/api/v1",
            "workflow": "Read career, templates and stored instructions; prepare a frozen context; write and compile externally; submit document revisions and PDF/source files; track progress explicitly.",
        }

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def jobs_search(value: JobQuery | None = None) -> dict:
        """Search compact paginated job summaries with location/source/remote/date/score filters. Read job_get for full content."""
        return workspace.list_jobs(**(value or JobQuery()).model_dump())

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def jobs_bulk(value: JobBulk) -> dict:
        """Apply saved/dismissed/inbox/forget/rescore to at most 200 explicit job IDs/versions, with per-item results. Forget is permanent."""
        return workspace.bulk_jobs(value)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def job_get(job_id: str) -> dict:
        """Read full job text, metadata, versions and assessment provenance."""
        return workspace.get_job(job_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    async def job_ingest(value: JobInput) -> dict:
        """Add a URL, pasted text or structured job. Duplicate identities preserve history."""
        from .fetching import complete_input

        value = await complete_input(value, workspace.discovery)
        return workspace.ingest_job(value)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def job_update(job_id: str, value: JobPatch) -> dict:
        """Correct job fields using the version returned by job_get."""
        return workspace.update_job(job_id, value)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def job_triage(job_id: str, value: TriageInput) -> dict:
        """Set inbox/saved/dismissed. Dismissed jobs remain remembered and excluded from scoring."""
        return workspace.set_triage(job_id, value.triage, value.expected_version)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def job_forget(job_id: str) -> dict:
        """Permanently delete a job and its application/file history. Future acquisition is new."""
        return workspace.forget_job(job_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def job_merge(job_id: str, value: MergeInput) -> dict:
        """Explicitly merge verified duplicate jobs, preserving postings, applications and notes."""
        return workspace.merge_jobs(
            job_id, value.target_id, value.expected_version, value.target_version
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def notes_list(job_id: str) -> dict:
        """Read notes retained with a job."""
        return workspace.list_notes(job_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def note_add(job_id: str, value: NoteInput) -> dict:
        """Store a note, optionally associated with a particular application attempt."""
        return workspace.add_note(job_id, value)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def note_delete(note_id: str) -> dict:
        """Remove an individual note."""
        return workspace.delete_note(note_id)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def applications_list(value: ApplicationQuery | None = None) -> dict:
        """Read paginated application summaries and stage totals independent of page, with query/stage/outcome/company filters."""
        return workspace.list_applications(**(value or ApplicationQuery()).model_dump())

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def application_delete(application_id: str, expected_version: int | None = None) -> dict:
        """Delete one attempt and its owned documents/history, retaining the archived job and other attempts."""
        return workspace.delete_application(application_id, expected_version)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def note_get(note_id: str) -> dict:
        """Read one editable note with its optimistic version."""
        return workspace.get_note(note_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def note_update(note_id: str, value: NotePatch) -> dict:
        """Edit a retained note without deleting/recreating it, using its current version."""
        return workspace.update_note(note_id, value)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def application_get(application_id: str) -> dict:
        """Read a single application and its job."""
        return workspace.get_application(application_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def application_create(value: ApplicationInput) -> dict:
        """Create a draft attempt. This never sends an application or generates documents."""
        return workspace.create_application(value)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def application_update(application_id: str, value: ApplicationPatch) -> dict:
        """Record progress/questions/answers explicitly; editing documents never marks sent."""
        return workspace.update_application(application_id, value)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def application_history(application_id: str) -> dict:
        """Read the recorded lifecycle events of an attempt."""
        return workspace.application_events(application_id)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
    def overview_get(value: PeriodQuery | None = None) -> dict:
        """Read funnel counts and activity from recorded application history."""
        return workspace.overview(**(value or PeriodQuery()).model_dump())
