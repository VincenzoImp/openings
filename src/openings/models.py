"""Core data model for Openings.

A *job* is the canonical posting object. Everything the user builds around it
(status, labels, notes, attachments, timeline) hangs off its ``job_id``.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Mapping


class JobStatus(StrEnum):
    """Where a job stands in the user's pipeline.

    Only ``NEW`` rows are subject to retention and reconciliation. Every other
    status means the user has acted on the job, so the row is protected.
    """

    NEW = "new"
    SHORTLISTED = "shortlisted"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


PROTECTED_STATUSES: frozenset[JobStatus] = frozenset(
    status for status in JobStatus if status is not JobStatus.NEW
)


class NoteKind(StrEnum):
    NOTE = "note"
    QA = "qa"


class AttachmentKind(StrEnum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    FORM_ANSWERS = "form_answers"
    OTHER = "other"


class EventKind(StrEnum):
    INGESTED = "ingested"
    STATUS = "status"
    LABEL = "label"
    NOTE = "note"
    ATTACHMENT = "attachment"


SOURCE_MANUAL = "manual"


def generate_job_id(title: str, company: str, location: str) -> str:
    """Stable identity for a posting: SHA-256 of normalized title, company, location.

    The same opening seen on two sources produces the same id, which is how
    cross-source deduplication works.
    """
    parts = []
    for value in (title, company, location):
        normalized = unicodedata.normalize("NFKC", value or "")
        normalized = " ".join(normalized.split())
        parts.append(normalized.casefold())
    identifier = "|".join(parts)
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def parse_date(value: object) -> date | None:
    """Parse ISO dates, ``date`` and ``datetime`` values; ``None`` on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for parser in (date.fromisoformat, lambda v: datetime.fromisoformat(v).date()):
            try:
                return parser(text)
            except ValueError:
                continue
        return None
    return None


def parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def clean_value(value: Any) -> Any:
    """Turn pandas/numpy scalars and NaN into plain Python values or ``None``."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "null"}:
        return None
    return value


def _clean_bool(value: Any) -> bool | None:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _clean_float(value: Any) -> float | None:
    value = clean_value(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_str(value: Any) -> str | None:
    value = clean_value(value)
    if value is None:
        return None
    return str(value)


@dataclass(frozen=True)
class Job:
    """A canonical posting plus the tracking state attached to it."""

    job_id: str
    title: str
    company: str
    location: str
    source: str
    external_id: str | None = None
    job_url: str | None = None
    description: str | None = None
    date_posted: date | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    salary_interval: str | None = None
    company_url: str | None = None
    raw_json: str | None = None
    first_seen: date = field(default_factory=date.today)
    last_seen: date = field(default_factory=date.today)
    relevance_score: int = 0
    status: JobStatus = JobStatus.NEW
    status_changed_at: datetime | None = None

    @classmethod
    def from_row(cls, data: Mapping[str, Any]) -> Job:
        """Build a job from a canonical row (DataFrame record, DB row, command).

        ``job_id`` is computed from title, company and location when absent so
        every producer shares one identity rule.
        """
        title = _clean_str(data.get("title")) or ""
        company = _clean_str(data.get("company")) or ""
        location = _clean_str(data.get("location")) or ""
        job_id = _clean_str(data.get("job_id")) or generate_job_id(title, company, location)
        raw = data.get("raw_json")
        if raw is not None and not isinstance(raw, str):
            raw = json.dumps(raw, default=str)
        status_value = _clean_str(data.get("status")) or JobStatus.NEW.value
        score = clean_value(data.get("relevance_score"))
        return cls(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            source=_clean_str(data.get("source")) or SOURCE_MANUAL,
            external_id=_clean_str(data.get("external_id")),
            job_url=_clean_str(data.get("job_url")),
            description=_clean_str(data.get("description")),
            date_posted=parse_date(clean_value(data.get("date_posted"))),
            job_type=_clean_str(data.get("job_type")),
            is_remote=_clean_bool(data.get("is_remote")),
            job_level=_clean_str(data.get("job_level")),
            min_amount=_clean_float(data.get("min_amount")),
            max_amount=_clean_float(data.get("max_amount")),
            currency=_clean_str(data.get("currency")),
            salary_interval=_clean_str(data.get("salary_interval")),
            company_url=_clean_str(data.get("company_url")),
            raw_json=_clean_str(raw),
            first_seen=parse_date(clean_value(data.get("first_seen"))) or date.today(),
            last_seen=parse_date(clean_value(data.get("last_seen"))) or date.today(),
            relevance_score=int(score) if score is not None else 0,
            status=JobStatus(status_value),
            status_changed_at=parse_datetime(clean_value(data.get("status_changed_at"))),
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe representation."""
        data = asdict(self)
        for key in ("date_posted", "first_seen", "last_seen", "status_changed_at"):
            value = data.get(key)
            data[key] = value.isoformat() if value is not None else None
        data["status"] = self.status.value
        return data

    def to_summary(self) -> dict[str, Any]:
        """Compact representation for list views, without the description."""
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "job_url": self.job_url,
            "job_type": self.job_type,
            "is_remote": self.is_remote,
            "job_level": self.job_level,
            "date_posted": self.date_posted.isoformat() if self.date_posted else None,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "currency": self.currency,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "relevance_score": self.relevance_score,
            "status": self.status.value,
            "status_changed_at": (
                self.status_changed_at.isoformat() if self.status_changed_at else None
            ),
        }


@dataclass(frozen=True)
class Note:
    id: int
    job_id: str
    kind: NoteKind
    title: str | None
    body: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "kind": self.kind.value,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class Attachment:
    id: int
    job_id: str
    kind: AttachmentKind
    filename: str
    stored_name: str
    sha256: str
    size_bytes: int
    note: str | None
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "kind": self.kind.value,
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class Event:
    id: int
    job_id: str
    kind: EventKind
    summary: str
    data: dict[str, Any] | None
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class BlacklistEntry:
    job_id: str
    title: str
    company: str
    location: str
    blacklisted_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "blacklisted_at": self.blacklisted_at.isoformat(),
        }


@dataclass
class SourceRunStats:
    """What one source did during a collection run."""

    name: str
    tasks: int = 0
    succeeded: int = 0
    failed: int = 0
    rows: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunSummary:
    """One collection run, as recorded in the ``runs`` table."""

    started_at: datetime
    finished_at: datetime | None = None
    total_found: int = 0
    unique_found: int = 0
    saved: int = 0
    new_jobs: int = 0
    notified: int = 0
    success: bool = True
    sources: list[SourceRunStats] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    id: int | None = None

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def duration_formatted(self) -> str:
        seconds = int(self.duration_seconds)
        return f"{seconds // 60}m {seconds % 60}s"

    def finish(self) -> None:
        self.finished_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "total_found": self.total_found,
            "unique_found": self.unique_found,
            "saved": self.saved,
            "new_jobs": self.new_jobs,
            "notified": self.notified,
            "success": self.success,
            "sources": [source.to_dict() for source in self.sources],
            "errors": list(self.errors),
        }
