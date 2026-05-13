"""Application-layer contracts for job queries and commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from job_search_tool.models import BlacklistedJobRecord, JobDBRecord

JobSort = Literal["score", "date", "company", "title", "salary"]
JobExportFormat = Literal["csv", "json"]


@dataclass(frozen=True)
class JobListQuery:
    """Query parameters for listing jobs across UI/API/MCP surfaces."""

    limit: int = 20
    offset: int = 0
    min_score: int | None = None
    max_score: int | None = None
    site: str | None = None
    sites: list[str] | None = None
    company: str | None = None
    location: str | None = None
    locations: list[str] | None = None
    bookmarked: bool | None = None
    applied: bool | None = None
    remote: bool | None = None
    job_type: str | None = None
    job_types: list[str] | None = None
    min_salary: float | None = None
    max_salary: float | None = None
    date_posted_from: date | datetime | str | None = None
    date_posted_to: date | datetime | str | None = None
    first_seen_from: date | datetime | str | None = None
    first_seen_to: date | datetime | str | None = None
    last_seen_from: date | datetime | str | None = None
    last_seen_to: date | datetime | str | None = None
    text: str | None = None
    sort: JobSort = "score"


@dataclass(frozen=True)
class JobListResult:
    """A page of jobs plus the unpaginated result count."""

    jobs: list[JobDBRecord]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class BlacklistListQuery:
    """Query parameters for listing blacklist entries."""

    limit: int = 100
    offset: int = 0
    text: str | None = None
    company: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class BlacklistListResult:
    """A page of blacklist entries plus the unpaginated result count."""

    items: list[BlacklistedJobRecord]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class JobCommandResult:
    """Outcome of a job mutation command."""

    success: bool
    affected_count: int = 0
    job_ids: list[str] = field(default_factory=list)
    bookmarked: bool | None = None
    applied: bool | None = None
    message: str | None = None


@dataclass(frozen=True)
class JobExportResult:
    """Serialized job export content and response metadata."""

    content: bytes
    media_type: str
    filename: str
    row_count: int


@dataclass(frozen=True)
class CleanupPreview:
    """Counts for cleanup actions before or after execution."""

    deleted_below_score: int = 0
    deleted_stale: int = 0
    purged_blacklist: int = 0
    protected_bookmarked: int = 0
    protected_applied: int = 0

    @property
    def total_deleted(self) -> int:
        return self.deleted_below_score + self.deleted_stale + self.purged_blacklist


CleanupResult = CleanupPreview
