"""Commands, queries and results shared by the dashboard, REST and MCP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from openings.models import Attachment, Event, Job, JobStatus, Note
from openings.scoring import ScoreExplanation

ExportFormat = Literal["csv", "json"]


@dataclass(frozen=True)
class AddJobCommand:
    """A posting handed to the tool by a person or an agent."""

    title: str
    company: str
    location: str
    job_url: str | None = None
    description: str | None = None
    date_posted: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    salary_interval: str | None = None
    company_url: str | None = None
    source: str | None = None
    external_id: str | None = None
    status: JobStatus = JobStatus.SHORTLISTED
    labels: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class CommandResult:
    success: bool
    affected_count: int = 0
    job_ids: list[str] = field(default_factory=list)
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "affected_count": self.affected_count,
            "job_ids": list(self.job_ids),
            "message": self.message,
        }


@dataclass(frozen=True)
class JobPage:
    jobs: list[Job]
    total: int
    limit: int
    offset: int
    labels: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        items = []
        for job in self.jobs:
            summary = job.to_summary()
            summary["labels"] = self.labels.get(job.job_id, [])
            items.append(summary)
        return {"items": items, "total": self.total, "limit": self.limit, "offset": self.offset}


@dataclass(frozen=True)
class JobDetail:
    job: Job
    explain: ScoreExplanation
    labels: list[str]
    notes: list[Note]
    attachments: list[Attachment]
    events: list[Event]

    def to_dict(self) -> dict[str, Any]:
        data = self.job.to_dict()
        data["explain"] = self.explain.to_dict()
        data["labels"] = list(self.labels)
        data["notes"] = [note.to_dict() for note in self.notes]
        data["attachments"] = [attachment.to_dict() for attachment in self.attachments]
        data["events"] = [event.to_dict() for event in self.events]
        return data


@dataclass(frozen=True)
class SemanticResult:
    job_id: str
    title: str | None
    company: str | None
    location: str | None
    similarity: float
    relevance_score: int | None
    source: str | None
    status: str | None
    job_url: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "similarity": round(self.similarity, 4),
            "relevance_score": self.relevance_score,
            "source": self.source,
            "status": self.status,
            "job_url": self.job_url,
        }


@dataclass(frozen=True)
class SourceStatus:
    """A configured source, as shown on the Companies view and by MCP."""

    name: str
    kind: str
    detail: str
    enabled: bool
    active_jobs: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "detail": self.detail,
            "enabled": self.enabled,
            "active_jobs": self.active_jobs,
        }


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    media_type: str
    filename: str
    row_count: int
    total: int
