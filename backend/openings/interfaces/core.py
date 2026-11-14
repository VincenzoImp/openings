"""Operations of the workspace: identity, jobs, notes, the timeline, applications, Stats,
the change log and the shipped skills."""

import os
from typing import Annotated

from fastapi import Query

from .. import __version__
from ..actors import current_actor
from ..db import SCHEMA_VERSION
from ..events import EventQuery
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
    TimelineQuery,
    TriageInput,
)
from ..operations import storage_status
from ..responses import (
    Application,
    ApplicationChange,
    ApplicationPage,
    BatchResult,
    Deleted,
    DuplicatePage,
    EventPage,
    Job,
    JobPage,
    JobSummary,
    Note,
    NoteList,
    ResolvedJobs,
    Skill,
    SkillList,
    Stats,
    Timeline,
    WorkspaceInfo,
)
from ..skills import SKILL_FILE, list_skills, read_skill
from ..stats import StatsQuery
from .operation import DESTRUCTIVE, WRITE, WS, Q, operation, request_origin

Version = Annotated[int, Query(ge=1)]

WORKFLOW = (
    "Read Preferences, career, templates and the application; write and compile externally; "
    "save CV and letter revisions with their PDF (and TeX source); an application is Ready "
    "when its required documents are complete. Mark applied and replies are recorded only as "
    "the owner reports them. Report what you did in the chat."
)


@operation("GET /workspace", tags=["workspace"])
def workspace_info(ws: WS) -> WorkspaceInfo:
    """Read the workspace identity.

    The version and schema_version, who this token is (actor: owner or agent:<token name>,
    the label its changes carry), storage (size, free space, restore limit, retention) and
    the workflow. File bytes use REST transfer grants.
    """
    return {
        "origin": os.environ.get("OPENINGS_PUBLIC_URL") or request_origin.get(),
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


@operation("GET /jobs", tags=["jobs"])
def jobs_list(ws: WS, query: Q[JobQuery]) -> JobPage:
    """Search job summaries.

    Compact pages filtered by triage, text, company, location, source, dates, signals
    (language, required languages, likely duplicate, no longer listed), who dismissed them
    or batch_id. include_counts and include_facets add totals; jobs_get has the text.
    """
    return ws.list_jobs(**query.model_dump())


@operation("POST /jobs/bulk", access=DESTRUCTIVE, tags=["jobs"])
def jobs_bulk(ws: WS, body: JobBulk) -> BatchResult:
    """Shortlist, dismiss, restore or forget selected jobs.

    Up to 200 job ids with versions, one result each. shortlisted starts each application;
    new or dismissed undoes a shortlist whose application is empty; reason goes with
    dismissed; forget is permanent.
    """
    return ws.bulk_jobs(body)


@operation("GET /jobs/resolve", tags=["jobs"])
def jobs_resolve(ws: WS, query: Q[JobResolve]) -> ResolvedJobs:
    """Look up archived jobs by URL or source key.

    Archived jobs matching a url or source_key, with triage and every application. Never
    ingests or fetches.
    """
    return ws.resolve_jobs(query)


@operation("GET /jobs/duplicates", tags=["jobs"])
def jobs_duplicates(ws: WS, query: Q[DuplicateQuery]) -> DuplicatePage:
    """List candidate duplicate job groups.

    Most confident first, each with a confidence in [0,1], a tier and the signals that
    matched or conflicted. min_confidence defaults to 0.5 (0 lists all). Verify before
    jobs_merge; never merges.
    """
    return ws.duplicate_jobs(query)


@operation("POST /jobs", access=WRITE, open_world=True, tags=["jobs"])
async def jobs_create(ws: WS, body: JobInput) -> Job:
    """Add a job from a URL, pasted text or fields.

    A URL is read through the provider gate. A known identity adds to its job's history; a
    new job gets its signals. A retry with the same idempotency_key returns the same job.
    """
    from ..fetching import complete_input
    from ..idempotency import fingerprint

    digest = fingerprint(body)
    replayed = ws.replayed_job(body.idempotency_key, digest)
    if replayed:
        return replayed
    body = await complete_input(body, ws.discovery)
    return ws.ingest_job(body, digest=digest)


@operation("GET /jobs/{job_id}", tags=["jobs"])
def jobs_get(ws: WS, job_id: str) -> Job:
    """Read a job in full.

    Posting text, metadata, version, observations (unlisted_at when a board stopped listing
    one), signals and dismissal.
    """
    return ws.get_job(job_id)


@operation("PATCH /jobs/{job_id}", access=WRITE, tags=["jobs"])
def jobs_update(ws: WS, job_id: str, body: JobPatch) -> JobSummary:
    """Correct a job's fields.

    With the version jobs_get returned; returns the compact summary.
    """
    return ws.update_job(job_id, body)


@operation("POST /jobs/{job_id}/triage", access=WRITE, tags=["jobs"])
def jobs_triage(ws: WS, job_id: str, body: TriageInput) -> JobSummary:
    """Shortlist, dismiss or return a job to review.

    shortlisted starts the job's application. Back to new or dismissed removes it only while
    it is empty (else 409 application_has_work). Give a short reason when dismissing; a
    dismissal can be restored.
    """
    return ws.set_triage(job_id, body.triage, body.expected_version, body.reason)


@operation("POST /jobs/{job_id}/distinct", access=WRITE, tags=["jobs"])
def jobs_distinct(ws: WS, job_id: str, body: DistinctInput) -> JobSummary:
    """Mark a likely duplicate as a different vacancy.

    The duplicate flag against other_id is cleared for good. Merge verified duplicates with
    jobs_merge instead.
    """
    return ws.mark_distinct(job_id, body.other_id)


@operation("POST /jobs/{job_id}/merge", access=DESTRUCTIVE, tags=["jobs"])
def jobs_merge(ws: WS, job_id: str, body: MergeInput) -> Job:
    """Merge verified duplicate jobs.

    Merges the job into target_id, keeping postings, applications and notes.
    """
    return ws.merge_jobs(job_id, body.target_id, body.expected_version, body.target_version)


@operation("DELETE /jobs/{job_id}", access=DESTRUCTIVE, tags=["jobs"])
def jobs_delete(ws: WS, job_id: str, expected_version: Version) -> Deleted:
    """Forget a job permanently.

    Deletes the job, its applications and files; acquiring it again later makes a new job.
    """
    return ws.forget_job(job_id, expected_version)


@operation("GET /jobs/{job_id}/notes", tags=["notes"])
def notes_list(ws: WS, job_id: str) -> NoteList:
    """List the notes of a job and its applications.

    Pinned first, each with its scope and author. timeline_get lists them with the changes.
    """
    return ws.list_notes(job_id)


@operation(
    "GET /jobs/{job_id}/timeline",
    "GET /applications/{application_id}/timeline",
    tags=["jobs", "applications"],
)
def timeline_get(
    ws: WS, query: Q[TimelineQuery], job_id: str | None = None, application_id: str | None = None
) -> Timeline:
    """Read the timeline of a job or an application.

    Give job_id or application_id. Notes and recorded changes, pinned notes first, then
    newest first, each with kind, scope, actor and batch_id. Filter by kinds, who, scope and
    dates; counts per kind.
    """
    return ws.timeline(job_id, application_id, query)


@operation("POST /jobs/{job_id}/notes", access=WRITE, tags=["notes"])
def notes_create(ws: WS, job_id: str, body: NoteInput) -> Note:
    """Add a note to a job or one of its applications.

    application_id puts it on the application. pinned=true lists it first and unpins the
    previous one; an application's pinned note is the owner's guidance for its documents.
    """
    return ws.add_note(job_id, body)


@operation("POST /notes/{note_id}/pin", access=WRITE, tags=["notes"])
def notes_pin(ws: WS, note_id: str, body: NotePin) -> Note:
    """Pin or unpin a note.

    With its version. One pinned note per job and per application: pinning unpins the other.
    """
    return ws.pin_note(note_id, body)


@operation("DELETE /notes/{note_id}", access=DESTRUCTIVE, tags=["notes"])
def notes_delete(ws: WS, note_id: str, expected_version: Version) -> Deleted:
    """Delete a note.

    With its version; the history records the deletion.
    """
    return ws.delete_note(note_id, expected_version)


@operation("GET /notes/{note_id}", tags=["notes"])
def notes_get(ws: WS, note_id: str) -> Note:
    """Read a note and its version."""
    return ws.get_note(note_id)


@operation("PATCH /notes/{note_id}", access=WRITE, tags=["notes"])
def notes_update(ws: WS, note_id: str, body: NotePatch) -> Note:
    """Edit a note.

    Replaces its body, with its version.
    """
    return ws.update_note(note_id, body)


@operation("GET /applications", tags=["applications"])
def applications_list(ws: WS, query: Q[ApplicationQuery]) -> ApplicationPage:
    """Search application summaries.

    Pages with stage counts; each row has ready, missing and last_reply. Filter by job_id,
    text, stage (ready: Shortlisted and Ready), outcome, company, needs and applied dates.
    no_reply gives the period and the overdue count.
    """
    return ws.list_applications(**query.model_dump())


@operation("DELETE /applications/{application_id}", access=DESTRUCTIVE, tags=["applications"])
def applications_delete(ws: WS, application_id: str, expected_version: Version) -> Deleted:
    """Delete an application.

    Deletes it with its documents and history; the job and other applications stay.
    """
    return ws.delete_application(application_id, expected_version)


@operation("POST /applications/bulk", access=DESTRUCTIVE, tags=["applications"])
def applications_bulk(ws: WS, body: ApplicationBulk) -> BatchResult:
    """Close, reopen or delete selected applications.

    Up to 200 ids with versions, one result each. close takes an outcome (no_response only
    for a sent application, when the owner asks); reopen a stage. Record replies with
    applications_update.
    """
    return ws.bulk_applications(body)


@operation("POST /applications", access=WRITE, tags=["applications"])
def applications_create(ws: WS, body: ApplicationInput) -> ApplicationChange:
    """Start an application.

    Stage Shortlisted; shortlists its job. Optional required_documents (default cv and
    letter), priority, deadline, questions and requirements. Never sends an application.
    """
    return ws.create_application(body)


@operation("GET /applications/{application_id}", tags=["applications"])
def applications_get(ws: WS, application_id: str) -> Application:
    """Read an application in full.

    Its job, requirements, questions and answers, required_documents, ready and missing,
    replies and pinned_note (the owner's guidance).
    """
    return ws.get_application(application_id)


@operation("PATCH /applications/{application_id}", access=WRITE, tags=["applications"])
def applications_update(ws: WS, application_id: str, body: ApplicationPatch) -> ApplicationChange:
    """Update an application.

    Stage, reply, outcome, priority, deadline, documents, requirements, answers. Mark applied
    (status=applied) only when the owner says it was sent. A reply moves the stage. Close as
    no_response only when the owner asks.
    """
    return ws.update_application(application_id, body)


@operation("GET /applications/{application_id}/events", tags=["applications"])
def applications_history(ws: WS, application_id: str) -> EventPage:
    """Read an application's recorded changes.

    timeline_get lists them with its notes and its job's entries.
    """
    return ws.application_events(application_id)


@operation("GET /stats", tags=["applications"])
def stats_get(ws: WS, query: Q[StatsQuery]) -> Stats:
    """Read how employers answered.

    Applications sent in a period (90d, 12m, all): replies and interviews with rates, median
    days to the first reply, the funnel, and replies by source when there is enough data.
    """
    return ws.stats.stats(query)


@operation("GET /events", tags=["workspace"])
def events_list(ws: WS, query: Q[EventQuery]) -> EventPage:
    """List recorded changes.

    Newest first, each with its actor label, batch_id and subject. Filter by actor, batch_id,
    dates, job, application, subject or kind; system changes only with actor=system or
    include_system.
    """
    return ws.events.list_events(query)


@operation("GET /skills", tags=["workspace"])
def skills_list(ws: WS) -> SkillList:
    """List the shipped agent skills.

    Workflow skills for agents using Openings, with what the owner can ask and their
    reference files. Read one with skills_get.
    """
    return list_skills(ws.skills)


@operation("GET /skills/{name}", tags=["workspace"])
def skills_get(ws: WS, name: str, path: str = SKILL_FILE) -> Skill:
    """Read a skill or one of its reference files.

    SKILL.md or a listed reference file (path), as Markdown; relative links resolve against
    the skill's directory. The owner's instructions are in Preferences.
    """
    return read_skill(ws.skills, name, path)
