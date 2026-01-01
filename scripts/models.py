"""
Data models for Job Search Tool.

Provides type-safe dataclasses for jobs and search results.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


def generate_job_id(title: str, company: str, location: str) -> str:
    """
    Generate unique ID for a job based on title, company, and location.

    Uses full 64-character SHA256 hash to prevent collisions.
    With 16 chars (64 bits), collision probability becomes significant
    at ~2^32 (~4 billion) jobs. Full hash provides 256 bits of security.

    Args:
        title: Job title.
        company: Company name.
        location: Job location.

    Returns:
        Full SHA256 hash of job identifiers.
    """
    identifier = f"{title}|{company}|{location}".lower()
    return hashlib.sha256(identifier.encode()).hexdigest()


@dataclass
class Job:
    """Represents a single job listing."""

    title: str
    company: str
    location: str
    job_url: str | None = None
    description: str | None = None
    date_posted: date | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    interval: str | None = None
    search_query: str | None = None
    search_location: str | None = None
    search_date: date | None = None
    relevance_score: int = 0

    @property
    def job_id(self) -> str:
        """
        Generate unique ID for job based on title, company, and location.

        Returns:
            Full SHA256 hash of job identifiers.
        """
        return generate_job_id(self.title, self.company, self.location)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """
        Create Job from dictionary (e.g., from DataFrame row).

        Args:
            data: Dictionary with job data.

        Returns:
            Job instance.
        """
        # Handle date parsing
        date_posted = None
        if data.get("date_posted"):
            date_val = data["date_posted"]
            if isinstance(date_val, str):
                try:
                    date_posted = datetime.strptime(date_val, "%Y-%m-%d").date()
                except ValueError:
                    pass
            elif isinstance(date_val, (date, datetime)):
                date_posted = (
                    date_val.date() if isinstance(date_val, datetime) else date_val
                )

        search_date = None
        if data.get("search_date"):
            date_val = data["search_date"]
            if isinstance(date_val, str):
                try:
                    search_date = datetime.strptime(date_val, "%Y-%m-%d").date()
                except ValueError:
                    pass
            elif isinstance(date_val, (date, datetime)):
                search_date = (
                    date_val.date() if isinstance(date_val, datetime) else date_val
                )

        return cls(
            title=str(data.get("title", "")),
            company=str(data.get("company", "")),
            location=str(data.get("location", "")),
            job_url=data.get("job_url"),
            description=data.get("description"),
            date_posted=date_posted,
            job_type=data.get("job_type"),
            is_remote=data.get("is_remote"),
            min_amount=data.get("min_amount"),
            max_amount=data.get("max_amount"),
            currency=data.get("currency"),
            interval=data.get("interval"),
            search_query=data.get("search_query"),
            search_location=data.get("search_location"),
            search_date=search_date,
            relevance_score=int(data.get("relevance_score", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert Job to dictionary.

        Returns:
            Dictionary representation of job.
        """
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "job_url": self.job_url,
            "description": self.description,
            "date_posted": (
                self.date_posted.isoformat() if self.date_posted else None
            ),
            "job_type": self.job_type,
            "is_remote": self.is_remote,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "currency": self.currency,
            "interval": self.interval,
            "search_query": self.search_query,
            "search_location": self.search_location,
            "search_date": (
                self.search_date.isoformat() if self.search_date else None
            ),
            "relevance_score": self.relevance_score,
        }


@dataclass
class SearchResult:
    """Represents results from a single search query."""

    query: str
    location: str
    jobs: list[Job] = field(default_factory=list)
    success: bool = True
    error_message: str | None = None
    search_time: datetime = field(default_factory=datetime.now)

    @property
    def job_count(self) -> int:
        """Get number of jobs found."""
        return len(self.jobs)


@dataclass
class SearchSummary:
    """Summary statistics for a complete search run."""

    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_jobs_found: int = 0
    unique_jobs: int = 0
    relevant_jobs: int = 0
    new_jobs: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        """Get search duration in seconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string."""
        seconds = self.duration_seconds
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"

    def finish(self) -> None:
        """Mark search as finished."""
        self.end_time = datetime.now()


@dataclass
class JobDBRecord:
    """Database record for a job with full details."""

    job_id: str
    title: str
    company: str
    location: str
    job_url: str | None = None
    site: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    description: str | None = None
    date_posted: date | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    company_url: str | None = None
    first_seen: date = field(default_factory=date.today)
    last_seen: date = field(default_factory=date.today)
    relevance_score: int = 0
    applied: bool = False

    @classmethod
    def from_job(cls, job: Job, site: str | None = None,
                 job_level: str | None = None,
                 company_url: str | None = None) -> JobDBRecord:
        """
        Create database record from Job.

        Args:
            job: Job instance.
            site: Job board source (indeed, linkedin, etc.).
            job_level: Seniority level (from LinkedIn).
            company_url: Company page URL.

        Returns:
            JobDBRecord instance.
        """
        return cls(
            job_id=job.job_id,
            title=job.title,
            company=job.company,
            location=job.location,
            job_url=job.job_url,
            site=site,
            job_type=job.job_type,
            is_remote=job.is_remote,
            job_level=job_level,
            description=job.description,
            date_posted=job.date_posted,
            min_amount=job.min_amount,
            max_amount=job.max_amount,
            currency=job.currency,
            company_url=company_url,
            relevance_score=job.relevance_score,
        )
