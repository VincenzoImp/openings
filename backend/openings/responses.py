"""Response models: what each operation returns, for OpenAPI and the generated client.

The services return plain dictionaries; REST validates them against these models
and leaves out what a record does not carry (``response_model_exclude_unset``).
Every model allows fields it does not name, so a new field reaches clients before
its model names it. A field that only some records or options carry has a default.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

Number = int | float
Json = dict[str, Any]


class Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class Record(Out):
    id: str
    version: int


class Page(Out):
    total: int
    limit: int | None = None
    offset: int | None = None


class Deleted(Out):
    """A permanent deletion."""

    deleted: bool
    id: str | None = None
    name: str | None = None


class TransferGrant(Out):
    """A one-shot grant: send the request to ``url`` with ``headers`` before it expires."""

    url: str = Field(description="Absolute, on the workspace's public origin.")
    method: str
    headers: dict[str, str]
    curl: str | None = Field(default=None, description="The same request as a shell line.")


class FileGrant(TransferGrant):
    expires_at: str
    max_bytes: int | None = None


class OperationGrant(TransferGrant):
    expires_in: int


# Batches


class BatchItem(Out):
    index: int = Field(description="The item's position in the request.")
    id: str | None = Field(default=None, description="The record; none for a failed create.")
    ok: bool
    version: int | None = Field(default=None, description="The record's version after a change.")
    result: Json | None = None
    error: Json | None = Field(default=None, description="The Error body of a failed item.")


class BatchResult(Out):
    """One result per selected item; each item succeeds or fails on its own."""

    batch_id: str | None = Field(
        default=None, description="The batch of the recorded changes (changes_list batch_id)."
    )
    items: list[BatchItem]
    total: int
    succeeded: int
    failed: int


# Workspace


class Storage(Out):
    database_bytes: int
    free_bytes: int
    restore_limit_bytes: int
    restore_limit_configured_bytes: int | None = None
    retention_days: int
    kept_runs_per_source: int


class WorkspaceInfo(Out):
    name: str
    version: str
    schema_version: int
    origin: str | None = None
    api_base: str
    mcp_endpoint: str
    single_owner: bool
    actor: str = Field(description="owner, agent:<token name> or system: the label of changes.")
    storage: Storage
    workflow: str


class WorkspaceContext(Out):
    """workspace_context: what to know before deciding or writing."""

    workspace: Json
    counts: dict[str, int]
    settings: Json
    profile: Json
    preferences: Json
    career: list[Json]
    templates: list[Json]
    skills: list[Json]
    feedback: list[Json] = Field(
        default=[], description="The owner's corrections of agent work since the previous read."
    )


class Event(Out):
    id: str
    kind: str
    created_at: str
    actor: str | None = None
    batch_id: str | None = None
    job_id: str | None = None
    application_id: str | None = None
    payload: Json = {}
    subject: Json | None = None


class EventPage(Page):
    items: list[Event]


class SkillSummary(Out):
    name: str
    title: str
    summary: str
    description: str
    example: str
    files: list[str]
    file_details: list[Json] = []


class SkillList(Out):
    items: list[SkillSummary]
    total: int


class Skill(Out):
    name: str
    path: str
    content: str


# Jobs


class ApplicationRef(Out):
    id: str
    stage: str
    outcome: str | None = None
    version: int


class Signals(Out):
    computed: bool
    language: str | None = None
    language_confidence: Number | None = None
    required: list[list[str]] = Field(
        default=[], description="Groups of language codes; one language of a group is enough."
    )
    duplicate_checked: bool
    duplicate: Json | None = Field(default=None, description="{job_id, confidence, tier}")
    no_longer_listed: bool
    unlisted_at: str | None = None


class Dismissal(Out):
    at: str | None = None
    by: str | None = None
    category: str
    reason: str = ""


class JobSummary(Record):
    """A compact job: list rows and the result of a change."""

    title: str
    company: str
    location: str
    url: str
    triage: str
    complete: bool
    created_at: str
    updated_at: str | None = None
    content_version: int | None = None
    metadata: Json = {}
    posting_preview: str | None = None
    source: str | None = None
    job_type: str | None = None
    application: ApplicationRef | None = None
    application_count: int
    signals: Signals
    dismissal: Dismissal | None = None


class Observation(Out):
    id: str
    url: str
    identity: str
    source_id: str | None = None
    source_name: str | None = None
    source_kind: str | None = None
    first_seen_at: str
    last_seen_at: str
    unlisted_at: str | None = None


class Job(JobSummary):
    """A job in full: the posting, its overrides and every observation."""

    posting: str
    overrides: Json = {}
    postings: list[Observation] = []
    created: bool | None = Field(default=None, description="On jobs_create: a new job.")
    needs_text: bool | None = Field(
        default=None,
        description="On jobs_create: the posting text could not be read; add it with jobs_update.",
    )


class JobCounts(Out):
    all: int
    new: int
    shortlisted: int
    dismissed: int
    dismissed_by: dict[str, int]


class JobPage(Page):
    items: list[JobSummary]
    counts: JobCounts | None = None
    facets: dict[str, list[str]] | None = None
    unspoken_required: Json | None = None


class ResolvedJob(JobSummary):
    matched_by: list[str]
    applications: list[Json] = []


class ResolvedJobs(Out):
    items: list[ResolvedJob]
    total: int
    url: str | None = None
    identities: list[str] = []
    identity_conflict: bool = False


class JobBatch(Out):
    items: list[Job]
    missing: list[str] = Field(default=[], description="Requested ids that do not exist.")


class DuplicateGroup(Out):
    reference_id: str
    job_ids: list[str]
    size: int
    confidence: Number
    tier: str
    signals: list[str] = []
    reasons: Json = {}
    identical_postings: bool
    merge_blocked: bool
    open_application_ids: list[str] = []
    items: list[Json]


class DuplicatePage(Page):
    items: list[DuplicateGroup]
    min_confidence: Number
    tiers: dict[str, Number]


# Notes and the timeline


class Note(Record):
    job_id: str
    application_id: str | None = None
    scope: str = Field(description="job or application")
    body: str
    author: str | None = None
    pinned: bool
    pinned_at: str | None = None
    created_at: str
    updated_at: str


class NoteList(Out):
    items: list[Note]
    total: int


class TimelineItem(Out):
    id: str
    type: str = Field(description="note or event")
    kind: str = Field(description="note, event or reply")
    scope: Json
    job_id: str | None = None
    application_id: str | None = None
    actor: str | None = None
    batch_id: str | None = None
    created_at: str
    note: Json | None = None
    event: Json | None = None


class Timeline(Page):
    items: list[TimelineItem]
    counts: dict[str, int]
    scope: Json


# Applications


class EmployerRequirement(Out):
    id: str
    kind: str
    text: str
    blocking: bool
    resolved: bool
    note: str = ""


class Reply(Record):
    application_id: str
    job_id: str | None = None
    kind: str
    date: str
    note: str = ""
    created_by: str | None = None
    updated_by: str | None = None
    created_at: str
    updated_at: str


class ApplicationRow(Record):
    """An application as lists show it; ready and missing are computed."""

    job_id: str
    stage: str
    outcome: str | None = None
    priority: int | None = None
    deadline: str | None = None
    applied_at: str | None = None
    concluded_on: str | None = None
    required_documents: list[str]
    ready: bool
    missing: list[str] = Field(description="cv, letter and requirement:<id> still missing.")
    documents_count: int
    open_requirements: int
    blocking_requirements: int
    preparation: list[Json] = []
    last_reply: Json | None = None
    created_at: str
    updated_at: str
    job: Json


class FormQuestion(Out):
    """A question of the employer's application form."""

    id: str
    label: str
    type: str = "text"
    required: bool = False
    options: list[str] = []
    max_length: int | None = None


class Application(ApplicationRow):
    """An application in full, with its job, form, requirements and replies."""

    job: Job | JobSummary
    questions: list[FormQuestion] = []
    answers: Json = {}
    requirements: list[EmployerRequirement] = []
    replies: list[Reply] = []
    pinned_note: Note | None = None
    from_shortlist: bool = False


class ApplicationChange(Application):
    """The application after a change; its job is the compact summary."""


class ApplicationBatch(Out):
    items: list[Application]
    missing: list[str] = Field(default=[], description="Requested ids that do not exist.")


class NoReply(Out):
    days: int
    source: str
    overdue: int | None = None


class ApplicationPage(Page):
    items: list[ApplicationRow]
    stage_counts: dict[str, int]
    no_reply: NoReply | None = None


class Stats(Out):
    period: str
    since: str | None = None
    applied: int
    replied: int
    reply_rate: Number | None = None
    interviews: int
    interview_rate: Number | None = None
    median_days_to_reply: Number | None = None
    funnel: list[Json]
    by_source: list[Json] | None = None


# Documents and files


class WorkspaceFile(Record):
    owner_type: str
    owner_id: str
    name: str
    media_type: str
    size: int
    sha256: str
    source_sha256: str | None = None
    url: str
    created_at: str


class FilePage(Page):
    items: list[WorkspaceFile]


class Document(Record):
    application_id: str
    kind: str
    title: str
    revision_number: int
    previous_id: str | None = None
    complete: bool = Field(description="A CV or letter whose PDF is stored.")
    text: str | None = None
    text_from: str | None = Field(default=None, description="tex or pdf")
    source_sha256: str | None = None
    content: Json | None = None
    highlight_ids: list[str] = []
    career_ids: list[str] = []
    note: str = ""
    files: list[WorkspaceFile] = []
    file_count: int | None = None
    created_at: str


class Uploads(Out):
    pdf: FileGrant | None = None
    source: FileGrant | None = None


class NewDocument(Document):
    uploads: Uploads | None = Field(
        default=None, description="CV or letter: PUT each file's bytes with its grant."
    )


class DocumentPage(Page):
    items: list[Document]


class Comparison(Out):
    document_id: str
    other_id: str | None = None
    added: int
    removed: int
    lines: list[Json]
    text: Json


class DocumentDetail(Document):
    comparison: Comparison | None = Field(
        default=None, description="With compare_to: the line diff against that revision."
    )


# Career


class Profile(Out):
    name: str
    email: str
    phone: str
    location: str
    headline: str
    summary: str
    links: list[Json] = []
    metadata: Json = {}
    version: int


class CareerEntry(Record):
    kind: str
    title: str
    organization: str
    narrative: str | None = None
    narrative_preview: str | None = None
    dates: Json | None = None
    skills: list[str] = []
    metadata: Json | None = None
    position: int
    highlight_count: int | None = None
    highlight_preview: str | None = None
    file_count: int | None = None
    created_at: str
    updated_at: str


class CareerPage(Page):
    items: list[CareerEntry]


class CareerBatch(Out):
    items: list[CareerEntry] = Field(description="Full entries with highlights and files.")
    missing: list[str] = []


class Highlight(Record):
    career_id: str
    career_title: str | None = None
    career_organization: str | None = None
    text: str | None = None
    text_preview: str | None = None
    approved: bool
    always_include: bool
    position: int
    metadata: Json | None = None
    created_at: str
    updated_at: str


class HighlightPage(Page):
    items: list[Highlight]


class Template(Record):
    kind: str
    name: str
    is_default: bool
    tex: str | None = None
    guidance: str | None = None
    rules: Json | None = None
    file_count: int | None = None
    files: list[WorkspaceFile] = []
    created_at: str
    updated_at: str


class TemplatePage(Page):
    items: list[Template]


class ImportPreviewResult(Out):
    entries: list[Json]
    warnings: list[Any] = []
    profile: Json | None = None


class ImportResult(Out):
    items: list[CareerEntry]
    total: int
    profile: Profile | None = None


# Preferences


class PreferenceSection(Out):
    section: str
    title: str
    description: str
    items: list[Json] = Field(description="{text} and, in writing, {text, scope}.")
    version: int
    updated_at: str | None = None
    updated_by: str | None = None


class Settings(Out):
    no_reply_days: int
    spoken_languages: list[str]
    version: int
    updated_at: str | None = None


class Preferences(Out):
    sections: list[PreferenceSection]
    settings: Settings


# Collection


class Collection(Out):
    enabled: bool
    version: int
    sources_failing: int | None = None
    kinds: Json | None = None
    providers: list[Json] | None = None
    fetches: Json | None = None
    results: BatchResult | None = Field(
        default=None, description="collection_update: one result per provider, cancel, retry."
    )
    source_count: int
    enabled_sources: int
    queued_tasks: int
    running_tasks: int
    next_run_at: str | None = None


class ProviderCapability(Out):
    supported: bool
    kind: str
    description: str
    transport_version: str
    credentials_required: bool


class ProviderPolicy(Out):
    enabled: bool
    min_interval_seconds: Number = Field(description="Seconds between two requests.")


class ProviderRuntime(Out):
    """The shared window: when the next request may go and what the last one answered."""

    next_allowed_at: str | None = None
    cooldown_until: str | None = None
    last_request_at: str | None = None
    last_status: int | None = None
    last_error: str | None = None
    requests_hour: int
    requests_day: int
    total_requests: int


class Provider(Record):
    name: str
    capability: ProviderCapability
    policy: ProviderPolicy
    runtime: ProviderRuntime
    updated_at: str | None = None


class ProviderList(Out):
    items: list[Provider]
    total: int


class Task(Out):
    id: str
    kind: str
    state: str
    attempts: int
    run_id: str | None = None
    source_id: str | None = None
    source_name: str | None = None
    job_id: str | None = None
    job_title: str | None = None
    payload: Json = {}
    result: Json | None = None
    error: str | None = None
    next_run_at: str | None = None
    created_at: str
    updated_at: str


class TaskPage(Page):
    items: list[Task]


class RunTask(Out):
    """One fetch of a run, without its inputs and result."""

    id: str
    kind: str
    provider: str | None = None
    state: str
    attempts: int
    error: str | None = None
    next_run_at: str | None = None
    updated_at: str


class CollectionRun(Out):
    id: str
    state: str
    source_id: str | None = None
    source_name: str | None = None
    source_version: int | None = None
    counts: Json = {}
    http_requests: int | None = None
    partial: bool | None = None
    task_ids: list[str] = []
    tasks: list[RunTask] = []
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    next_run_at: str | None = None


class CollectionRunPage(Page):
    items: list[CollectionRun]


class Source(Record):
    name: str
    kind: str
    url: str
    enabled: bool
    automatic_collection: bool
    config: Json
    filters: Json
    schedule: Json
    counts: dict[str, int] = Field(
        default={}, description="Jobs found, shortlisted, applied and replied."
    )
    last_run: Json | None = None
    last_outcome: str | None = None
    last_error: str | None = None
    next_run_at: str | None = None
    created_at: str
    updated_at: str


class SourcePage(Page):
    items: list[Source]


class SourceDetail(Source):
    recent_runs: list[Json] = Field(default=[], description="The latest checks, newest first.")


class SourcePreviewResult(Out):
    items: list[Json]
    total: int
    preview_limit: int
    diagnostics: list[Json] = []


class SourceSchemas(Out):
    items: list[Json]
    schedule_schema: Json
    run_overrides_schema: Json


# Owner


class PasswordChanged(Out):
    updated: bool
    sign_in_required: bool
    api_tokens_preserved: bool


class Token(Out):
    id: str
    name: str
    kind: str
    created_at: str
    token: str | None = Field(default=None, description="The secret, shown only once.")


class TokenRow(Out):
    id: str
    name: str
    kind: str
    created_at: str
    last_used_at: str | None = None


class TokenList(Out):
    items: list[TokenRow]
    total: int


class KeptBackup(Out):
    name: str
    kind: str = Field(description="scheduled or pre_upgrade.")
    size_bytes: int
    created_at: str


class BackupAttempt(Out):
    outcome: str = Field(description="ok, failed or skipped.")
    attempted_at: str
    error: str | None = None


class BackupSchedule(Out):
    enabled: bool
    keep: int
    interval_hours: int
    last_at: str | None = None
    age_hours: Number | None = None
    ok: bool
    last_attempt: BackupAttempt | None = None


class BackupList(Out):
    items: list[KeptBackup]
    total: int
    schedule: BackupSchedule
