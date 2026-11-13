"""REST routes and MCP tools of the workspace: jobs, notes, applications and the overview."""

import os
from typing import Annotated

from fastapi import APIRouter, Query, Request
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from .. import __version__
from ..actors import current_actor
from ..db import SCHEMA_VERSION
from ..models import (
    ApplicationBulk,
    ApplicationInput,
    ApplicationPatch,
    ApplicationQuery,
    DistinctInput,
    DuplicateQuery,
    JobBulk,
    JobInput,
    JobPatch,
    JobQuery,
    JobResolve,
    MergeInput,
    NoteInput,
    NotePatch,
    NotePin,
    PeriodQuery,
    TimelineQuery,
    TriageInput,
)
from ..operations import storage_status
from .registry import (
    REQUIRED,
    Operation,
    Param,
    Route,
    Tool,
    bind_mcp,
    bind_rest,
    query_model,
)

WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)
REMOVE = ToolAnnotations(destructiveHint=True, openWorldHint=False)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
FETCH = ToolAnnotations(destructiveHint=False, openWorldHint=True)


async def ingest(workspace, value):
    """Complete a URL or partial posting through the provider gate, then ingest it.

    A retry with an idempotency key returns its job without reading the URL again.
    """
    from ..fetching import complete_input
    from ..idempotency import fingerprint

    digest = fingerprint(value)
    replayed = workspace.replayed_job(value.idempotency_key, digest)
    if replayed:
        return replayed
    value = await complete_input(value, workspace.discovery)
    return workspace.ingest_job(value, digest=digest)


OPERATIONS = (
    Operation(
        "workspace.info",
        "workspace",
        "info",
        "Archive",
        "Read workspace identity and workflow",
        rest=(Route("GET", "/workspace", "info", custom=True),),
        tool=Tool(READ_ONLY, custom=True),
    ),
    Operation(
        "overview.read",
        "overview",
        "get",
        "Archive",
        "Read submitted-attempt funnel and activity for a period",
        params=(query_model(PeriodQuery),),
        call=lambda s, value: s.overview(**(value or PeriodQuery()).model_dump()),
        rest=(Route("GET", "/overview", "overview"),),
        tool=Tool(
            READ_ONLY,
            "Read funnel counts and activity from recorded application history.",
        ),
    ),
    Operation(
        "jobs.list",
        "jobs",
        "list",
        "Archive",
        "Search/filter/sort paginated job summaries",
        params=(query_model(JobQuery),),
        call=lambda s, value: s.list_jobs(**(value or JobQuery()).model_dump()),
        rest=(Route("GET", "/jobs", "jobs"),),
        tool=Tool(
            READ_ONLY,
            "Search compact paginated job summaries with triage (new, shortlisted, dismissed, active), location, source, remote and date filters; include_facets=true adds filter value lists and include_counts=true the number of jobs by triage. Each job has its ingest signals (posting language, languages the posting requires or welcomes, the earlier job it likely duplicates with a confidence, whether the source no longer lists it, policy rules that matched) and, when dismissed, its dismissal (who, why, which rule). Filter by signal, posting_language, posting_language_not, requires, dismissed_by or rule_id. Read jobs_get for full content.",
        ),
    ),
    Operation(
        "jobs.bulk",
        "jobs",
        "bulk",
        "Archive",
        "Shortlist/dismiss/restore/forget selected jobs",
        params=(Param("value", JobBulk),),
        call=lambda s, value: s.bulk_jobs(value),
        rest=(Route("POST", "/jobs/bulk", "bulk_jobs"),),
        tool=Tool(
            REMOVE,
            "Apply shortlisted/dismissed/new/forget to at most 200 explicit job IDs/versions, with per-item results; shortlisted starts each job's application, and new or dismissed undoes a shortlist whose application is still empty (application_has_work otherwise). reason (dismissed only) is stored on each dismissal. Forget is permanent.",
        ),
    ),
    Operation(
        "jobs.resolve",
        "jobs",
        "resolve",
        "Archive",
        "Look up archived jobs by URL or source identity without ingesting",
        params=(Param("value", JobResolve, rest=(Annotated[JobResolve, Query()], REQUIRED)),),
        call=lambda s, value: s.resolve_jobs(value),
        rest=(Route("GET", "/jobs/resolve", "resolve_jobs"),),
        tool=Tool(
            READ_ONLY,
            "Read-only identity lookup: archived jobs matching a URL or source_key, with triage and every application attempt. Never ingests or fetches.",
        ),
    ),
    Operation(
        "jobs.duplicates",
        "jobs",
        "duplicates",
        "Archive",
        "List candidate duplicate job groups for review",
        params=(query_model(DuplicateQuery),),
        call=lambda s, value: s.duplicate_jobs(value or DuplicateQuery()),
        rest=(Route("GET", "/jobs/duplicates", "duplicate_jobs"),),
        tool=Tool(
            READ_ONLY,
            "Read-only candidate duplicate groups, most confident first: each has a confidence in [0,1], a tier and the signals that matched or conflicted (requisition id, apply target, posting text, company and title, location), with triage and attempts. min_confidence defaults to 0.5; 0 lists every candidate. Verify before jobs_merge; never merges.",
        ),
    ),
    Operation(
        "jobs.create",
        "jobs",
        "create",
        "Archive",
        "Import a URL, pasted posting or structured job",
        params=(Param("value", JobInput),),
        call=ingest,
        rest=(Route("POST", "/jobs", "ingest"),),
        tool=Tool(
            FETCH,
            "Add a URL, pasted text or structured job. Duplicate identities preserve history. A new job gets its ingest signals, and an enabled rule the owner confirmed may dismiss it at once (dismissal.rule names the rule; restore it with jobs_triage).",
        ),
    ),
    Operation(
        "jobs.read",
        "jobs",
        "get",
        "Archive",
        "Read full posting, metadata and source provenance",
        params=(Param("job_id", str),),
        call=lambda s, job_id: s.get_job(job_id),
        rest=(Route("GET", "/jobs/{job_id}", "get_job"),),
        tool=Tool(
            READ_ONLY,
            "Read full job text, metadata, versions, observations (with unlisted_at when a board stopped listing one), signals and dismissal.",
        ),
    ),
    Operation(
        "jobs.update",
        "jobs",
        "update",
        "Archive",
        "Correct job fields and metadata",
        params=(Param("job_id", str), Param("value", JobPatch)),
        call=lambda s, job_id, value: s.update_job(job_id, value),
        rest=(Route("PATCH", "/jobs/{job_id}", "edit_job"),),
        tool=Tool(
            WRITE,
            "Correct job fields using the version returned by jobs_get. Returns the compact job summary; read jobs_get for full text.",
        ),
    ),
    Operation(
        "jobs.triage",
        "jobs",
        "triage",
        "Archive",
        "Shortlist, dismiss or return a job to review",
        params=(Param("job_id", str), Param("value", TriageInput)),
        call=lambda s, job_id, value: s.set_triage(
            job_id, value.triage, value.expected_version, value.reason
        ),
        rest=(Route("POST", "/jobs/{job_id}/triage", "triage"),),
        tool=Tool(
            WRITE,
            "Set new/shortlisted/dismissed and return the compact job summary. shortlisted starts the job's application (stage Shortlisted, CV and letter required) when it has no open one; moving a shortlisted job back to new or dismissed deletes that application only while it is empty (no documents, notes, replies, requirements or answers), otherwise 409 application_has_work names what exists. When dismissing, give a short reason (shown to the owner beside the dismissal); the dismissal records who made it and can be restored.",
        ),
    ),
    Operation(
        "jobs.distinct",
        "jobs",
        "distinct",
        "Archive",
        "Mark a job flagged as a likely duplicate as a different vacancy",
        params=(Param("job_id", str), Param("value", DistinctInput)),
        call=lambda s, job_id, value: s.mark_distinct(job_id, value.other_id),
        rest=(Route("POST", "/jobs/{job_id}/distinct", "distinct"),),
        tool=Tool(
            WRITE,
            "Record that a job flagged as a likely duplicate (signals.duplicate) is a different vacancy from other_id: the flag is cleared and does not return. Merge verified duplicates with jobs_merge instead.",
        ),
    ),
    Operation(
        "jobs.merge",
        "jobs",
        "merge",
        "Archive",
        "Merge verified duplicate jobs and retain history",
        params=(Param("job_id", str), Param("value", MergeInput)),
        call=lambda s, job_id, value: s.merge_jobs(
            job_id, value.target_id, value.expected_version, value.target_version
        ),
        rest=(Route("POST", "/jobs/{job_id}/merge", "merge"),),
        tool=Tool(
            REMOVE,
            "Explicitly merge verified duplicate jobs, preserving postings, applications and notes.",
        ),
    ),
    Operation(
        "jobs.delete",
        "jobs",
        "delete",
        "Archive",
        "Permanently forget job-owned data and identities",
        params=(
            Param("job_id", str),
            Param("expected_version", int, rest=(Annotated[int, Query(ge=1)], REQUIRED)),
        ),
        call=lambda s, job_id, expected_version: s.forget_job(job_id, expected_version),
        rest=(Route("DELETE", "/jobs/{job_id}", "forget"),),
        tool=Tool(
            REMOVE,
            "Permanently delete the current version of a job and its application/file history. Future acquisition is new.",
        ),
    ),
    Operation(
        "notes.list",
        "notes",
        "list",
        "Archive",
        "List the notes of a job and its applications",
        params=(Param("job_id", str),),
        call=lambda s, job_id: s.list_notes(job_id),
        rest=(Route("GET", "/jobs/{job_id}/notes", "notes"),),
        tool=Tool(
            READ_ONLY,
            "Read the notes of a job and of its applications (scope, author, run, pinned), pinned first. timeline_get lists them with the recorded changes.",
        ),
    ),
    Operation(
        "timeline.read",
        "timeline",
        "get",
        "Archive",
        "Read the timeline of a job or an application: notes and attributed events with scope and filters",
        params=(
            Param("job_id", str | None, None),
            Param("application_id", str | None, None),
            query_model(TimelineQuery),
        ),
        call=lambda s, job_id, application_id, value: s.timeline(job_id, application_id, value),
        rest=(
            Route(
                "GET",
                "/jobs/{job_id}/timeline",
                "job_timeline",
                params=(Param("job_id", str), query_model(TimelineQuery)),
                call=lambda s, job_id, value: s.timeline(job_id=job_id, value=value),
            ),
            Route(
                "GET",
                "/applications/{application_id}/timeline",
                "application_timeline",
                params=(Param("application_id", str), query_model(TimelineQuery)),
                call=lambda s, application_id, value: s.timeline(
                    application_id=application_id, value=value
                ),
            ),
        ),
        tool=Tool(
            READ_ONLY,
            "Read the timeline of a job (job_id) or of an application (application_id): its notes and recorded changes in one list, pinned notes first, then newest first. A job's timeline includes its applications' entries; an application's includes its job's. Each entry has type (note or event), kind (note, event or reply), scope (job or application), actor (who), run and either note (body, version, pinned) or event (kind, payload of identifiers and field names, subject). Filter by kinds, who (owner, agent, system, unknown), scope, since and until; counts gives the entries of each kind for the other filters. Page with limit and offset.",
        ),
    ),
    Operation(
        "notes.create",
        "notes",
        "create",
        "Archive",
        "Add a note on a job or on one of its applications, optionally pinned",
        params=(Param("job_id", str), Param("value", NoteInput)),
        call=lambda s, job_id, value: s.add_note(job_id, value),
        rest=(Route("POST", "/jobs/{job_id}/notes", "note"),),
        tool=Tool(
            WRITE,
            "Write a note on a job, or on one of its applications with application_id. The note records you as its author and your open run. pinned=true pins it: it is listed first, and a job and an application each have one pinned note (pinning unpins the previous one). The application's pinned note is its standing guidance, included in new frozen contexts.",
        ),
    ),
    Operation(
        "notes.pin",
        "notes",
        "pin",
        "Archive",
        "Pin a note first in its timeline, or unpin it",
        params=(Param("note_id", str), Param("value", NotePin)),
        call=lambda s, note_id, value: s.pin_note(note_id, value),
        rest=(Route("POST", "/notes/{note_id}/pin", "pin_note"),),
        tool=Tool(
            WRITE,
            "Pin a note (pinned=true) or unpin it (pinned=false) with its current version. A job and an application each have at most one pinned note: pinning unpins the note pinned in the same scope. Unpinning keeps the note in the timeline.",
        ),
    ),
    Operation(
        "notes.delete",
        "notes",
        "delete",
        "Archive",
        "Delete one note",
        params=(
            Param("note_id", str),
            Param("expected_version", int, rest=(Annotated[int, Query(ge=1)], REQUIRED)),
        ),
        call=lambda s, note_id, expected_version: s.delete_note(note_id, expected_version),
        rest=(Route("DELETE", "/notes/{note_id}", "remove_note"),),
        tool=Tool(
            REMOVE,
            "Delete a note for good with its current version; a note_deleted change records it.",
        ),
    ),
    Operation(
        "applications.list",
        "applications",
        "list",
        "Applications and documents",
        "Search/filter/sort paginated application summaries",
        params=(query_model(ApplicationQuery),),
        call=lambda s, value: s.list_applications(**(value or ApplicationQuery()).model_dump()),
        rest=(Route("GET", "/applications", "applications"),),
        tool=Tool(
            READ_ONLY,
            "Read paginated application summaries and stage counts (shortlisted, ready, applied, interview, offer, closed). Each row has ready, computed (Shortlisted, every required document has a current complete revision, no open blocking requirement), and missing (cv, letter, requirement:<id>), and its last_reply. Filter by exact job_id, query, stage (ready is the Shortlisted ones that are Ready), outcome, company, needs (documents: Shortlisted and missing a document; reply_overdue: Applied without a reply past the no-reply period, to close as no_response by hand), applied_since and applied_until. no_reply gives the period, its source and the number overdue. Sort by deadline or priority.",
        ),
    ),
    Operation(
        "notes.read",
        "notes",
        "get",
        "Archive",
        "Read one note and its version",
        params=(Param("note_id", str),),
        call=lambda s, note_id: s.get_note(note_id),
        rest=(Route("GET", "/notes/{note_id}", "get_note"),),
        tool=Tool(READ_ONLY, "Read one editable note with its optimistic version."),
    ),
    Operation(
        "notes.update",
        "notes",
        "update",
        "Archive",
        "Edit a note with version protection",
        params=(Param("note_id", str), Param("value", NotePatch)),
        call=lambda s, note_id, value: s.update_note(note_id, value),
        rest=(Route("PATCH", "/notes/{note_id}", "edit_note"),),
        tool=Tool(
            WRITE,
            "Edit a retained note without deleting/recreating it, using its current version.",
        ),
    ),
    Operation(
        "applications.delete",
        "applications",
        "delete",
        "Applications and documents",
        "Delete one attempt and its owned history/files",
        params=(
            Param("application_id", str),
            Param("expected_version", int, rest=(Annotated[int, Query(ge=1)], REQUIRED)),
        ),
        call=lambda s, application_id, expected_version: s.delete_application(
            application_id, expected_version
        ),
        rest=(Route("DELETE", "/applications/{application_id}", "delete_application"),),
        tool=Tool(
            REMOVE,
            "Delete one attempt and its owned documents/history, retaining the archived job and other attempts.",
        ),
    ),
    Operation(
        "applications.bulk",
        "applications",
        "bulk",
        "Applications and documents",
        "Close, reopen or delete selected application attempts",
        params=(Param("value", ApplicationBulk),),
        call=lambda s, value: s.bulk_applications(value),
        rest=(Route("POST", "/applications/bulk", "bulk_applications"),),
        tool=Tool(
            REMOVE,
            "Close (with outcome: accepted, rejected, not_pursued or no_response), reopen (to a non-Closed stage) or delete at most 200 explicit application IDs/versions, with per-item results. no_response needs a sent application and is concluded today: close the overdue ones (needs=reply_overdue) this way when the owner asks. Record an employer's answer with applications_update reply instead. Delete is permanent.",
        ),
    ),
    Operation(
        "applications.create",
        "applications",
        "create",
        "Applications and documents",
        "Start an application (stage Shortlisted)",
        params=(Param("value", ApplicationInput),),
        call=lambda s, value: s.create_application(value),
        rest=(Route("POST", "/applications", "create_application"),),
        tool=Tool(
            WRITE,
            "Start an application in stage Shortlisted and shortlist its job, optionally with the documents Ready needs (required_documents, default cv and letter), priority, deadline and employer requirements. Shortlisting a job with jobs_triage starts one too. This never sends an application or generates documents. Write standing guidance as the application's pinned note (notes_create with application_id and pinned=true).",
        ),
    ),
    Operation(
        "applications.read",
        "applications",
        "get",
        "Applications and documents",
        "Read full attempt, questions/answers, requirements and job",
        params=(Param("application_id", str),),
        call=lambda s, application_id: s.get_application(application_id),
        rest=(Route("GET", "/applications/{application_id}", "get_application"),),
        tool=Tool(
            READ_ONLY,
            "Read a single application, its job, employer requirements, required_documents, ready and missing (computed), its employer replies and its pinned note (pinned_note), the owner's standing guidance. timeline_get lists its notes and changes.",
        ),
    ),
    Operation(
        "applications.update",
        "applications",
        "update",
        "Applications and documents",
        "Record stage, Mark applied, an employer reply, outcome, priority, deadline, required documents, employer requirements and questions/answers",
        params=(Param("application_id", str), Param("value", ApplicationPatch)),
        call=lambda s, application_id, value: s.update_application(application_id, value),
        rest=(Route("PATCH", "/applications/{application_id}", "edit_application"),),
        tool=Tool(
            WRITE,
            "Record progress, priority, deadline, required documents, employer requirements and questions/answers explicitly; editing documents never marks sent. Mark applied is the owner's act (status=applied; applied_at defaults to now): never set it unless the owner says they sent the application; status=shortlisted undoes it while there is no reply. reply records an employer reply the owner reported (kind interview, rejection, offer or other; date defaults to today) and moves the stage with it in one change: interview to Interview, offer to Offer, rejection closes as rejected, other leaves the stage; reply with id corrects or removes one. Close as no_response (with concluded_on, today by default) only a sent application whose employer did not answer within the no-reply period, when the owner asks. The returned job is the compact summary. Standing guidance is the pinned note: edit it with notes_update and notes_pin.",
        ),
    ),
    Operation(
        "applications.history",
        "applications",
        "history",
        "Applications and documents",
        "Read immutable lifecycle history",
        params=(Param("application_id", str),),
        call=lambda s, application_id: s.application_events(application_id),
        rest=(Route("GET", "/applications/{application_id}/events", "events"),),
        tool=Tool(
            READ_ONLY,
            "Read the recorded lifecycle events of an attempt. timeline_get lists them with its notes and its job's entries.",
        ),
    ),
)


def register_core(router: APIRouter, workspace, requests):
    # workspace.info is hand-written: it reads the request and the open requests.
    @router.get("/workspace")
    def info(request: Request):
        return {
            "origin": os.environ.get("OPENINGS_PUBLIC_URL", str(request.base_url)).rstrip("/"),
            "name": "Openings",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "api_base": "/api/v1",
            "mcp_endpoint": "/mcp",
            "single_owner": True,
            "actor": current_actor().describe(),
            "open_requests": requests.count_open(),
            "storage": storage_status(workspace.db),
        }

    bind_rest(router, OPERATIONS, workspace)


def register_core_mcp(mcp, workspace, requests):
    @mcp.tool(annotations=READ_ONLY)
    def workspace_info(ctx: Context) -> dict:
        """Read workspace capabilities, the version and schema_version, who this token is (actor, with token_kind owner or agent), open_requests, the number of owner requests waiting for an agent (requests_list), and storage: database size, free space on the data volume, the largest backup a restore accepts and the days finished collection runs are kept. Use REST transfer grants for file bytes."""
        request = ctx.request_context.request
        origin = os.environ.get("OPENINGS_PUBLIC_URL") or (
            str(request.base_url).rstrip("/") if request else None
        )
        return {
            "name": "Openings",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "origin": origin,
            "api_base": "/api/v1",
            "actor": current_actor().describe(),
            "open_requests": requests.count_open(),
            "storage": storage_status(workspace.db),
            "workflow": "Read open requests for the agent first. Read career, templates and stored instructions; prepare a frozen context; write and compile externally; save CV and letter revisions with their PDF (and TeX source); an application is Ready when its required documents are complete. Mark applied and replies are recorded only as the owner reports them.",
        }

    bind_mcp(mcp, OPERATIONS, workspace)
