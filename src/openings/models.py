"""Core data model for Openings.

A *job* is one opening: the canonical posting plus everything the user builds
around it (status, labels, notes, attachments, timeline). The same opening
seen on several boards is one job with several *postings*.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit


class JobStatus(StrEnum):
    """Where a job stands in the user's pipeline.

    Only ``NEW`` rows are subject to retention. Every other status means the
    user acted on the job, so the row is protected. ``BLACKLISTED`` keeps the
    job and its history but hides it everywhere and blocks re-ingestion.
    """

    NEW = "new"
    SHORTLISTED = "shortlisted"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    BLACKLISTED = "blacklisted"


PROTECTED_STATUSES: frozenset[JobStatus] = frozenset(
    status for status in JobStatus if status is not JobStatus.NEW
)
"""Statuses retention never touches."""

ACTIVE_STATUSES: frozenset[JobStatus] = frozenset(
    status for status in JobStatus if status is not JobStatus.BLACKLISTED
)
"""Statuses shown when a query names none."""


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
    POSTING = "posting"
    STATUS = "status"
    LABEL = "label"
    NOTE = "note"
    ATTACHMENT = "attachment"
    UPDATED = "updated"
    MERGED = "merged"


SOURCE_MANUAL = "manual"


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """The current time, timezone-aware, in UTC."""
    return datetime.now(timezone.utc)


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
    """Parse an ISO datetime; naive values are taken as UTC."""
    if value is None or value == "":
        return None
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def generate_job_id(title: str, company: str, location: str) -> str:
    """Identity of an opening: SHA-256 of the normalized title, company, location.

    Used to recognise the same opening across boards and as the job id when a
    posting carries no URL or external id.
    """
    parts = []
    for value in (title, company, location):
        normalized = unicodedata.normalize("NFKC", value or "")
        normalized = " ".join(normalized.split())
        parts.append(normalized.casefold())
    identifier = "|".join(parts)
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


_BOARD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("linkedin", re.compile(r"linkedin\.com/jobs/view/(?:[^/?#]*?-)?(\d+)")),
    ("greenhouse", re.compile(r"greenhouse\.io/[^/?#]+/jobs/(\d+)")),
    ("lever", re.compile(r"jobs\.lever\.co/[^/?#]+/([0-9a-f-]{36})")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/[^/?#]+/([0-9a-f-]{36})")),
    ("smartrecruiters", re.compile(r"smartrecruiters\.com/[^/?#]+/(\d+)")),
    ("google", re.compile(r"careers\.google\.com/jobs/results/(\d+)")),
)
_ID_PARAMS = {"jk", "gh_jid", "id", "jobid", "job_id", "reqid", "requisitionid", "job", "p"}


def canonical_url(url: str | None) -> str | None:
    """A stable key for a posting URL.

    Known boards reduce to ``board:id`` so tracking parameters and slugs do
    not matter. Other URLs keep scheme, host and path plus identifying query
    parameters only.
    """
    if not url:
        return None
    text = str(url).strip()
    if not text:
        return None
    lowered = text.lower()
    for board, pattern in _BOARD_PATTERNS:
        match = pattern.search(lowered)
        if match:
            return f"{board}:{match.group(1)}"
    parts = urlsplit(text)
    if not parts.netloc:
        return None
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+$", "", parts.path) or "/"
    kept = sorted(
        (key.lower(), value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() in _ID_PARAMS
    )
    query = "&".join(f"{key}={value}" for key, value in kept)
    return f"url:{host}{path}" + (f"?{query}" if query else "")


def posting_key(source: str | None, external_id: str | None, url: str | None) -> str | None:
    """What identifies one posting: its canonical URL, else ``source:external_id``."""
    key = canonical_url(url)
    if key:
        return key
    if external_id and source:
        return f"{source.lower()}:{external_id}"
    return None


def job_id_for(key: str | None, identity: str) -> str:
    """The job id of a new job: hash of its posting key, else its identity."""
    if key:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
    return identity


# ---------------------------------------------------------------------------
# Value cleaning
# ---------------------------------------------------------------------------


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


def _clean_int(value: Any, default: int = 0) -> int:
    value = clean_value(value)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

POSTING_FIELDS = (
    "title",
    "company",
    "location",
    "job_url",
    "description",
    "date_posted",
    "job_type",
    "is_remote",
    "job_level",
    "min_amount",
    "max_amount",
    "currency",
    "salary_interval",
    "company_url",
)
"""Posting fields a user may edit through ``update_job``."""


@dataclass(frozen=True)
class Job:
    """One opening plus the tracking state attached to it."""

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
    postings_count: int = 0
    notes_count: int = 0
    attachments_count: int = 0

    @property
    def identity(self) -> str:
        return generate_job_id(self.title, self.company, self.location)

    @property
    def posting_key(self) -> str | None:
        return posting_key(self.source, self.external_id, self.job_url)

    @classmethod
    def from_row(cls, data: Mapping[str, Any]) -> Job:
        """Build a job from a canonical row (DataFrame record, DB row, command).

        ``job_id`` is derived from the posting key, else from the identity,
        when absent, so every producer shares one identity rule.
        """
        title = _clean_str(data.get("title")) or ""
        company = _clean_str(data.get("company")) or ""
        location = _clean_str(data.get("location")) or ""
        source = _clean_str(data.get("source")) or SOURCE_MANUAL
        external_id = _clean_str(data.get("external_id"))
        job_url = _clean_str(data.get("job_url"))
        job_id = _clean_str(data.get("job_id")) or job_id_for(
            posting_key(source, external_id, job_url),
            generate_job_id(title, company, location),
        )
        raw = data.get("raw_json")
        if raw is not None and not isinstance(raw, str):
            raw = json.dumps(raw, default=str)
        status_value = _clean_str(data.get("status")) or JobStatus.NEW.value
        return cls(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            source=source,
            external_id=external_id,
            job_url=job_url,
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
            relevance_score=_clean_int(data.get("relevance_score")),
            status=JobStatus(status_value),
            status_changed_at=parse_datetime(clean_value(data.get("status_changed_at"))),
            postings_count=_clean_int(data.get("postings_count")),
            notes_count=_clean_int(data.get("notes_count")),
            attachments_count=_clean_int(data.get("attachments_count")),
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
        """Compact representation for list views, without description and raw payload."""
        data = self.to_dict()
        data.pop("description", None)
        data.pop("raw_json", None)
        return data


@dataclass(frozen=True)
class Posting:
    """One appearance of a job on one source."""

    id: int
    job_id: str
    key: str
    source: str
    external_id: str | None
    url: str | None
    first_seen: date
    last_seen: date

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "key": self.key,
            "source": self.source,
            "external_id": self.external_id,
            "url": self.url,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


@dataclass(frozen=True)
class Note:
    id: int
    job_id: str
    kind: NoteKind
    title: str | None
    body: str
    created_at: datetime
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "kind": self.kind.value,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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
        end = self.finished_at or utcnow()
        return max(0.0, (end - self.started_at).total_seconds())

    @property
    def duration_formatted(self) -> str:
        seconds = int(self.duration_seconds)
        return f"{seconds // 60}m {seconds % 60}s"

    @property
    def running(self) -> bool:
        return self.finished_at is None

    def finish(self) -> None:
        self.finished_at = utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "running": self.running,
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
