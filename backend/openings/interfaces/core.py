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
    ApplicationReady,
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
    PeriodQuery,
    TriageInput,
)
from ..operations import storage_status
from .registry import REQUIRED, Operation, Param, Route, Tool, bind_mcp, bind_rest, query_model

WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)
REMOVE = ToolAnnotations(destructiveHint=True, openWorldHint=False)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
FETCH = ToolAnnotations(destructiveHint=False, openWorldHint=True)


async def ingest(workspace, value):
    """Complete a URL or partial posting through the provider gate, then ingest it."""
    from ..fetching import complete_input

    value = await complete_input(value, workspace.discovery)
    return workspace.ingest_job(value)


OPERATIONS = (
    Operation(
        "workspace.info",
        "workspace",
        "info",
        "Archive",
        "Read workspace identity and workflow",
        rest=(Route("GET", "/workspace", "info", custom=True),),
        tool=Tool("workspace_info", READ_ONLY, custom=True),
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
            "overview_get",
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
            "jobs_search",
            READ_ONLY,
            "Search compact paginated job summaries with location/source/remote/date/queue filters; include_facets=true adds filter value lists and include_counts=true the size of each queue. Each job has its ingest signals (posting language, languages the posting requires or welcomes, the earlier job it likely duplicates with a confidence, whether the source no longer lists it, policy rules that matched) and, when dismissed, its dismissal (who, why, which rule). Filter by signal, posting_language, posting_language_not, requires, dismissed_by or rule_id. Read job_get for full content.",
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
            "jobs_bulk",
            REMOVE,
            "Apply saved/dismissed/inbox/forget to at most 200 explicit job IDs/versions, with per-item results; reason (dismissed only) is stored on each dismissal. Forget is permanent.",
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
            "jobs_resolve",
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
            "jobs_duplicates",
            READ_ONLY,
            "Read-only candidate duplicate groups, most confident first: each has a confidence in [0,1], a tier and the signals that matched or conflicted (requisition id, apply target, posting text, company and title, location), with triage and attempts. min_confidence defaults to 0.5; 0 lists every candidate. Verify before job_merge; never merges.",
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
            "job_ingest",
            FETCH,
            "Add a URL, pasted text or structured job. Duplicate identities preserve history. A new job gets its ingest signals, and an enabled rule the owner confirmed may dismiss it at once (dismissal.rule names the rule; restore it with job_triage).",
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
            "job_get",
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
            "job_update",
            WRITE,
            "Correct job fields using the version returned by job_get. Returns the compact job summary; read job_get for full text.",
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
            "job_triage",
            WRITE,
            "Set inbox/saved/dismissed and return the compact job summary. Use queue=inbox/shortlist/applications for actionable queues; saved is retained interest. When dismissing, give a short reason (shown to the owner beside the dismissal); the dismissal records who made it and can be restored.",
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
            "job_distinct",
            WRITE,
            "Record that a job flagged as a likely duplicate (signals.duplicate) is a different vacancy from other_id: the flag is cleared and does not return. Merge verified duplicates with job_merge instead.",
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
            "job_merge",
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
            "job_forget",
            REMOVE,
            "Permanently delete the current version of a job and its application/file history. Future acquisition is new.",
        ),
    ),
    Operation(
        "notes.list",
        "notes",
        "list",
        "Archive",
        "List job notes",
        params=(Param("job_id", str),),
        call=lambda s, job_id: s.list_notes(job_id),
        rest=(Route("GET", "/jobs/{job_id}/notes", "notes"),),
        tool=Tool("notes_list", READ_ONLY, "Read notes retained with a job."),
    ),
    Operation(
        "notes.create",
        "notes",
        "create",
        "Archive",
        "Add a job note with optional application association",
        params=(Param("job_id", str), Param("value", NoteInput)),
        call=lambda s, job_id, value: s.add_note(job_id, value),
        rest=(Route("POST", "/jobs/{job_id}/notes", "note"),),
        tool=Tool(
            "note_add",
            WRITE,
            "Store a note, optionally associated with a particular application attempt.",
        ),
    ),
    Operation(
        "notes.delete",
        "notes",
        "delete",
        "Archive",
        "Delete one note",
        params=(Param("note_id", str),),
        call=lambda s, note_id: s.delete_note(note_id),
        rest=(Route("DELETE", "/notes/{note_id}", "remove_note"),),
        tool=Tool("note_delete", REMOVE, "Remove an individual note."),
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
            "applications_list",
            READ_ONLY,
            "Read paginated application summaries, stage totals and the ready count. Filter by exact job_id, query, stage, outcome, company or readiness (readiness=ready is the stored Ready step; reviewed passes every check but is not marked; ready=false lists the Preparing ones not marked); applied_since and applied_until filter by the time recorded as applied; no_reply_due=true lists the Applied applications past the no-reply period, to propose closing them as no_response. Each row has its last_response; no_reply gives the period, its source (the policy's No reply decision item and whether the owner confirmed it, or the 30-day default) and the number due. Sort by deadline, priority or ready time.",
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
        tool=Tool("note_get", READ_ONLY, "Read one editable note with its optimistic version."),
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
            "note_update",
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
            "application_delete",
            REMOVE,
            "Delete one attempt and its owned documents/history, retaining the archived job and other attempts.",
        ),
    ),
    Operation(
        "applications.bulk",
        "applications",
        "bulk",
        "Applications and documents",
        "Close, reopen, mark ready, unmark ready or delete selected application attempts",
        params=(Param("value", ApplicationBulk),),
        call=lambda s, value: s.bulk_applications(value),
        rest=(Route("POST", "/applications/bulk", "bulk_applications"),),
        tool=Tool(
            "applications_bulk",
            REMOVE,
            "Close (with outcome: accepted, rejected, not_pursued or no_response), reopen (to a non-Closed stage), mark_ready, unmark_ready or delete at most 200 explicit application IDs/versions, with per-item results. Closing as rejected records a rejection response dated today; no_response needs a sent application and is concluded today. Delete is permanent.",
        ),
    ),
    Operation(
        "applications.create",
        "applications",
        "create",
        "Applications and documents",
        "Start application preparation (draft)",
        params=(Param("value", ApplicationInput),),
        call=lambda s, value: s.create_application(value),
        rest=(Route("POST", "/applications", "create_application"),),
        tool=Tool(
            "application_create",
            WRITE,
            "Create a draft attempt, optionally with priority, deadline and employer requirements. This never sends an application or generates documents.",
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
            "application_get",
            READ_ONLY,
            "Read a single application, its job, employer requirements, derived readiness, the stored Ready step (ready_at, ready_by) and its employer responses.",
        ),
    ),
    Operation(
        "applications.update",
        "applications",
        "update",
        "Applications and documents",
        "Record stage, outcome, priority, deadline, employer requirements, questions/answers and application instructions",
        params=(Param("application_id", str), Param("value", ApplicationPatch)),
        call=lambda s, application_id, value: s.update_application(application_id, value),
        rest=(Route("PATCH", "/applications/{application_id}", "edit_application"),),
        tool=Tool(
            "application_update",
            WRITE,
            "Record progress, priority, deadline, employer requirements and questions/answers explicitly; editing documents never marks sent. Moving to Interview or Offer, or closing as rejected (or accepted without an offer on record), records the matching employer response dated response_date (today by default) with response_note. Close as no_response (with concluded_on, today by default) only a sent application whose employer did not answer within the no-reply period. Record only what the owner reported. The returned job is the compact summary.",
        ),
    ),
    Operation(
        "applications.ready",
        "applications",
        "ready",
        "Applications and documents",
        "Mark a Preparing application ready to apply, or clear the mark",
        params=(Param("application_id", str), Param("value", ApplicationReady)),
        call=lambda s, application_id, value: s.set_ready(application_id, value),
        rest=(Route("POST", "/applications/{application_id}/ready", "ready_application"),),
        tool=Tool(
            "application_ready",
            WRITE,
            "Mark a Preparing application ready to apply (ready=true) or clear the mark (ready=false), using its current version. Refused with application_not_ready naming the failed check (stage, blocked, none, missing_pdf, unreviewed). The mark is cleared automatically when a revision, context, file or blocking requirement changes. This never submits anything.",
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
            "application_history", READ_ONLY, "Read the recorded lifecycle events of an attempt."
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
            "workflow": "Read open requests for the agent first. Read career, templates and stored instructions; prepare a frozen context; write and compile externally; submit document revisions and PDF/source files; track progress explicitly.",
        }

    bind_mcp(mcp, OPERATIONS, workspace)
