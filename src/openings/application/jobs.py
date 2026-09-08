"""The one application service behind the dashboard, REST and MCP.

Every surface calls the same methods, so behaviour cannot drift between a
click, an HTTP request and an agent's tool call.
"""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Callable, Sequence

from openings.application.attachments import AttachmentStore
from openings.application.models import (
    AddJobCommand,
    CommandResult,
    ExportFormat,
    ExportResult,
    JobDetail,
    JobPage,
    SemanticResult,
    SourceStatus,
)
from openings.database import BlacklistQuery, JobDatabase, JobQuery, ReconciliationReport
from openings.logger import get_logger
from openings.models import (
    Attachment,
    AttachmentKind,
    BlacklistEntry,
    Job,
    JobStatus,
    Note,
    NoteKind,
    RunSummary,
)
from openings.scoring import calculate_relevance_score, explain_score
from openings.sources.manual import record_from_fields

if TYPE_CHECKING:
    from pathlib import Path

    from openings.config import Config
    from openings.vector_store import ReadOnlyVectorStore


class VectorStoreUnavailableError(RuntimeError):
    pass


class JobApplicationService:
    def __init__(
        self,
        db: JobDatabase,
        config_provider: Callable[[], Config],
        attachments: AttachmentStore,
        vector_store_factory: Callable[[], ReadOnlyVectorStore | None] | None = None,
    ):
        self.db = db
        self._config = config_provider
        self.attachments = attachments
        self._vector_store_factory = vector_store_factory
        self.logger = get_logger("service")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_jobs(self, query: JobQuery) -> JobPage:
        jobs, total = self.db.query_jobs(query)
        labels = self.db.get_labels_for([job.job_id for job in jobs])
        return JobPage(
            jobs=jobs,
            total=total,
            limit=max(1, min(int(query.limit), self.db.MAX_QUERY_LIMIT)),
            offset=max(0, int(query.offset)),
            labels=labels,
        )

    def get_job(self, job_id: str) -> Job | None:
        return self.db.get_job(job_id)

    def get_job_detail(self, job_id: str) -> JobDetail | None:
        job = self.db.get_job(job_id)
        if job is None:
            return None
        return JobDetail(
            job=job,
            explain=explain_score(job, self._config()),
            labels=self.db.get_labels(job_id),
            notes=self.db.list_notes(job_id),
            attachments=self.db.list_attachments(job_id),
            events=self.db.list_events(job_id),
        )

    def get_statistics(self) -> dict:
        return self.db.get_statistics()

    def get_score_distribution(self, bin_size: int = 5) -> list[list[int]]:
        return self.db.get_score_distribution(bin_size)

    def get_facets(self) -> dict:
        return self.db.get_facets()

    def list_blacklist(self, query: BlacklistQuery) -> tuple[list[BlacklistEntry], int]:
        return self.db.list_blacklist(query)

    def list_runs(self, limit: int = 20) -> list[RunSummary]:
        return self.db.list_runs(limit)

    def list_sources(self) -> list[SourceStatus]:
        config = self._config()
        counts = {
            item["value"]: item["count"] for item in self.db.get_facets(limit=1000)["sources"]
        }
        company_counts = {
            item["value"]: item["count"] for item in self.db.get_facets(limit=1000)["companies"]
        }
        sources: list[SourceStatus] = []
        jobspy = config.sources.jobspy
        sources.append(
            SourceStatus(
                name="jobspy",
                kind="boards",
                detail=", ".join(jobspy.sites) if jobspy.sites else "no sites",
                enabled=jobspy.enabled and bool(jobspy.all_queries),
                active_jobs=sum(counts.get(site, 0) for site in jobspy.sites),
            )
        )
        for company in config.sources.companies:
            sources.append(
                SourceStatus(
                    name=company.name,
                    kind=company.ats,
                    detail=company.slug,
                    enabled=True,
                    active_jobs=company_counts.get(company.name, 0),
                )
            )
        for feed in config.sources.feeds:
            sources.append(
                SourceStatus(
                    name=feed.name, kind="rss", detail=feed.url, enabled=True, active_jobs=0
                )
            )
        adzuna = config.sources.adzuna
        if adzuna.enabled:
            sources.append(
                SourceStatus(
                    name="adzuna",
                    kind="adzuna",
                    detail=adzuna.country,
                    enabled=True,
                    active_jobs=counts.get("adzuna", 0),
                )
            )
        sources.append(
            SourceStatus(
                name="manual",
                kind="manual",
                detail="add_job",
                enabled=True,
                active_jobs=counts.get("manual", 0),
            )
        )
        return sources

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        min_score: int | None = None,
        source: str | None = None,
    ) -> list[SemanticResult]:
        store = self._vector_store_factory() if self._vector_store_factory else None
        if store is None:
            raise VectorStoreUnavailableError("Vector store not available")
        hits = store.search(query, n_results=n_results, min_score=min_score, source=source)
        jobs = {job.job_id: job for job in self.db.get_jobs([hit.job_id for hit in hits])}
        results: list[SemanticResult] = []
        for hit in hits:
            job = jobs.get(hit.job_id)
            if job is None:
                continue  # embedding not yet pruned for a deleted job
            results.append(
                SemanticResult(
                    job_id=job.job_id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    similarity=hit.similarity,
                    relevance_score=job.relevance_score,
                    source=job.source,
                    status=job.status.value,
                    job_url=job.job_url,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def add_job(self, command: AddJobCommand) -> CommandResult:
        if not command.title.strip() or not command.company.strip():
            return CommandResult(success=False, message="title and company are required")
        record = record_from_fields(
            title=command.title,
            company=command.company,
            location=command.location or "",
            job_url=command.job_url,
            description=command.description,
            date_posted=command.date_posted,
            job_type=command.job_type,
            is_remote=command.is_remote,
            job_level=command.job_level,
            min_amount=command.min_amount,
            max_amount=command.max_amount,
            currency=command.currency,
            salary_interval=command.salary_interval,
            company_url=command.company_url,
            source=command.source,
            external_id=command.external_id,
        )
        config = self._config()
        job = Job.from_row(record)
        job = Job.from_row(
            {
                **record,
                "job_id": job.job_id,
                "relevance_score": calculate_relevance_score(job, config),
            }
        )
        if self.db.blacklisted_ids([job.job_id]):
            return CommandResult(
                success=False,
                job_ids=[job.job_id],
                message="This posting is blacklisted; remove it from the blacklist first",
            )
        result = self.db.upsert_jobs([job])
        was_new = job.job_id in result.new_ids
        if command.status is not JobStatus.NEW:
            self.db.set_status([job.job_id], command.status, note="added by hand")
        if command.labels:
            self.db.add_labels([job.job_id], list(command.labels))
        if command.note:
            self.db.add_note(job.job_id, NoteKind.NOTE, command.note)
        return CommandResult(
            success=True,
            affected_count=1,
            job_ids=[job.job_id],
            message="created" if was_new else "updated",
        )

    def set_status(
        self, job_ids: Sequence[str], status: JobStatus, note: str | None = None
    ) -> CommandResult:
        changed = self.db.set_status(job_ids, status, note=note)
        return CommandResult(success=True, affected_count=len(changed), job_ids=changed)

    def add_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> CommandResult:
        added = self.db.add_labels(job_ids, labels)
        return CommandResult(success=True, affected_count=added, job_ids=list(job_ids))

    def remove_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> CommandResult:
        removed = self.db.remove_labels(job_ids, labels)
        return CommandResult(success=True, affected_count=removed, job_ids=list(job_ids))

    def add_note(
        self, job_id: str, kind: NoteKind, body: str, title: str | None = None
    ) -> Note | None:
        if not body.strip():
            raise ValueError("note body is required")
        return self.db.add_note(job_id, kind, body, title=title)

    def delete_note(self, job_id: str, note_id: int) -> bool:
        return self.db.delete_note(job_id, note_id)

    def add_attachment(
        self,
        job_id: str,
        *,
        kind: AttachmentKind,
        filename: str,
        content: bytes,
        note: str | None = None,
    ) -> Attachment | None:
        if self.db.get_job(job_id) is None:
            return None
        stored_name, digest, size = self.attachments.save(job_id, filename, content)
        attachment = self.db.add_attachment(
            job_id,
            kind=kind,
            filename=filename,
            stored_name=stored_name,
            sha256=digest,
            size_bytes=size,
            note=note,
        )
        if attachment is None:
            self.attachments.delete(job_id, stored_name)
        return attachment

    def get_attachment_file(
        self, job_id: str, attachment_id: int
    ) -> tuple[Attachment, Path] | None:
        attachment = self.db.get_attachment(job_id, attachment_id)
        if attachment is None:
            return None
        path = self.attachments.path(job_id, attachment.stored_name)
        if not path.is_file():
            return None
        return attachment, path

    def delete_attachment(self, job_id: str, attachment_id: int) -> bool:
        attachment = self.db.delete_attachment(job_id, attachment_id)
        if attachment is None:
            return False
        self.attachments.delete(job_id, attachment.stored_name)
        return True

    def blacklist_jobs(self, job_ids: Sequence[str]) -> CommandResult:
        ids = list(dict.fromkeys(job_ids))
        affected = self.db.blacklist_jobs(ids)
        for job_id in ids:
            self.attachments.delete_job(job_id)
        return CommandResult(success=True, affected_count=affected, job_ids=ids)

    def unblacklist_jobs(self, job_ids: Sequence[str]) -> CommandResult:
        ids = list(dict.fromkeys(job_ids))
        return CommandResult(
            success=True, affected_count=self.db.unblacklist_jobs(ids), job_ids=ids
        )

    def delete_jobs(self, job_ids: Sequence[str]) -> CommandResult:
        ids = list(dict.fromkeys(job_ids))
        affected = self.db.delete_jobs(ids)
        for job_id in ids:
            self.attachments.delete_job(job_id)
        return CommandResult(success=True, affected_count=affected, job_ids=ids)

    def delete_below_score(self, score: int) -> CommandResult:
        return CommandResult(success=True, affected_count=self.db.delete_below_score(score))

    def delete_stale(self, days: int) -> CommandResult:
        return CommandResult(success=True, affected_count=self.db.delete_stale(days))

    def purge_blacklist(self, older_than_days: int | None = None) -> CommandResult:
        return CommandResult(success=True, affected_count=self.db.purge_blacklist(older_than_days))

    def preview_cleanup(self) -> ReconciliationReport:
        return self.db.preview_reconcile(self._config())

    def run_cleanup(self) -> ReconciliationReport:
        return self.db.reconcile(self._config())

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    _EXPORT_COLUMNS = (
        "job_id",
        "title",
        "company",
        "location",
        "source",
        "status",
        "relevance_score",
        "job_url",
        "job_type",
        "is_remote",
        "job_level",
        "date_posted",
        "first_seen",
        "last_seen",
        "min_amount",
        "max_amount",
        "currency",
        "labels",
        "description",
    )

    def _export_rows(self, jobs: list[Job]) -> list[dict]:
        labels = self.db.get_labels_for([job.job_id for job in jobs])
        rows = []
        for job in jobs:
            data = job.to_dict()
            data["labels"] = ", ".join(labels.get(job.job_id, []))
            rows.append({column: data.get(column) for column in self._EXPORT_COLUMNS})
        return rows

    def export_jobs(
        self,
        *,
        job_ids: Sequence[str] | None = None,
        query: JobQuery | None = None,
        fmt: ExportFormat = "csv",
    ) -> ExportResult:
        if job_ids is not None:
            jobs = self.db.get_jobs(job_ids)
            total = len(jobs)
        else:
            base = query or JobQuery()
            if base.limit == 0:
                jobs = []
                offset = 0
                while True:
                    page, total = self.db.query_jobs(
                        JobQuery(
                            **{**base.__dict__, "limit": self.db.MAX_QUERY_LIMIT, "offset": offset}
                        )
                    )
                    jobs.extend(page)
                    offset += len(page)
                    if not page or offset >= total:
                        break
            else:
                jobs, total = self.db.query_jobs(base)
        rows = self._export_rows(jobs)
        if fmt == "json":
            content = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
            return ExportResult(content, "application/json", "openings.json", len(rows), total)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(self._EXPORT_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
        return ExportResult(
            buffer.getvalue().encode("utf-8"), "text/csv", "openings.csv", len(rows), total
        )
