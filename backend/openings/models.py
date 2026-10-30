from typing import Any, Literal
from datetime import datetime, timezone, timedelta
import json
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


class ApplicationInput(Input):
    job_id: str
    note: str = Field(default="", max_length=30_000)
    questions: list[Question] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=100)


class ApplicationPatch(Versioned):
    status: Literal["draft", "applied", "interview", "offer", "closed"] | None = None
    outcome: Literal["accepted", "rejected", "not_pursued"] | None = None
    note: str | None = Field(default=None, max_length=30_000)
    questions: list[Question] | None = Field(default=None, max_length=100)
    answers: dict[str, Any] | None = None
    applied_at: str | None = None

    @field_validator("applied_at")
    @classmethod
    def valid_applied_date(cls, value):
        return normalized_date(value)

    @model_validator(mode="after")
    def reject_null_fields(self):
        for key in self.model_fields_set & {"status", "note", "questions", "answers"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null; omit it to keep the existing value.")
        return self


class NotePatch(Versioned):
    body: str = Field(min_length=1, max_length=30_000)


class BulkItem(Versioned):
    id: str


class JobBulk(Input):
    action: Literal["saved", "dismissed", "inbox", "forget", "rescore"]
    items: list[BulkItem] = Field(min_length=1, max_length=200)


def normalized_date(value, *, end=False):
    if not value:
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Use an ISO8601 date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if end and len(value) == 10:
        parsed += timedelta(days=1, microseconds=-1)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


class JobQuery(Input):
    q: str = Field(default="", max_length=1000)
    triage: Literal["inbox", "saved", "dismissed"] | None = None
    company: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=300)
    remote: bool | None = None
    complete: bool | None = None
    job_type: str | None = Field(default=None, max_length=100)
    score_min: float | None = Field(default=None, ge=0, le=100)
    score_max: float | None = Field(default=None, ge=0, le=100)
    score_state: Literal["all", "current", "outdated", "unscored"] = "all"
    created_since: str | None = None
    created_until: str | None = None
    sort: Literal["newest", "oldest", "company", "title", "score", "fit"] = "newest"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("created_since", "created_until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "created_until")

    @model_validator(mode="after")
    def valid_range(self):
        if (
            self.score_min is not None
            and self.score_max is not None
            and self.score_min > self.score_max
        ):
            raise ValueError("The minimum score must not exceed the maximum.")
        if self.created_since and self.created_until and self.created_since > self.created_until:
            raise ValueError("The start date must not follow the end date.")
        return self


class ApplicationQuery(Input):
    q: str = Field(default="", max_length=1000)
    status: Literal["draft", "applied", "interview", "offer", "closed"] | None = None
    outcome: Literal["accepted", "rejected", "not_pursued"] | None = None
    company: str | None = Field(default=None, max_length=300)
    sort: Literal["updated", "newest", "oldest", "company", "stage", "applied"] = "updated"
    limit: int = Field(default=100, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


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
