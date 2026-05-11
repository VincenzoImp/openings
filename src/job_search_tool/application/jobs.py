"""Shared job application service."""

from __future__ import annotations

from job_search_tool.application.models import (
    CleanupPreview,
    CleanupResult,
    JobCommandResult,
    JobListQuery,
    JobListResult,
)
from job_search_tool.database import JobDatabase


class JobApplicationService:
    """Application-level job queries and commands.

    This layer is intentionally independent of FastAPI, MCP, and frontend
    concerns so every surface uses the same behavior.
    """

    def __init__(self, db: JobDatabase) -> None:
        self.db = db

    def list_jobs(self, query: JobListQuery | None = None) -> JobListResult:
        """Return a filtered, sorted, paginated job list."""
        query = query or JobListQuery()
        jobs, total = self.db.query_jobs(
            limit=query.limit,
            offset=query.offset,
            min_score=query.min_score,
            max_score=query.max_score,
            site=query.site,
            company=query.company,
            bookmarked=query.bookmarked,
            applied=query.applied,
            remote=query.remote,
            job_type=query.job_type,
            text=query.text,
            sort=query.sort,
        )
        return JobListResult(
            jobs=jobs,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    def get_job(self, job_id: str):
        """Return one job record, or None when absent."""
        return self.db.get_job_by_id(job_id)

    def set_bookmarked(self, job_id: str, bookmarked: bool) -> JobCommandResult:
        """Set bookmark state idempotently."""
        success = self.db.set_bookmarked(job_id, bookmarked)
        return JobCommandResult(
            success=success,
            affected_count=1 if success else 0,
            job_id=job_id,
            bookmarked=bookmarked if success else None,
            message=None if success else "Job not found",
        )

    def set_applied(self, job_id: str, applied: bool) -> JobCommandResult:
        """Set applied state idempotently."""
        success = self.db.set_applied(job_id, applied)
        return JobCommandResult(
            success=success,
            affected_count=1 if success else 0,
            job_id=job_id,
            applied=applied if success else None,
            message=None if success else "Job not found",
        )

    def blacklist_jobs(self, job_ids: list[str]) -> JobCommandResult:
        """Blacklist active jobs by ID."""
        count = self.db.blacklist_jobs(job_ids)
        return JobCommandResult(success=count > 0, affected_count=count)

    def preview_cleanup(self, config) -> CleanupPreview:
        """Return cleanup counts using the same order as runtime reconciliation."""
        preview = self.db.preview_reconcile_with_config(config)
        return CleanupPreview(
            deleted_below_score=preview.deleted_below_score,
            deleted_stale=preview.deleted_stale,
            purged_blacklist=preview.purged_blacklist,
            protected_bookmarked=preview.protected_bookmarked,
            protected_applied=preview.protected_applied,
        )

    def run_cleanup(self, config) -> CleanupResult:
        """Run cleanup and return the resulting counts."""
        report = self.db.reconcile_with_config(config)
        return CleanupResult(
            deleted_below_score=report.deleted_below_score,
            deleted_stale=report.deleted_stale,
            purged_blacklist=report.purged_blacklist,
            protected_bookmarked=report.protected_bookmarked,
            protected_applied=report.protected_applied,
        )
