"""Application-layer contracts for job queries and commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from job_search_tool.models import JobDBRecord

JobSort = Literal["score", "date"]


@dataclass(frozen=True)
class JobListQuery:
    """Query parameters for listing jobs across UI/API/MCP surfaces."""

    limit: int = 20
    offset: int = 0
    min_score: int | None = None
    max_score: int | None = None
    site: str | None = None
    company: str | None = None
    bookmarked: bool | None = None
    applied: bool | None = None
    remote: bool | None = None
    job_type: str | None = None
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
class JobCommandResult:
    """Outcome of a job mutation command."""

    success: bool
    affected_count: int = 0
    job_id: str | None = None
    bookmarked: bool | None = None
    applied: bool | None = None
    message: str | None = None


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
