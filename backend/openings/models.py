import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("metadata", "raw", "answers", check_fields=False)
    @classmethod
    def finite_json(cls, value):
        if value is not None:
            try:
                encoded = json.dumps(value, allow_nan=False)
            except (ValueError, TypeError) as error:
                raise ValueError("Use finite JSON values.") from error
            if len(encoded) > 2_000_000:
                raise ValueError("Structured data exceeds the 2 MB limit.")
        return value


class Versioned(Input):
    expected_version: int = Field(ge=1)


class JobInput(Input):
    url: str = Field(default="", max_length=4000)
    title: str = Field(default="", max_length=400)
    company: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=500)
    posting: str = Field(default="", max_length=200_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_key: str | None = Field(default=None, max_length=1000)
    source_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the record the first request created.",
    )

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username:
                raise ValueError("Use an HTTP or HTTPS job URL without credentials.")
        return value


class JobPatch(Versioned):
    title: str | None = Field(default=None, min_length=1, max_length=400)
    company: str | None = Field(default=None, min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=4000)
    posting: str | None = Field(default=None, max_length=200_000)
    metadata: dict[str, Any] | None = None

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return JobInput.valid_url(value) if value else value


def dismiss_reason():
    return Field(
        default=None,
        max_length=500,
        description="With dismissed: why, in a short sentence, shown in the Dismissed list (for example 'Junior role; I look for senior roles').",
    )


Triage = Literal["new", "shortlisted", "dismissed"]


class TriageInput(Versioned):
    triage: Triage = Field(
        description="new (to review), shortlisted (starts an application in stage Shortlisted when the job has no open one) or dismissed. Moving a shortlisted job back to new or dismissed removes the application its shortlist started while it is still empty; otherwise 409 application_has_work."
    )
    reason: str | None = dismiss_reason()


class DistinctInput(Input):
    other_id: str = Field(
        min_length=1,
        max_length=100,
        description="The job flagged as its likely duplicate that is in fact a different vacancy.",
    )


class MergeInput(Versioned):
    target_id: str
    target_version: int


class NoteInput(Input):
    body: str = Field(min_length=1, max_length=30_000)
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the record the first request created.",
    )
    application_id: str | None = Field(
        default=None,
        description="Write the note on this application of the job; omit for a note on the job itself.",
    )
    pinned: bool = Field(
        default=False,
        description="Pin the note: it is listed first in its timeline. A job and an application each have at most one pinned note; pinning another unpins it.",
    )


class NotePin(Versioned):
    pinned: bool = Field(
        default=True,
        description="True pins the note (unpinning the note pinned in the same scope); false unpins it.",
    )


class Question(Input):
    id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=2000)
    type: Literal["text", "choice", "boolean", "number"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)
    max_length: int | None = Field(default=None, ge=1, le=50_000)


RequirementKind = Literal[
    "authorship",
    "attachment",
    "reference",
    "format",
    "language",
    "eligibility",
    "deadline",
    "other",
]
Priority = Annotated[int, Field(ge=1, le=5, description="1 is the highest priority, 5 the lowest.")]


class Requirement(Input):
    """One employer requirement found in a posting or application form."""

    id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Stable identifier; assigned when omitted.",
    )
    kind: RequirementKind = "other"
    text: str = Field(min_length=1, max_length=2000, description="The requirement as stated.")
    blocking: bool = Field(
        default=False,
        description="True when documents must not be prepared or submitted until it is resolved.",
    )
    resolved: bool = False
    note: str = Field(
        default="", max_length=2000, description="Resolution, owner decision or open question."
    )


def valid_deadline(value):
    if value is None:
        return value
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Use an ISO date (YYYY-MM-DD).") from error
    if len(value) != 10 or parsed.isoformat() != value:
        raise ValueError("Use an ISO date (YYYY-MM-DD).")
    return value


def latest_day():
    """The latest calendar day anywhere on Earth now (UTC+14): later days are in the future."""
    return (datetime.now(UTC) + timedelta(hours=14)).date().isoformat()


def past_day(value):
    """An ISO date that is not in the future, as an employer response or a closing has."""
    value = valid_deadline(value)
    if value is not None and value > latest_day():
        raise ValueError("Use a day that is not in the future.")
    if value is not None and value < "2000-01-01":
        raise ValueError("Use a day from 2000 on.")
    return value


def normalized_date(value, *, end=False):
    if not value:
        return value
    try:
        # The replacement also accepts some malformed inputs; keep validation unchanged.
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # noqa: FURB162
    except ValueError as error:
        raise ValueError("Use an ISO8601 date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if end and len(value) == 10:
        parsed += timedelta(days=1, microseconds=-1)
    return parsed.astimezone(UTC).isoformat(timespec="microseconds")


def not_blank(value):
    value = value.strip()
    if not value:
        raise ValueError("Write some text; a blank value is left out.")
    return value


# Shared field types: validation runs once per type instead of once per model.
Day = Annotated[str, AfterValidator(valid_deadline)]  # YYYY-MM-DD
PastDay = Annotated[str, AfterValidator(past_day)]  # YYYY-MM-DD, not in the future
Since = Annotated[str, AfterValidator(normalized_date)]  # a date or timestamp, from its start
Until = Annotated[str, AfterValidator(lambda value: normalized_date(value, end=True))]
NonBlank = Annotated[str, AfterValidator(not_blank)]  # stripped, not empty


class SubjectRef(Input):
    """A filter by changed record: subject_id needs its subject_type."""

    subject_type: str | None = Field(default=None, max_length=50)
    subject_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def whole_reference(self):
        if self.subject_id is not None and self.subject_type is None:
            raise ValueError("Provide subject_type when filtering by subject_id.")
        return self


# How an application ended: hired (accepted), turned down by the employer (rejected),
# stopped by the owner (not_pursued) or no answer within the no-reply period (no_response).
Outcome = Literal["accepted", "rejected", "not_pursued", "no_response"]
OUTCOMES = ("accepted", "rejected", "not_pursued", "no_response")


DocumentKindRequired = Literal["cv", "letter"]
Stage = Literal["shortlisted", "applied", "interview", "offer", "closed"]
ReplyKind = Literal["interview", "rejection", "offer", "other"]


def required_documents_field(default):
    return Field(
        default=default,
        max_length=2,
        description="The documents Ready needs: a subset of cv and letter (both by default). Form answers never affect Ready.",
    )


class ApplicationInput(Input):
    job_id: str
    required_documents: list[DocumentKindRequired] = required_documents_field(["cv", "letter"])
    questions: list[Question] = Field(default_factory=list, max_length=100)
    priority: Priority | None = None
    deadline: Day | None = Field(default=None, description="Closing date as YYYY-MM-DD.")
    requirements: list[Requirement] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class ReplyChange(Input):
    """An employer reply to record, correct or remove."""

    id: str | None = Field(
        default=None,
        max_length=100,
        description="The reply to correct or remove; omit to record a new reply.",
    )
    kind: ReplyKind | None = Field(
        default=None,
        description="interview (an invitation), rejection, offer or other (any other answer). Required for a new reply.",
    )
    date: PastDay | None = Field(
        default=None,
        description="The day it arrived (YYYY-MM-DD, not in the future); today (UTC) for a new reply when omitted.",
    )
    note: str | None = Field(default=None, max_length=2000)
    remove: bool = Field(default=False, description="With id: delete a reply recorded by mistake.")

    @model_validator(mode="after")
    def valid_change(self):
        if self.remove and (self.id is None or self.model_fields_set & {"kind", "date", "note"}):
            raise ValueError("remove takes the id of the reply only.")
        if self.id is None and self.kind is None:
            raise ValueError("A new reply needs its kind.")
        return self


class ApplicationPatch(Versioned):
    status: Stage | None = Field(
        default=None,
        description="applied is Mark applied (applied_at defaults to now); shortlisted again undoes it while the application has no reply, clearing applied_at. Record an employer reply with reply, which sets the stage itself.",
    )
    outcome: Outcome | None = Field(
        default=None,
        description="Required to close: accepted, rejected (by the employer), not_pursued (stopped by the owner) or no_response (no answer within the no-reply period; only for a sent application).",
    )
    questions: list[Question] | None = Field(default=None, max_length=100)
    answers: dict[str, Any] | None = None
    applied_at: str | None = None
    required_documents: list[DocumentKindRequired] | None = required_documents_field(None)
    priority: Priority | None = None
    deadline: Day | None = Field(
        default=None, description="Closing date as YYYY-MM-DD; null clears it."
    )
    requirements: list[Requirement] | None = Field(
        default=None,
        max_length=100,
        description="Replaces the whole requirement list; include existing ids to keep them.",
    )
    concluded_on: PastDay | None = Field(
        default=None,
        description="With outcome no_response: the day it was concluded that no reply will come (YYYY-MM-DD, not in the future); today (UTC) when omitted.",
    )
    reply: ReplyChange | None = Field(
        default=None,
        description="Record an employer reply (kind, date, note) and move the stage with it in the same change: interview moves an Applied application to Interview, offer moves it to Offer, rejection closes it as rejected; other never moves the stage. A Closed application without a reply (no_response) is reopened the same way. With id: correct a reply's kind, date or note, or remove it (remove=true); a correction never moves the stage.",
    )

    @field_validator("applied_at")
    @classmethod
    def valid_applied_date(cls, value):
        return normalized_date(value)

    @model_validator(mode="after")
    def reject_null_fields(self):
        for key in self.model_fields_set & {
            "status",
            "questions",
            "answers",
            "requirements",
            "required_documents",
            "reply",
        }:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null; omit it to keep the existing value.")
        return self


class NotePatch(Versioned):
    body: str = Field(min_length=1, max_length=30_000)


TimelineKind = Literal["note", "event", "reply"]
TimelineWho = Literal["owner", "agent", "system", "unknown"]


class TimelineQuery(Input):
    kinds: list[TimelineKind] | None = Field(
        default=None,
        max_length=3,
        description="Only these kinds of entry: note, event (a recorded change) and reply (an employer reply recorded, corrected or removed). Every kind when omitted.",
    )
    who: list[TimelineWho] | None = Field(
        default=None,
        max_length=4,
        description="Only entries by: owner (the dashboard or an owner token), agent (an agent token), system, unknown (recorded before 0.17, including application notes last written then).",
    )
    scope: Literal["job", "application"] | None = Field(
        default=None,
        description="Only the entries of the job itself (job) or of its applications (application). An application's timeline includes its job's entries unless scope=application.",
    )
    since: Since | None = Field(default=None, description="Only entries at or after this time.")
    until: Until | None = Field(
        default=None, description="Only entries at or before this time (a date includes its day)."
    )
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class BulkItem(Versioned):
    id: str


class JobBulk(Input):
    action: Literal["shortlisted", "dismissed", "new", "forget"]
    items: list[BulkItem] = Field(min_length=1, max_length=200)
    reason: str | None = dismiss_reason()

    @model_validator(mode="after")
    def reason_with_dismissal(self):
        if self.reason and self.action != "dismissed":
            raise ValueError("A reason goes with the dismissed action only.")
        return self


def unique_items(items, label):
    if len({item.id for item in items}) != len(items):
        raise ValueError(f"Select each {label} once.")
    return items


class ApplicationBulk(Input):
    action: Literal["close", "reopen", "delete"]
    items: list[BulkItem] = Field(min_length=1, max_length=200)
    outcome: Outcome | None = None
    status: Literal["shortlisted", "applied", "interview", "offer"] | None = None

    @model_validator(mode="after")
    def valid_options(self):
        if (self.action == "close") != (self.outcome is not None):
            raise ValueError("An outcome is required only for close.")
        if (self.action == "reopen") != (self.status is not None):
            raise ValueError("A non-Closed stage is required only for reopen.")
        unique_items(self.items, "application")
        return self


class JobResolve(Input):
    url: str = Field(default="", max_length=4000)
    source_key: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return JobInput.valid_url(value) if value else value

    @model_validator(mode="after")
    def some_identity(self):
        if not self.url and not self.source_key:
            raise ValueError("Provide a job URL or source_key.")
        return self


class DuplicateQuery(Input):
    triage: Triage | None = None
    job_id: str | None = Field(default=None, max_length=100)
    match_location: bool = False
    min_confidence: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Lowest group confidence to return: 0.85 high tier only, 0.5 medium and high, 0 every candidate.",
    )
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class JobQuery(Input):
    q: str = Field(default="", max_length=1000)
    triage: Literal["new", "shortlisted", "dismissed", "active"] | None = Field(
        default=None,
        description="new (to review), shortlisted (each has an application), dismissed, or active (not dismissed).",
    )
    company: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=300)
    remote: bool | None = None
    complete: bool | None = None
    job_type: str | None = Field(default=None, max_length=100)
    created_since: Since | None = None
    created_until: Until | None = None
    signal: (
        Literal["likely_duplicate", "no_longer_listed", "language_required", "pending"] | None
    ) = Field(
        default=None,
        description="Only jobs with this ingest signal: likely_duplicate (flagged as a copy of an earlier job), no_longer_listed (the board stopped listing it), language_required (the posting states a required language) or pending (signals not computed yet).",
    )
    posting_language: str | None = Field(
        default=None,
        max_length=40,
        description="Only postings written in this language (ISO 639-1 code such as de, or a name such as German).",
    )
    posting_language_not: str | None = Field(
        default=None,
        max_length=40,
        description="Only postings whose detected language is another one; postings of unknown language are left out.",
    )
    requires: str | None = Field(
        default=None,
        max_length=40,
        description="Only postings that state this language as required (alone or as one of alternatives).",
    )
    dismissed_by: str | None = Field(
        default=None,
        max_length=200,
        pattern=r"^(owner|agent|system|agent:.+)$",
        description="Only dismissed jobs, by who dismissed them: agent (any agent token), agent:<token name>, owner (dashboard or owner token) or system (job sources, or before 0.21 without a record).",
    )
    batch_id: str | None = Field(
        default=None,
        max_length=100,
        description="Only jobs changed by one REST request or MCP tool call (its batch_id, as events_list and histories show it). Restore an agent's dismissals with jobs_bulk action inbox.",
    )
    since: Since | None = Field(
        default=None, description="Only jobs dismissed at or after this time."
    )
    hide_unspoken_required: bool | None = Field(
        default=None,
        description="true: leave out jobs that require a language outside the owner's spoken_languages (settings); nothing is dismissed. With true or false the response's unspoken_required gives how many jobs of these filters require such a language. No effect while spoken_languages is empty.",
    )
    sort: Literal["newest", "oldest", "company", "title", "dismissed"] = Field(
        default="newest", description="dismissed: most recently dismissed first."
    )
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    include_facets: bool = Field(
        default=False,
        description="Also return up to 200 distinct companies/locations/sources/job types matching the filters.",
    )
    include_counts: bool = Field(
        default=False,
        description="Also return counts: jobs by triage (new, shortlisted, dismissed, all) and dismissed jobs by who dismissed them, for the same search, company, location, source, date and signal filters.",
    )

    @model_validator(mode="after")
    def valid_range(self):
        if self.created_since and self.created_until and self.created_since > self.created_until:
            raise ValueError("The start date must not follow the end date.")
        return self


class ApplicationQuery(Input):
    q: str = Field(default="", max_length=1000)
    job_id: str | None = None
    stage: Literal["shortlisted", "ready", "applied", "interview", "offer", "closed"] | None = (
        Field(
            default=None,
            description="Only applications in this stage; ready is the Shortlisted ones that are Ready (every required document complete, no open blocking requirement).",
        )
    )
    needs: Literal["documents", "reply_overdue"] | None = Field(
        default=None,
        description="documents: Shortlisted applications missing a required document; reply_overdue: Applied applications without a reply for longer than the no-reply period, to close as no_response by hand.",
    )
    outcome: Outcome | None = None
    company: str | None = Field(default=None, max_length=300)
    applied_since: Since | None = Field(
        default=None, description="Only applications recorded as applied at or after this time."
    )
    applied_until: Until | None = Field(
        default=None,
        description="Only applications recorded as applied at or before this time; with stage=applied, the ones still waiting for a reply.",
    )
    sort: Literal[
        "updated",
        "newest",
        "oldest",
        "company",
        "stage",
        "applied",
        "deadline",
        "priority",
    ] = "updated"
    limit: int = Field(default=100, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
