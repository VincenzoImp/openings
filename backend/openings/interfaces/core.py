"""Operations of the workspace: the start read, jobs, notes, applications, Stats, the change
log and the shipped skills.

The MCP tools are the agent's interface (batch reads and writes); the operations
declared with ``mcp=`` are REST routes the dashboard and scripts keep, whose work
the named tool does.
"""

import os
from typing import Annotated

from fastapi import Query

from .. import __version__
from ..actors import current_actor
from ..context import ContextQuery
from ..db import SCHEMA_VERSION
from ..events import EventQuery
from ..models import (
    ApplicationBulk,
    ApplicationIds,
    ApplicationInput,
    ApplicationPatch,
    ApplicationQuery,
    ApplicationsCreate,
    ApplicationsUpdate,
    DistinctInput,
    DuplicateQuery,
    JobBulk,
    JobIds,
    JobInput,
    JobPatch,
    JobQuery,
    JobResolve,
    JobTriage,
    LinkInput,
    MergeInput,
    NoteInput,
    NotePatch,
    NotePin,
    TimelineQuery,
    TriageInput,
)
from ..operations import storage_status
from ..responses import (
    Application,
    ApplicationBatch,
    ApplicationChange,
    ApplicationPage,
    BatchResult,
    Deleted,
    DuplicatePage,
    EventPage,
    Job,
    JobBatch,
    JobPage,
    JobSummary,
    Note,
    NoteList,
    ResolvedJobs,
    Skill,
    SkillList,
    Stats,
    Timeline,
    WorkspaceContext,
    WorkspaceInfo,
)
from ..skills import SKILL_FILE, list_skills, read_skill
from ..stats import StatsQuery
from .operation import DESTRUCTIVE, WRITE, WS, Q, operation, request_origin

Version = Annotated[int, Query(ge=1)]

WORKFLOW = (
    "Read workspace_context first; write and compile CV and letter externally; save each "
    "revision with its PDF (and TeX source); an application is Ready when its required "
    "documents are complete. Mark applied and replies only as the owner reports them."
)


def _origin():
    return os.environ.get("OPENINGS_PUBLIC_URL") or request_origin.get()


def absolute(grant):
    """Resolve a grant's url against the public origin, so an agent can use it as given."""
    origin = (_origin() or "").rstrip("/")
    if grant["url"].startswith("/"):
        grant["url"] = origin + grant["url"]
    return grant


def with_curl(grant, name):
    """Add the shell line that uses a transfer grant: a PUT of the file ``name`` or a GET."""
    url = absolute(grant)["url"]
    headers = " ".join(f"-H '{key}: {value}'" for key, value in grant["headers"].items())
    if grant["method"] == "PUT":
        grant["curl"] = f"curl -fsS -X PUT {headers} --data-binary @'{name}' '{url}'"
    else:
        grant["curl"] = f"curl -fsS {headers} -o '{name}' '{url}'"
    return grant


# Workspace


@operation("GET /workspace/context", tags=["workspace"])
def workspace_context(ws: WS, query: Q[ContextQuery]) -> WorkspaceContext:
    """Start here: what to know before deciding or writing.

    Counts, settings, profile, Preferences, career summary, templates, skills and feedback
    (the owner's corrections of agent work since your last read).
    """
    return ws.context.context(query, origin=_origin())


@operation("GET /workspace", tags=["workspace"], mcp="workspace_context")
def workspace_info(ws: WS) -> WorkspaceInfo:
    """Read the workspace identity.

    Version, schema, this token's actor label, storage and the workflow.
    """
    return {
        "origin": _origin(),
        "name": "Openings",
        "version": __version__,
        "schema_version": SCHEMA_VERSION,
        "api_base": "/api/v1",
        "mcp_endpoint": "/mcp",
        "single_owner": True,
        "actor": current_actor().label,
        "storage": storage_status(ws.db),
        "workflow": WORKFLOW,
    }


@operation("GET /changes", tags=["workspace"])
def changes_list(ws: WS, query: Q[EventQuery]) -> EventPage:
    """List recorded changes, newest first.

    Each with actor (owner, agent:<name>, system), batch_id and subject. Filter by job_id,
    application_id, subject, actor, batch_id or dates.
    """
    return ws.events.list_events(query)


@operation("GET /stats", tags=["applications"])
def stats_get(ws: WS, query: Q[StatsQuery]) -> Stats:
    """Read how employers answered.

    For applications sent in a period (90d, 12m, all): replies, interviews, rates, median
    days to a reply, the funnel.
    """
    return ws.stats.stats(query)


@operation("GET /skills", "GET /skills/{name}", tags=["workspace"])
def skills_get(ws: WS, name: str = "", path: str = SKILL_FILE) -> Skill | SkillList:
    """Read a skill, or without name the list of skills.

    A skill is the method for one kind of work; path reads one of its reference files.
    """
    if not name:
        return list_skills(ws.skills)
    return read_skill(ws.skills, name, path)


# Jobs


@operation("GET /jobs", tags=["jobs"])
def jobs_list(ws: WS, query: Q[JobQuery]) -> JobPage:
    """Search job summaries.

    Filter by triage, q, url, signal, requires, posting_language, hide_unspoken_required,
    dismissed_by, batch_id; include_counts adds totals. jobs_get has the posting.
    """
    return ws.list_jobs(**query.model_dump())


@operation("GET /jobs/batch", tags=["jobs"])
def jobs_get(ws: WS, query: Q[JobIds]) -> JobBatch:
    """Read up to 20 jobs in full.

    Posting text, metadata, signals, dismissal, application and notes.
    """
    return ws.read_jobs(query)


@operation("POST /jobs/triage", access=WRITE, tags=["jobs"])
def jobs_triage(ws: WS, body: JobTriage) -> BatchResult:
    """Triage up to 200 jobs: new, shortlisted or dismissed.

    shortlisted starts the job's application; dismissed needs a reason the owner reads.
    Each item has its own result.
    """
    return ws.triage_jobs(body)


@operation("POST /jobs", access=WRITE, open_world=True, tags=["jobs"])
async def jobs_create(ws: WS, body: JobInput) -> Job:
    """Add a job from a URL, pasted text or fields.

    A URL is read through the provider gate. A known job is returned (created false); a
    retry with the same idempotency_key returns the same job.
    """
    from ..fetching import complete_input
    from ..idempotency import fingerprint

    digest = fingerprint(body)
    replayed = ws.replayed_job(body.idempotency_key, digest)
    if replayed:
        return replayed
    body = await complete_input(body, ws.discovery)
    return ws.ingest_job(body, digest=digest)


@operation("GET /jobs/resolve", tags=["jobs"], mcp="jobs_list")
def jobs_resolve(ws: WS, query: Q[JobResolve]) -> ResolvedJobs:
    """Look up archived jobs by URL or source key.

    With triage and every application. Never ingests or fetches.
    """
    return ws.resolve_jobs(query)


@operation("GET /jobs/duplicates", tags=["jobs"], mcp="jobs_list")
def jobs_duplicates(ws: WS, query: Q[DuplicateQuery]) -> DuplicatePage:
    """List candidate duplicate job groups.

    Most confident first, with the signals that matched. min_confidence defaults to 0.5.
    """
    return ws.duplicate_jobs(query)


@operation("POST /jobs/bulk", access=DESTRUCTIVE, tags=["jobs"], mcp="jobs_triage")
def jobs_bulk(ws: WS, body: JobBulk) -> BatchResult:
    """Shortlist, dismiss, restore or forget selected jobs.

    Up to 200 ids with versions, one result each; forget is permanent.
    """
    return ws.bulk_jobs(body)


@operation("GET /jobs/{job_id}", tags=["jobs"], mcp="jobs_get")
def jobs_read(ws: WS, job_id: str) -> Job:
    """Read a job in full."""
    return ws.get_job(job_id)


@operation("PATCH /jobs/{job_id}", access=WRITE, tags=["jobs"])
def jobs_update(ws: WS, job_id: str, body: JobPatch) -> JobSummary:
    """Correct a job's fields.

    title, company, location, url, posting or metadata, with the job's version.
    """
    return ws.update_job(job_id, body)


@operation("POST /jobs/{job_id}/link", access=WRITE, tags=["jobs"])
def jobs_link(ws: WS, job_id: str, body: LinkInput) -> JobSummary:
    """Decide a likely duplicate.

    same merges job_id into other_id (other_id survives, with postings, applications and
    notes); different clears the flag for good. Returns the job that remains.
    """
    return ws.link_jobs(job_id, body)


@operation("POST /jobs/{job_id}/triage", access=WRITE, tags=["jobs"], mcp="jobs_triage")
def jobs_triage_one(ws: WS, job_id: str, body: TriageInput) -> JobSummary:
    """Shortlist, dismiss or return one job to review, with its version."""
    return ws.set_triage(job_id, body.triage, body.expected_version, body.reason)


@operation("POST /jobs/{job_id}/distinct", access=WRITE, tags=["jobs"], mcp="jobs_link")
def jobs_distinct(ws: WS, job_id: str, body: DistinctInput) -> JobSummary:
    """Mark a likely duplicate as a different vacancy."""
    return ws.mark_distinct(job_id, body.other_id)


@operation("POST /jobs/{job_id}/merge", access=DESTRUCTIVE, tags=["jobs"], mcp="jobs_link")
def jobs_merge(ws: WS, job_id: str, body: MergeInput) -> Job:
    """Merge a job into target_id, keeping postings, applications and notes."""
    return ws.merge_jobs(job_id, body.target_id, body.expected_version, body.target_version)


@operation("DELETE /jobs/{job_id}", access=DESTRUCTIVE, tags=["jobs"])
def jobs_delete(ws: WS, job_id: str, expected_version: Version) -> Deleted:
    """Delete a job permanently, only on the owner's explicit request.

    With its applications, documents and files; collecting it again makes a new job.
    """
    return ws.forget_job(job_id, expected_version)


@operation(
    "GET /jobs/{job_id}/timeline",
    "GET /applications/{application_id}/timeline",
    tags=["jobs", "applications"],
    mcp="changes_list",
)
def timeline_get(
    ws: WS, query: Q[TimelineQuery], job_id: str | None = None, application_id: str | None = None
) -> Timeline:
    """Read the timeline of a job or an application.

    Notes and recorded changes, pinned notes first, then newest first.
    """
    return ws.timeline(job_id, application_id, query)


# Notes


@operation("GET /jobs/{job_id}/notes", tags=["notes"], mcp="jobs_get")
def notes_list(ws: WS, job_id: str) -> NoteList:
    """List the notes of a job and its applications."""
    return ws.list_notes(job_id)


@operation("POST /jobs/{job_id}/notes", access=WRITE, tags=["notes"])
def notes_create(ws: WS, job_id: str, body: NoteInput) -> Note:
    """Add a note to a job, or to its application (application_id).

    pinned lists it first and unpins the other; an application's pinned note is the owner's
    guidance for its documents.
    """
    return ws.add_note(job_id, body)


@operation("GET /notes/{note_id}", tags=["notes"], mcp="jobs_get")
def notes_get(ws: WS, note_id: str) -> Note:
    """Read a note and its version."""
    return ws.get_note(note_id)


@operation("PATCH /notes/{note_id}", access=WRITE, tags=["notes"])
def notes_update(ws: WS, note_id: str, body: NotePatch) -> Note:
    """Edit a note's body, pin or unpin it, with its version."""
    return ws.update_note(note_id, body)


@operation("POST /notes/{note_id}/pin", access=WRITE, tags=["notes"], mcp="notes_update")
def notes_pin(ws: WS, note_id: str, body: NotePin) -> Note:
    """Pin or unpin a note, with its version."""
    return ws.pin_note(note_id, body)


@operation("DELETE /notes/{note_id}", access=DESTRUCTIVE, tags=["notes"])
def notes_delete(ws: WS, note_id: str, expected_version: Version) -> Deleted:
    """Delete a note, with its version."""
    return ws.delete_note(note_id, expected_version)


# Applications


@operation("GET /applications", tags=["applications"])
def applications_list(ws: WS, query: Q[ApplicationQuery]) -> ApplicationPage:
    """Search application summaries with stage counts.

    Each with ready, missing and last_reply. Filter by stage (ready: Shortlisted and Ready),
    needs (documents, reply_overdue), job_id, q, outcome, company, applied dates.
    """
    return ws.list_applications(**query.model_dump())


@operation("GET /applications/batch", tags=["applications"])
def applications_get(ws: WS, query: Q[ApplicationIds]) -> ApplicationBatch:
    """Read up to 20 applications in full.

    Job summary, required documents, ready and missing, requirements, questions, answers,
    replies, revisions and notes (the pinned one is the owner's guidance).
    """
    return ws.read_applications(query)


@operation("POST /applications/batch", access=WRITE, tags=["applications"])
def applications_create(ws: WS, body: ApplicationsCreate) -> BatchResult:
    """Start applications for up to 50 jobs (stage Shortlisted; shortlists the job).

    A job's open application is returned (created false) and takes the item's fields while
    Shortlisted. Never sends anything.
    """
    return ws.create_applications(body)


@operation("PATCH /applications/batch", access=WRITE, tags=["applications"])
def applications_update(ws: WS, body: ApplicationsUpdate) -> BatchResult:
    """Update up to 200 applications: stage, outcome, reply, fields.

    A reply moves the stage. Set stage applied only when the owner says they applied.
    Ready is computed. Each item has its own result.
    """
    return ws.update_applications(body)


@operation("POST /applications", access=WRITE, tags=["applications"], mcp="applications_create")
def applications_start(ws: WS, body: ApplicationInput) -> ApplicationChange:
    """Start one application in stage Shortlisted; shortlists its job."""
    return ws.create_application(body)


@operation(
    "POST /applications/bulk",
    access=DESTRUCTIVE,
    tags=["applications"],
    mcp="applications_update",
)
def applications_bulk(ws: WS, body: ApplicationBulk) -> BatchResult:
    """Close, reopen or delete selected applications.

    Up to 200 ids with versions, one result each.
    """
    return ws.bulk_applications(body)


@operation("GET /applications/{application_id}", tags=["applications"], mcp="applications_get")
def applications_read(ws: WS, application_id: str) -> Application:
    """Read an application in full."""
    return ws.get_application(application_id)


@operation(
    "PATCH /applications/{application_id}",
    access=WRITE,
    tags=["applications"],
    mcp="applications_update",
)
def applications_change(ws: WS, application_id: str, body: ApplicationPatch) -> ApplicationChange:
    """Update one application, with its version.

    Stage (status), reply, outcome, priority, deadline, documents, requirements, answers.
    """
    return ws.update_application(application_id, body)


@operation("DELETE /applications/{application_id}", access=DESTRUCTIVE, tags=["applications"])
def applications_delete(ws: WS, application_id: str, expected_version: Version) -> Deleted:
    """Delete an application permanently, only on the owner's explicit request.

    With its documents and history; the job stays.
    """
    return ws.delete_application(application_id, expected_version)
