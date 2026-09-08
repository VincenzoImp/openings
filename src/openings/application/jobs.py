"""The one application service behind the dashboard, REST and MCP.

Every surface calls the same methods, so behaviour cannot drift between a
click, an HTTP request and an agent's tool call.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from openings.application.attachments import AttachmentStore
from openings.application.bundle import build_bundle
from openings.application.models import (
    AddJobCommand,
    AttachmentEntry,
    CommandResult,
    ExportFormat,
    ExportResult,
    JobDetail,
    JobPage,
    SemanticResult,
    SourceStatus,
)
from openings.db import JobDatabase, JobQuery, ReconciliationReport
from openings.logger import get_logger
from openings.models import (
    POSTING_FIELDS,
    Attachment,
    AttachmentKind,
    Job,
    JobStatus,
    Note,
    NoteKind,
    RunSummary,
    SOURCE_MANUAL,
)
from openings.project_meta import get_project_version
from openings.scheduler import request_run, run_requested
from openings.scoring import calculate_relevance_score, explain_score
from openings.sources.manual import record_from_fields

if TYPE_CHECKING:
    from openings.config import Config
    from openings.embeddings import Embeddings
    from openings.runtime import Runtime


class VectorStoreUnavailableError(RuntimeError):
    pass


class JobApplicationService:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime
        self.logger = get_logger("service")

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------

    @property
    def db(self) -> JobDatabase:
        return self.runtime.db

    @property
    def config(self) -> Config:
        return self.runtime.config()

    @property
    def attachments(self) -> AttachmentStore:
        return self.runtime.attachments

    @property
    def embeddings(self) -> Embeddings | None:
        return self.runtime.embeddings

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
            explain=explain_score(job, self.config),
            labels=self.db.get_labels(job_id),
            postings=self.db.list_postings(job_id),
            notes=self.db.list_notes(job_id),
            attachments=self.db.list_attachments(job_id),
            events=self.db.list_events(job_id),
        )

    def get_statistics(self) -> dict:
        return self.db.get_statistics()

    def get_score_distribution(self, bin_size: int = 5) -> list[list[int]]:
        return self.db.get_score_distribution(bin_size)

    def get_facets(self, limit: int = 50, q: str | None = None) -> dict:
        return self.db.get_facets(limit=limit, q=q)

    def list_runs(self, limit: int = 20) -> list[RunSummary]:
        return self.db.list_runs(limit)

    def run_status(self) -> dict[str, Any]:
        open_run = self.db.open_run()
        return {
            "running": open_run is not None,
            "run": open_run.to_dict() if open_run else None,
            "requested": run_requested(self.config.run_now_path),
        }

    def request_run(self) -> dict[str, Any]:
        request_run(self.config.run_now_path)
        return self.run_status()

    def list_sources(self) -> list[SourceStatus]:
        config = self.config
        by_source = self.db.source_counts()
        by_company = self.db.company_source_counts()
        last_run = self.db.list_runs(1)
        stats_by_name: dict[str, dict[str, Any]] = {}
        if last_run:
            for stat in last_run[0].sources:
                data = stat.to_dict()
                data["started_at"] = last_run[0].started_at.isoformat()
                stats_by_name[stat.name] = data

        sources: list[SourceStatus] = []
        jobspy = config.sources.jobspy
        sources.append(
            SourceStatus(
                name="jobspy",
                kind="boards",
                detail=", ".join(jobspy.sites) if jobspy.sites else "no sites",
                enabled=jobspy.enabled and bool(jobspy.all_queries),
                active_jobs=sum(by_source.get(site, 0) for site in jobspy.sites),
                last_run=stats_by_name.get("jobspy"),
            )
        )
        for company in config.sources.companies:
            sources.append(
                SourceStatus(
                    name=company.name,
                    kind=company.ats,
                    detail=company.slug,
                    enabled=True,
                    active_jobs=by_company.get((company.name, company.ats), 0),
                    last_run=stats_by_name.get(f"{company.ats}:{company.slug}"),
                )
            )
        for feed in config.sources.feeds:
            sources.append(
                SourceStatus(
                    name=feed.name,
                    kind="rss",
                    detail=feed.url,
                    enabled=True,
                    active_jobs=by_company.get((feed.name, "rss"), 0),
                    last_run=stats_by_name.get(f"rss:{feed.name}"),
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
                    active_jobs=by_source.get("adzuna", 0),
                    last_run=stats_by_name.get("adzuna"),
                )
            )
        sources.append(
            SourceStatus(
                name=SOURCE_MANUAL,
                kind=SOURCE_MANUAL,
                detail="add_job",
                enabled=True,
                active_jobs=by_source.get(SOURCE_MANUAL, 0),
            )
        )
        return sources

    def company_status_counts(self, company: str) -> dict[str, int]:
        return self.db.company_status_counts(company)

    def settings_summary(self) -> dict[str, Any]:
        config = self.config
        return {
            "version": get_project_version(),
            "profile": {
                "name": config.profile.name,
                "headline": config.profile.headline,
                "target": config.profile.target,
            },
            "scoring": {
                "save_threshold": config.scoring.save_threshold,
                "notify_threshold": config.scoring.notify_threshold,
                "weights": dict(config.scoring.weights),
                "keywords": {key: list(value) for key, value in config.scoring.keywords.items()},
            },
            "scheduler": {
                "interval_hours": config.scheduler.interval_hours,
                "run_on_startup": config.scheduler.run_on_startup,
            },
            "sources": {
                "jobspy": {
                    "enabled": config.sources.jobspy.enabled,
                    "sites": list(config.sources.jobspy.sites),
                    "locations": list(config.sources.jobspy.locations),
                    "queries": config.sources.jobspy.all_queries,
                    "job_types": list(config.sources.jobspy.job_types),
                    "hours_old": config.sources.jobspy.hours_old,
                },
                "companies": [
                    {"name": c.name, "ats": c.ats, "slug": c.slug, "locations": list(c.locations)}
                    for c in config.sources.companies
                ],
                "feeds": [{"name": f.name, "url": f.url} for f in config.sources.feeds],
                "adzuna": {"enabled": config.sources.adzuna.enabled},
            },
            "notifications": {
                "telegram": config.notifications.enabled
                and config.notifications.telegram.enabled
                and bool(config.notifications.telegram.chat_ids),
            },
            "retention": {"max_age_days": config.retention.max_age_days},
            "attachments": {"max_size_mb": config.attachments.max_size_mb},
            "embeddings": {
                "enabled": config.embeddings.enabled,
                "status": self.runtime.embeddings_status,
            },
            "timezone": config.logging.timezone,
            "data_dir": str(config.data_dir),
        }

    def search_similar(
        self,
        query: str | None = None,
        *,
        job_id: str | None = None,
        n_results: int = 10,
        min_score: int | None = None,
        source: str | None = None,
        statuses: Sequence[str] = (),
    ) -> list[SemanticResult]:
        embeddings = self.embeddings
        if embeddings is None:
            raise VectorStoreUnavailableError(
                f"Semantic search is not available ({self.runtime.embeddings_status})"
            )
        wanted = max(1, int(n_results))
        # Over-fetch so post-filters still leave enough results.
        if job_id:
            hits = embeddings.similar(job_id, wanted * 4)
        else:
            hits = embeddings.search(query or "", wanted * 4)
        jobs = {job.job_id: job for job in self.db.get_jobs([hit for hit, _ in hits])}
        allowed = {status.lower() for status in statuses if status}
        results: list[SemanticResult] = []
        for hit_id, similarity in hits:
            job = jobs.get(hit_id)
            if job is None:
                continue
            if min_score is not None and job.relevance_score < min_score:
                continue
            if source and job.source.lower() != source.lower():
                continue
            if allowed and job.status.value not in allowed:
                continue
            results.append(SemanticResult(job=job, similarity=similarity))
            if len(results) >= wanted:
                break
        return results

    # ------------------------------------------------------------------
    # Commands: jobs
    # ------------------------------------------------------------------

    def _embed(self, job_ids: Sequence[str]) -> None:
        config = self.config
        if not (config.embeddings.enabled and config.embeddings.embed_on_save):
            return
        embeddings = self.embeddings
        if embeddings is None:
            return
        try:
            embeddings.embed_jobs(self.db.get_jobs(job_ids))
        except Exception as exc:  # noqa: BLE001 - search is best effort
            self.logger.warning("Embedding failed: %s", exc)

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
        job = Job.from_row(record)
        existing = self.db.find_job(job.posting_key, job.identity)
        if existing is not None:
            if existing.status is JobStatus.BLACKLISTED:
                return CommandResult(
                    success=False,
                    job_ids=[existing.job_id],
                    message="This posting is blacklisted; restore it first",
                )
            changes = {
                key: value
                for key, value in record.items()
                if key in POSTING_FIELDS and value not in (None, "")
            }
            self.update_job(existing.job_id, changes)
            job_id, was_new = existing.job_id, False
        else:
            job = Job.from_row(
                {**record, "relevance_score": calculate_relevance_score(job, self.config)}
            )
            result = self.db.upsert_jobs([job])
            job_id, was_new = job.job_id, job.job_id in result.new_ids
            if result.skipped_blacklisted:
                return CommandResult(
                    success=False, job_ids=[job_id], message="This posting is blacklisted"
                )
        if was_new and command.status is not JobStatus.NEW:
            self.db.set_status([job_id], command.status, note="added by hand")
        if command.labels:
            self.db.add_labels([job_id], list(command.labels))
        if command.note:
            self.db.add_note(job_id, NoteKind.NOTE, command.note)
        self._embed([job_id])
        return CommandResult(
            success=True,
            affected_count=1,
            job_ids=[job_id],
            message="created" if was_new else "updated",
        )

    def update_job(self, job_id: str, changes: dict[str, Any]) -> Job | None:
        """Edit posting fields, rescore and re-embed."""
        current = self.db.get_job(job_id)
        if current is None:
            return None
        allowed = {key: value for key, value in changes.items() if key in POSTING_FIELDS}
        merged = Job.from_row({**current.to_dict(), **allowed})
        updated = self.db.update_job(
            job_id, allowed, score=calculate_relevance_score(merged, self.config)
        )
        if updated is not None and allowed:
            self._embed([job_id])
        return updated

    def set_status(
        self, job_ids: Sequence[str], status: JobStatus, note: str | None = None
    ) -> CommandResult:
        changed = self.db.set_status(job_ids, status, note=note)
        if status is JobStatus.BLACKLISTED:
            self.db.delete_embeddings(changed)
        elif changed:
            self._embed_missing(changed)
        return CommandResult(success=True, affected_count=len(changed), job_ids=changed)

    def _embed_missing(self, job_ids: Sequence[str]) -> None:
        embeddings = self.embeddings
        if embeddings is None:
            return
        missing = set(embeddings.db.jobs_without_embedding(embeddings.model_name))
        wanted = [job_id for job_id in job_ids if job_id in missing]
        if wanted:
            self._embed(wanted)

    def blacklist_jobs(self, job_ids: Sequence[str], note: str | None = None) -> CommandResult:
        return self.set_status(job_ids, JobStatus.BLACKLISTED, note)

    def unblacklist_jobs(self, job_ids: Sequence[str]) -> CommandResult:
        """Restore blacklisted jobs to the status they held before."""
        ids = list(dict.fromkeys(job_ids))
        jobs = [job for job in self.db.get_jobs(ids) if job.status is JobStatus.BLACKLISTED]
        previous = self.db.previous_statuses([job.job_id for job in jobs])
        changed: list[str] = []
        for job in jobs:
            target = previous.get(job.job_id, JobStatus.NEW.value)
            try:
                status = JobStatus(target)
            except ValueError:
                status = JobStatus.NEW
            if status is JobStatus.BLACKLISTED:
                status = JobStatus.NEW
            changed.extend(self.db.set_status([job.job_id], status, note="restored"))
        self._embed(changed)
        return CommandResult(success=True, affected_count=len(changed), job_ids=changed)

    def delete_jobs(self, job_ids: Sequence[str]) -> CommandResult:
        ids = list(dict.fromkeys(job_ids))
        affected = self.db.delete_jobs(ids)
        for job_id in ids:
            self.attachments.delete_job(job_id)
        return CommandResult(success=True, affected_count=affected, job_ids=ids)

    def merge_jobs(self, primary_id: str, other_ids: Sequence[str]) -> CommandResult:
        result = self.db.merge_jobs(primary_id, other_ids)
        if result is None:
            return CommandResult(success=False, message=f"Job not found: {primary_id}")
        for previous, stored_name in result.moved_attachments:
            self.attachments.move(previous, primary_id, stored_name)
        for previous in result.merged_ids:
            self.attachments.delete_job(previous)
        self._embed([primary_id])
        return CommandResult(
            success=True,
            affected_count=len(result.merged_ids),
            job_ids=[primary_id, *result.merged_ids],
            message="merged" if result.merged_ids else "nothing to merge",
        )

    # ------------------------------------------------------------------
    # Commands: labels, notes, attachments
    # ------------------------------------------------------------------

    def add_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> CommandResult:
        added = self.db.add_labels(job_ids, labels)
        return CommandResult(success=True, affected_count=added, job_ids=list(job_ids))

    def remove_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> CommandResult:
        removed = self.db.remove_labels(job_ids, labels)
        return CommandResult(success=True, affected_count=removed, job_ids=list(job_ids))

    def rename_label(self, old: str, new: str) -> CommandResult:
        return CommandResult(success=True, affected_count=self.db.rename_label(old, new))

    def delete_label(self, label: str) -> CommandResult:
        return CommandResult(success=True, affected_count=self.db.delete_label(label))

    def add_note(
        self, job_id: str, kind: NoteKind, body: str, title: str | None = None
    ) -> Note | None:
        if not body.strip():
            raise ValueError("note body is required")
        return self.db.add_note(job_id, kind, body, title=title)

    def update_note(
        self,
        job_id: str,
        note_id: int,
        *,
        body: str | None = None,
        title: str | None = None,
        kind: NoteKind | None = None,
    ) -> Note | None:
        if body is not None and not body.strip():
            raise ValueError("note body is required")
        return self.db.update_note(job_id, note_id, body=body, title=title, kind=kind)

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
        try:
            attachment = self.db.add_attachment(
                job_id,
                kind=kind,
                filename=filename,
                stored_name=stored_name,
                sha256=digest,
                size_bytes=size,
                note=note,
            )
        except Exception:
            self.attachments.delete(job_id, stored_name)
            raise
        if attachment is None:
            self.attachments.delete(job_id, stored_name)
        return attachment

    def update_attachment(
        self,
        job_id: str,
        attachment_id: int,
        *,
        kind: AttachmentKind | None = None,
        note: str | None = None,
        filename: str | None = None,
    ) -> Attachment | None:
        return self.db.update_attachment(
            job_id, attachment_id, kind=kind, note=note, filename=filename
        )

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

    def list_attachments(
        self,
        *,
        kind: AttachmentKind | None = None,
        statuses: Sequence[str] = (),
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AttachmentEntry], int]:
        rows, total = self.db.list_all_attachments(
            kind=kind, statuses=statuses, limit=limit, offset=offset
        )
        return [AttachmentEntry(att, title, company) for att, title, company in rows], total

    def delete_attachment(self, job_id: str, attachment_id: int) -> bool:
        attachment = self.db.delete_attachment(job_id, attachment_id)
        if attachment is None:
            return False
        self.attachments.delete(job_id, attachment.stored_name)
        return True

    def build_bundle(self, job_id: str) -> tuple[bytes, str] | None:
        detail = self.get_job_detail(job_id)
        if detail is None:
            return None
        files = [
            (attachment.filename, self.attachments.path(job_id, attachment.stored_name))
            for attachment in detail.attachments
        ]
        stem = "-".join(part for part in (detail.job.company, detail.job.title) if part).lower()
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in stem)[:80] or "job"
        return build_bundle(detail, files), f"openings-{safe}.zip"

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def delete_below_score(self, score: int, *, dry_run: bool = False) -> CommandResult:
        if dry_run:
            return CommandResult(
                success=True, affected_count=self.db.count_below_score(score), message="dry run"
            )
        return CommandResult(success=True, affected_count=self.db.delete_below_score(score))

    def delete_stale(self, days: int, *, dry_run: bool = False) -> CommandResult:
        if dry_run:
            return CommandResult(
                success=True, affected_count=self.db.count_stale(days), message="dry run"
            )
        return CommandResult(success=True, affected_count=self.db.delete_stale(days))

    def preview_cleanup(self) -> ReconciliationReport:
        return self.db.preview_reconcile(self.config)

    def run_cleanup(self) -> ReconciliationReport:
        return self.db.reconcile(self.config)

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
        "status_changed_at",
        "min_amount",
        "max_amount",
        "currency",
        "labels",
        "notes_count",
        "attachments_count",
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
