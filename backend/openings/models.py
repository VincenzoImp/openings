import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    availability: Literal["open", "closed", "unknown"] | None = None

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return JobInput.valid_url(value) if value else value


class TriageInput(Versioned):
    triage: Literal["inbox", "saved", "dismissed"]


class MergeInput(Versioned):
    target_id: str
    target_version: int


class NoteInput(Input):
    body: str = Field(min_length=1, max_length=30_000)
    application_id: str | None = None


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


class ApplicationInput(Input):
    job_id: str
    note: str = Field(default="", max_length=30_000)
    questions: list[Question] = Field(default_factory=list, max_length=100)
    priority: Priority | None = None
    deadline: str | None = Field(default=None, description="Closing date as YYYY-MM-DD.")
    requirements: list[Requirement] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=100)

    @field_validator("deadline")
    @classmethod
    def valid_deadline(cls, value):
        return valid_deadline(value)


class ApplicationPatch(Versioned):
    status: Literal["draft", "applied", "interview", "offer", "closed"] | None = None
    outcome: Literal["accepted", "rejected", "not_pursued"] | None = None
    note: str | None = Field(default=None, max_length=30_000)
    questions: list[Question] | None = Field(default=None, max_length=100)
    answers: dict[str, Any] | None = None
    applied_at: str | None = None
    priority: Priority | None = None
    deadline: str | None = Field(
        default=None, description="Closing date as YYYY-MM-DD; null clears it."
    )
    requirements: list[Requirement] | None = Field(
        default=None,
        max_length=100,
        description="Replaces the whole requirement list; include existing ids to keep them.",
    )

    @field_validator("applied_at")
    @classmethod
    def valid_applied_date(cls, value):
        return normalized_date(value)

    @field_validator("deadline")
    @classmethod
    def valid_deadline(cls, value):
        return valid_deadline(value)

    @model_validator(mode="after")
    def reject_null_fields(self):
        for key in self.model_fields_set & {
            "status",
            "note",
            "questions",
            "answers",
            "requirements",
        }:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null; omit it to keep the existing value.")
        return self


class ApplicationReady(Versioned):
    ready: bool = Field(
        default=True,
        description="True marks the application ready to apply; false clears the mark.",
    )


class NotePatch(Versioned):
    body: str = Field(min_length=1, max_length=30_000)


class BulkItem(Versioned):
    id: str


class JobBulk(Input):
    action: Literal["saved", "dismissed", "inbox", "forget"]
    items: list[BulkItem] = Field(min_length=1, max_length=200)


def unique_items(items, label):
    if len({item.id for item in items}) != len(items):
        raise ValueError(f"Select each {label} once.")
    return items


class ApplicationBulk(Input):
    action: Literal["close", "reopen", "delete", "mark_ready", "unmark_ready"]
    items: list[BulkItem] = Field(min_length=1, max_length=200)
    outcome: Literal["accepted", "rejected", "not_pursued"] | None = None
    status: Literal["draft", "applied", "interview", "offer"] | None = None

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
    queue: Literal["inbox", "shortlist", "applications", "dismissed"] | None = None
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


class JobQuery(Input):
    q: str = Field(default="", max_length=1000)
    triage: Literal["inbox", "saved", "dismissed", "active"] | None = None
    queue: Literal["inbox", "shortlist", "applications", "dismissed"] | None = None
    company: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=300)
    remote: bool | None = None
    complete: bool | None = None
    job_type: str | None = Field(default=None, max_length=100)
    created_since: str | None = None
    created_until: str | None = None
    sort: Literal["newest", "oldest", "company", "title"] = "newest"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    include_facets: bool = Field(
        default=False,
        description="Also return up to 200 distinct companies/locations/sources/job types matching the filters.",
    )

    @field_validator("created_since", "created_until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "created_until")

    @model_validator(mode="after")
    def valid_range(self):
        if self.created_since and self.created_until and self.created_since > self.created_until:
            raise ValueError("The start date must not follow the end date.")
        return self


class ApplicationQuery(Input):
    q: str = Field(default="", max_length=1000)
    job_id: str | None = None
    status: Literal["draft", "applied", "interview", "offer", "closed"] | None = None
    outcome: Literal["accepted", "rejected", "not_pursued"] | None = None
    company: str | None = Field(default=None, max_length=300)
    readiness: (
        Literal["blocked", "none", "missing_pdf", "unreviewed", "reviewed", "ready"] | None
    ) = Field(
        default=None,
        description="ready is the stored step (marked ready and still passing every check); reviewed passes every check but is not marked; the other values are derived from current revision leaves and unresolved blocking requirements.",
    )
    ready_since: str | None = Field(
        default=None, description="Only applications marked ready at or after this time."
    )
    ready_until: str | None = Field(
        default=None, description="Only applications marked ready at or before this time."
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
        "ready",
    ] = "updated"
    limit: int = Field(default=100, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("ready_since", "ready_until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "ready_until")


class PeriodQuery(Input):
    since: str | None = None
    until: str | None = None

    @field_validator("since", "until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "until")

    @model_validator(mode="after")
    def valid_range(self):
        if self.since and self.until and self.since > self.until:
            raise ValueError("The start date must not follow the end date.")
        return self
