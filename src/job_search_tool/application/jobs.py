"""Shared job application service."""

from __future__ import annotations

from dataclasses import asdict
import csv
import json
from io import StringIO
import logging
from typing import Any, Callable, Protocol, Sequence, cast

from job_search_tool.application.models import (
    BlacklistListQuery,
    BlacklistListResult,
    CleanupPreview,
    CleanupResult,
    JobCommandResult,
    JobExportFormat,
    JobExportResult,
    JobListQuery,
    JobListResult,
    SemanticJobResult,
)
from job_search_tool.database import JobDatabase
from job_search_tool.models import JobDBRecord

logger = logging.getLogger("job_search.application.jobs")


class VectorSearchResult(Protocol):
    job_id: str
    similarity: float
    metadata: dict[str, Any]


class VectorStore(Protocol):
    """Read-only surface the web process is allowed to use.

    Only the scheduler process may mutate Chroma's on-disk index — see
    ``vector_store.ReadOnlyVectorStore`` for why concurrent multi-process
    writes corrupt it. This service must never call a mutating method here.
    """

    def search(
        self,
        query: str,
        n_results: int = 20,
        min_score: int | None = None,
        site: str | None = None,
    ) -> Sequence[VectorSearchResult]: ...


class VectorStoreUnavailableError(RuntimeError):
    """Raised when semantic search is requested without a vector store."""


class JobApplicationService:
    """Application-level job queries and commands.

    This layer is intentionally independent of FastAPI, MCP, and frontend
    concerns so every surface uses the same behavior.
    """

    def __init__(
        self,
        db: JobDatabase,
        vector_store_factory: Callable[[], object | None] | None = None,
    ) -> None:
        self.db = db
        self._vector_store_factory = vector_store_factory

    @staticmethod
    def _normalize_job_ids(job_ids: str | list[str]) -> list[str]:
        """Return deduplicated job IDs while preserving the caller's order."""
        if isinstance(job_ids, str):
            values = [job_ids]
        else:
            values = job_ids
        return list(dict.fromkeys(job_id for job_id in values if job_id))

    @staticmethod
    def _command_result(
        affected_ids: list[str],
        *,
        total_requested: int | None = None,
        bookmarked: bool | None = None,
        applied: bool | None = None,
    ) -> JobCommandResult:
        requested = len(affected_ids) if total_requested is None else total_requested
        affected_count = len(affected_ids)
        success = affected_count > 0 and affected_count == requested
        message = None
        if requested == 0:
            message = "No job IDs provided"
        elif affected_count != requested:
            message = f"Updated {affected_count} of {requested} requested job(s)"
        return JobCommandResult(
            success=success,
            affected_count=affected_count,
            job_ids=affected_ids,
            bookmarked=bookmarked,
            applied=applied,
            message=message,
        )

    @staticmethod
    def _record_to_export_row(record: JobDBRecord) -> dict[str, object]:
        row = asdict(record)
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()
        return row

    def _get_vector_store(self) -> VectorStore | None:
        if self._vector_store_factory is None:
            return None
        try:
            vector_store = self._vector_store_factory()
            return cast(VectorStore | None, vector_store)
        except Exception as exc:
            logger.warning("Vector store unavailable: %s", exc)
            return None

    def list_jobs(self, query: JobListQuery | None = None) -> JobListResult:
        """Return a filtered, sorted, paginated job list."""
        query = query or JobListQuery()
        jobs, total = self.db.query_jobs(
            limit=query.limit,
            offset=query.offset,
            min_score=query.min_score,
            max_score=query.max_score,
            site=query.site,
            sites=query.sites,
            company=query.company,
            location=query.location,
            locations=query.locations,
            bookmarked=query.bookmarked,
            applied=query.applied,
            remote=query.remote,
            job_type=query.job_type,
            job_types=query.job_types,
            min_salary=query.min_salary,
            max_salary=query.max_salary,
            date_posted_from=query.date_posted_from,
            date_posted_to=query.date_posted_to,
            first_seen_from=query.first_seen_from,
            first_seen_to=query.first_seen_to,
            last_seen_from=query.last_seen_from,
            last_seen_to=query.last_seen_to,
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

    def list_blacklisted_jobs(
        self,
        query: BlacklistListQuery | None = None,
    ) -> BlacklistListResult:
        """Return a filtered, sorted, paginated blacklist list."""
        query = query or BlacklistListQuery()
        items, total = self.db.list_blacklisted_jobs(
            limit=query.limit,
            offset=query.offset,
            text=query.text,
            company=query.company,
            location=query.location,
        )
        return BlacklistListResult(
            items=items,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    def get_statistics(self) -> dict[str, int | float]:
        """Return database statistics."""
        return self.db.get_statistics()

    def get_score_distribution(self, bin_size: int = 5) -> list[tuple[int, int]]:
        """Return score distribution bins."""
        return self.db.get_score_distribution(bin_size)

    def get_facets(self) -> dict[str, list[dict[str, object]]]:
        """Return dashboard filter facets."""
        return self.db.get_facets()

    def search_similar(
        self,
        query: str,
        n_results: int = 20,
        min_score: int | None = None,
        site: str | None = None,
    ) -> list[SemanticJobResult]:
        """Return semantic results that still exist in the active job database.

        Stale hits (jobs Chroma still has embedded but that are no longer in
        the SQL DB) are filtered out of the results here, but not deleted
        from Chroma — only the scheduler process may write to Chroma; it
        prunes the same stale entries on its own periodic sync.
        """
        vector_store = self._get_vector_store()
        if vector_store is None:
            raise VectorStoreUnavailableError("Vector store not available")

        vector_results = vector_store.search(
            query=query,
            n_results=n_results,
            min_score=min_score,
            site=site,
        )
        records_by_id = {
            record.job_id: record
            for record in self.db.get_jobs_by_ids(
                [result.job_id for result in vector_results]
            )
        }
        semantic_results: list[SemanticJobResult] = []

        for result in vector_results:
            record = records_by_id.get(result.job_id)
            if record is None:
                continue
            metadata = result.metadata or {}
            semantic_results.append(
                SemanticJobResult(
                    job_id=result.job_id,
                    title=metadata.get("title") or record.title,
                    company=metadata.get("company") or record.company,
                    location=metadata.get("location") or record.location,
                    similarity=result.similarity,
                    relevance_score=metadata.get("relevance_score")
                    or record.relevance_score,
                    site=metadata.get("site") or record.site,
                    job_url=metadata.get("job_url") or record.job_url,
                )
            )

        return semantic_results

    def set_bookmarked(
        self,
        job_ids: str | list[str],
        bookmarked: bool,
    ) -> JobCommandResult:
        """Set bookmark state idempotently for one or more jobs."""
        requested_ids = self._normalize_job_ids(job_ids)
        affected_ids = [
            job_id
            for job_id in requested_ids
            if self.db.set_bookmarked(job_id, bookmarked)
        ]
        return self._command_result(
            affected_ids,
            total_requested=len(requested_ids),
            bookmarked=bookmarked if affected_ids else None,
        )

    def set_applied(
        self,
        job_ids: str | list[str],
        applied: bool,
    ) -> JobCommandResult:
        """Set applied state idempotently for one or more jobs."""
        requested_ids = self._normalize_job_ids(job_ids)
        affected_ids = [
            job_id for job_id in requested_ids if self.db.set_applied(job_id, applied)
        ]
        return self._command_result(
            affected_ids,
            total_requested=len(requested_ids),
            applied=applied if affected_ids else None,
        )

    def blacklist_jobs(self, job_ids: list[str]) -> JobCommandResult:
        """Blacklist active jobs by ID."""
        requested_ids = self._normalize_job_ids(job_ids)
        affected_ids = [
            job_id for job_id in requested_ids if self.db.get_job_by_id(job_id)
        ]
        self.db.blacklist_jobs(affected_ids)
        return self._command_result(
            affected_ids,
            total_requested=len(requested_ids),
        )

    def unblacklist_jobs(self, job_ids: list[str]) -> JobCommandResult:
        """Remove job IDs from the blacklist without restoring active rows."""
        requested_ids = self._normalize_job_ids(job_ids)
        blacklisted_ids = self.db.get_blacklisted_job_ids(requested_ids)
        affected_ids = [job_id for job_id in requested_ids if job_id in blacklisted_ids]
        self.db.unblacklist_jobs(affected_ids)
        return self._command_result(
            affected_ids,
            total_requested=len(requested_ids),
        )

    def delete_jobs(self, job_ids: list[str]) -> JobCommandResult:
        """Permanently delete active jobs without blacklisting them."""
        requested_ids = self._normalize_job_ids(job_ids)
        affected_ids = [
            job_id for job_id in requested_ids if self.db.get_job_by_id(job_id)
        ]
        self.db.delete_jobs(affected_ids)
        return self._command_result(
            affected_ids,
            total_requested=len(requested_ids),
        )

    def delete_jobs_below_score(self, score: int) -> JobCommandResult:
        """Delete unprotected active jobs below a relevance score.

        Chroma embeddings for these jobs are pruned by the scheduler's own
        periodic sync, not from here — see ``search_similar``.
        """
        count = self.db.delete_jobs_below_score(score)
        return JobCommandResult(success=count > 0, affected_count=count)

    def delete_stale_jobs(self, days: int) -> JobCommandResult:
        """Delete unprotected active jobs older than a last-seen threshold.

        Chroma embeddings for these jobs are pruned by the scheduler's own
        periodic sync, not from here — see ``search_similar``.
        """
        count = self.db.delete_stale_jobs(days)
        return JobCommandResult(success=count > 0, affected_count=count)

    def purge_blacklist(self, older_than_days: int | None = None) -> JobCommandResult:
        """Purge blacklist rows, optionally older than a threshold."""
        count = self.db.purge_blacklist(older_than_days)
        return JobCommandResult(success=count > 0, affected_count=count)

    def export_jobs(
        self,
        *,
        query: JobListQuery | None = None,
        job_ids: list[str] | None = None,
        fmt: JobExportFormat = "csv",
    ) -> JobExportResult:
        """Serialize selected or filtered jobs for download/export surfaces."""
        if job_ids is not None:
            records = self.db.get_jobs_by_ids(self._normalize_job_ids(job_ids))
        else:
            export_query = query or JobListQuery(limit=1000)
            export_query = JobListQuery(
                **{**asdict(export_query), "limit": 1000, "offset": 0}
            )
            records = self.list_jobs(export_query).jobs

        rows = [self._record_to_export_row(record) for record in records]
        if fmt == "json":
            return JobExportResult(
                content=json.dumps(rows).encode("utf-8"),
                media_type="application/json",
                filename="jobs.json",
                row_count=len(rows),
            )
        if fmt != "csv":
            raise ValueError(f"Unsupported export format: {fmt}")

        buffer = StringIO()
        fieldnames = list(rows[0]) if rows else list(JobDBRecord.__dataclass_fields__)
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return JobExportResult(
            content=buffer.getvalue().encode("utf-8"),
            media_type="text/csv",
            filename="jobs.csv",
            row_count=len(rows),
        )

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
        """Run cleanup and return the resulting counts.

        Chroma embeddings for jobs deleted here are pruned by the
        scheduler's own periodic sync, not from here — see
        ``search_similar``.
        """
        report = self.db.reconcile_with_config(config)
        return CleanupResult(
            deleted_below_score=report.deleted_below_score,
            deleted_stale=report.deleted_stale,
            purged_blacklist=report.purged_blacklist,
            protected_bookmarked=report.protected_bookmarked,
            protected_applied=report.protected_applied,
        )
