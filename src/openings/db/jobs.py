"""Jobs: ingest, state changes, queries and statistics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Generator, Iterable, Sequence

from openings.db.base import (
    JOB_COLUMNS,
    JOB_SELECT,
    MAX_QUERY_LIMIT,
    Store,
    chunks,
    placeholders,
    unique,
)
from openings.db.postings import PostingsMixin
from openings.models import (
    POSTING_FIELDS,
    EventKind,
    Job,
    JobStatus,
    generate_job_id,
    job_id_for,
    utcnow,
)

if TYPE_CHECKING:
    from openings.config import Config

JOB_SORTS = ("score", "date", "first_seen", "updated", "company", "title", "salary")
SORT_DIRECTIONS = ("asc", "desc")

_ORDER_BY: dict[str, tuple[str, str]] = {
    # sort key -> (expression, natural direction)
    "score": ("jobs.relevance_score", "desc"),
    "date": ("COALESCE(jobs.date_posted, jobs.first_seen)", "desc"),
    "first_seen": ("jobs.first_seen", "desc"),
    "updated": ("jobs.status_changed_at", "desc"),
    "company": ("LOWER(jobs.company)", "asc"),
    "title": ("LOWER(jobs.title)", "asc"),
    "salary": ("COALESCE(jobs.max_amount, jobs.min_amount, 0)", "desc"),
}

_BLACKLISTED = JobStatus.BLACKLISTED.value


@dataclass(frozen=True)
class JobQuery:
    """Filter and pagination parameters shared by the dashboard, REST and MCP.

    Without ``statuses`` every status except ``blacklisted`` is returned.
    """

    limit: int = 50
    offset: int = 0
    statuses: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    company: str | None = None
    location: str | None = None
    locations: tuple[str, ...] = ()
    job_types: tuple[str, ...] = ()
    remote: bool | None = None
    min_score: int | None = None
    max_score: int | None = None
    min_salary: float | None = None
    max_salary: float | None = None
    date_posted_from: str | None = None
    date_posted_to: str | None = None
    first_seen_from: str | None = None
    first_seen_to: str | None = None
    last_seen_from: str | None = None
    last_seen_to: str | None = None
    status_changed_from: str | None = None
    status_changed_to: str | None = None
    has_attachments: bool | None = None
    without_labels: bool | None = None
    text: str | None = None
    sort: str = "score"
    direction: str | None = None


@dataclass
class UpsertResult:
    new_ids: list[str] = field(default_factory=list)
    updated_ids: list[str] = field(default_factory=list)
    new_postings: list[str] = field(default_factory=list)
    skipped_blacklisted: int = 0

    @property
    def new_count(self) -> int:
        return len(self.new_ids)

    @property
    def updated_count(self) -> int:
        return len(self.updated_ids)


@dataclass
class MergeResult:
    primary_id: str
    merged_ids: list[str] = field(default_factory=list)
    moved_attachments: list[tuple[str, str]] = field(default_factory=list)
    """``(previous job id, stored name)`` of every attachment file to relocate."""


def _date_value(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class JobsMixin(PostingsMixin, Store):
    INSERT_JOB = (
        f"INSERT INTO jobs ({', '.join(JOB_COLUMNS)}) VALUES ({placeholders(len(JOB_COLUMNS))})"
    )

    REFRESH_JOB = f"""
        UPDATE jobs SET
            last_seen = ?,
            relevance_score = ?,
            external_id = COALESCE(jobs.external_id, ?),
            job_url = COALESCE(jobs.job_url, ?),
            description = COALESCE(?, jobs.description),
            date_posted = COALESCE(jobs.date_posted, ?),
            job_type = COALESCE(?, jobs.job_type),
            is_remote = COALESCE(?, jobs.is_remote),
            job_level = COALESCE(?, jobs.job_level),
            min_amount = COALESCE(?, jobs.min_amount),
            max_amount = COALESCE(?, jobs.max_amount),
            currency = COALESCE(?, jobs.currency),
            salary_interval = COALESCE(?, jobs.salary_interval),
            company_url = COALESCE(?, jobs.company_url),
            raw_json = COALESCE(?, jobs.raw_json)
        WHERE job_id = ? AND status != '{_BLACKLISTED}'
    """

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def _jobs_for_identities(
        self, conn: sqlite3.Connection, identities: Iterable[str]
    ) -> dict[str, list[tuple[str, str, set[str]]]]:
        """``identity -> [(job_id, status, posting sources)]``."""
        found: dict[str, list[tuple[str, str, set[str]]]] = {}
        ids = unique(identities)
        if not ids:
            return found
        job_ids: list[str] = []
        for chunk in chunks(ids):
            rows = conn.execute(
                "SELECT job_id, identity, status, source FROM jobs "
                f"WHERE identity IN ({placeholders(len(chunk))})",
                list(chunk),
            ).fetchall()
            for row in rows:
                found.setdefault(row["identity"], []).append(
                    (row["job_id"], row["status"], {str(row["source"]).lower()})
                )
                job_ids.append(row["job_id"])
        for chunk in chunks(job_ids):
            rows = conn.execute(
                "SELECT job_id, source FROM postings "
                f"WHERE job_id IN ({placeholders(len(chunk))})",
                list(chunk),
            ).fetchall()
            sources: dict[str, set[str]] = {}
            for row in rows:
                sources.setdefault(row["job_id"], set()).add(str(row["source"]).lower())
            for entries in found.values():
                for job_id, _status, known in entries:
                    known.update(sources.get(job_id, set()))
        return found

    def upsert_jobs(self, jobs: Iterable[Job]) -> UpsertResult:
        """Insert new openings, refresh known ones, attach mirrors. Never touches status.

        A posting whose key is known refreshes its job. An unknown posting
        whose identity matches a job seen on another source becomes a new
        posting of that job. Anything else is a new job. Blacklisted jobs are
        skipped entirely.
        """
        result = UpsertResult()
        batch = list(jobs)
        if not batch:
            return result
        keys = [job.posting_key for job in batch]
        known_keys = self.jobs_for_posting_keys([key for key in keys if key])
        today = date.today()
        seen_in_batch: dict[str, str] = {}

        with self._connection() as conn:
            by_identity = self._jobs_for_identities(conn, [job.identity for job in batch])
            conn.execute("BEGIN")
            for job, key in zip(batch, keys):
                target: str | None = known_keys.get(key) if key else None
                mirror = False
                if target is None and key:
                    target = seen_in_batch.get(key)
                if target is None:
                    for job_id, _status, sources in by_identity.get(job.identity, []):
                        if job.source.lower() not in sources:
                            target, mirror = job_id, True
                            sources.add(job.source.lower())
                            break
                if target is None:
                    target = seen_in_batch.get(f"id:{job.identity}") if not key else None
                if target is None:
                    target = job_id_for(key, job.identity)

                row = conn.execute(
                    "SELECT status FROM jobs WHERE job_id = ?", (target,)
                ).fetchone()
                if row is not None and row["status"] == _BLACKLISTED:
                    result.skipped_blacklisted += 1
                    continue

                if row is None:
                    stored = Job.from_row({**job.to_dict(), "job_id": target})
                    conn.execute(self.INSERT_JOB, self.job_params(stored))
                    self._insert_event(
                        conn,
                        target,
                        EventKind.INGESTED,
                        f"First seen via {job.source}",
                        {"source": job.source},
                    )
                    result.new_ids.append(target)
                    by_identity.setdefault(job.identity, []).append(
                        (target, JobStatus.NEW.value, {job.source.lower()})
                    )
                else:
                    conn.execute(
                        self.REFRESH_JOB,
                        (
                            job.last_seen or today,
                            job.relevance_score,
                            job.external_id,
                            job.job_url,
                            job.description,
                            job.date_posted,
                            job.job_type,
                            job.is_remote,
                            job.job_level,
                            job.min_amount,
                            job.max_amount,
                            job.currency,
                            job.salary_interval,
                            job.company_url,
                            job.raw_json,
                            target,
                        ),
                    )
                    if target not in result.new_ids and target not in result.updated_ids:
                        result.updated_ids.append(target)

                if key:
                    is_new_posting = self._touch_posting(
                        conn,
                        target,
                        key,
                        job.source,
                        job.external_id,
                        job.job_url,
                        job.last_seen or today,
                    )
                    if is_new_posting and row is not None:
                        result.new_postings.append(target)
                        self._insert_event(
                            conn,
                            target,
                            EventKind.POSTING,
                            f"Also seen on {job.source}",
                            {"source": job.source, "url": job.job_url, "mirror": mirror},
                        )
                    seen_in_batch[key] = target
                else:
                    seen_in_batch[f"id:{job.identity}"] = target
            conn.commit()
        return result

    def find_job(self, key: str | None, identity: str) -> Job | None:
        """The job a posting key or an identity already belongs to, if any."""
        if key:
            known = self.jobs_for_posting_keys([key])
            if key in known:
                return self.get_job(known[key])
            direct = self.get_job(job_id_for(key, identity))
            if direct is not None:
                return direct
        with self._connection() as conn:
            row = conn.execute(
                f"SELECT {JOB_SELECT} FROM jobs WHERE identity = ? ORDER BY first_seen LIMIT 1",
                (identity,),
            ).fetchone()
        return self.row_to_job(row) if row else None

    def existing_ids(self, job_ids: Sequence[str]) -> set[str]:
        found: set[str] = set()
        with self._connection() as conn:
            for chunk in chunks(unique(job_ids)):
                rows = conn.execute(
                    f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders(len(chunk))})",
                    list(chunk),
                ).fetchall()
                found.update(row["job_id"] for row in rows)
        return found

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def set_status(
        self, job_ids: Sequence[str], status: JobStatus, *, note: str | None = None
    ) -> list[str]:
        """Move jobs to ``status`` and record an event for each change.

        Returns the ids whose status actually changed.
        """
        ids = unique(job_ids)
        if not ids:
            return []
        now = utcnow()
        changed: list[str] = []
        with self._connection() as conn:
            for chunk in chunks(ids):
                rows = conn.execute(
                    f"SELECT job_id, status FROM jobs WHERE job_id IN ({placeholders(len(chunk))})",
                    list(chunk),
                ).fetchall()
                for row in rows:
                    previous = row["status"]
                    if previous == status.value:
                        continue
                    conn.execute(
                        "UPDATE jobs SET status = ?, status_changed_at = ? WHERE job_id = ?",
                        (status.value, now, row["job_id"]),
                    )
                    summary = f"Status {previous} -> {status.value}"
                    if note:
                        summary = f"{summary}: {note}"
                    self._insert_event(
                        conn,
                        row["job_id"],
                        EventKind.STATUS,
                        summary,
                        {"from": previous, "to": status.value, "note": note},
                        now,
                    )
                    changed.append(row["job_id"])
            conn.commit()
        return changed

    def previous_statuses(self, job_ids: Sequence[str]) -> dict[str, str]:
        """For blacklisted jobs, the status they held before being blacklisted."""
        found: dict[str, str] = {}
        with self._connection() as conn:
            for chunk in chunks(unique(job_ids)):
                rows = conn.execute(
                    "SELECT job_id, data_json FROM events WHERE kind = 'status' "
                    f"AND job_id IN ({placeholders(len(chunk))}) ORDER BY created_at ASC, id ASC",
                    list(chunk),
                ).fetchall()
                for row in rows:
                    import json

                    data = json.loads(row["data_json"] or "{}")
                    if data.get("to") == _BLACKLISTED and data.get("from"):
                        found[row["job_id"]] = str(data["from"])
        return found

    def update_job(
        self, job_id: str, changes: dict[str, Any], *, score: int | None = None
    ) -> Job | None:
        """Edit posting fields; identity follows title, company and location."""
        allowed = {key: value for key, value in changes.items() if key in POSTING_FIELDS}
        current = self.get_job(job_id)
        if current is None:
            return None
        if not allowed and score is None:
            return current
        merged = Job.from_row({**current.to_dict(), **allowed})
        assignments = [f"{column} = ?" for column in allowed]
        params: list[Any] = [getattr(merged, column) for column in allowed]
        assignments.append("identity = ?")
        params.append(generate_job_id(merged.title, merged.company, merged.location))
        if score is not None:
            assignments.append("relevance_score = ?")
            params.append(int(score))
        params.append(job_id)
        with self._connection() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id = ?", params)
            if allowed:
                self._insert_event(
                    conn,
                    job_id,
                    EventKind.UPDATED,
                    "Posting edited: " + ", ".join(sorted(allowed)),
                    {"fields": sorted(allowed)},
                )
            conn.commit()
        return self.get_job(job_id)

    def delete_jobs(self, job_ids: Sequence[str]) -> int:
        """Permanently delete jobs of any status."""
        ids = unique(job_ids)
        if not ids:
            return 0
        deleted = 0
        with self._connection() as conn:
            for chunk in chunks(ids):
                cursor = conn.execute(
                    f"DELETE FROM jobs WHERE job_id IN ({placeholders(len(chunk))})", list(chunk)
                )
                deleted += cursor.rowcount
            conn.commit()
        return deleted

    def merge_jobs(self, primary_id: str, other_ids: Sequence[str]) -> MergeResult | None:
        """Fold ``other_ids`` into ``primary_id``: postings, notes, attachments, labels, events."""
        others = [job_id for job_id in unique(other_ids) if job_id != primary_id]
        primary = self.get_job(primary_id)
        if primary is None:
            return None
        result = MergeResult(primary_id=primary_id)
        with self._connection() as conn:
            conn.execute("BEGIN")
            for other in others:
                row = conn.execute(
                    "SELECT title, company, source FROM jobs WHERE job_id = ?", (other,)
                ).fetchone()
                if row is None:
                    continue
                for att in conn.execute(
                    "SELECT stored_name FROM attachments WHERE job_id = ?", (other,)
                ).fetchall():
                    result.moved_attachments.append((other, att["stored_name"]))
                for table in ("postings", "notes", "attachments", "events"):
                    conn.execute(
                        f"UPDATE {table} SET job_id = ? WHERE job_id = ?", (primary_id, other)
                    )
                conn.execute(
                    "INSERT OR IGNORE INTO job_labels (job_id, label) "
                    "SELECT ?, label FROM job_labels WHERE job_id = ?",
                    (primary_id, other),
                )
                conn.execute("DELETE FROM jobs WHERE job_id = ?", (other,))
                self._insert_event(
                    conn,
                    primary_id,
                    EventKind.MERGED,
                    f"Merged {row['title']} ({row['source']}) into this job",
                    {"merged_job_id": other, "source": row["source"]},
                )
                result.merged_ids.append(other)
            conn.commit()
        return result

    def rescore_all(self, config: Config) -> int:
        """Recompute every active job's score against the current configuration."""
        from openings.scoring import calculate_relevance_score

        updates: list[tuple[int, str]] = []
        for job in self.iter_jobs():
            score = calculate_relevance_score(job, config)
            if score != job.relevance_score:
                updates.append((score, job.job_id))
        if updates:
            with self._connection() as conn:
                conn.executemany("UPDATE jobs SET relevance_score = ? WHERE job_id = ?", updates)
                conn.commit()
        return len(updates)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Job | None:
        with self._connection() as conn:
            row = conn.execute(
                f"SELECT {JOB_SELECT} FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self.row_to_job(row) if row else None

    def get_jobs(self, job_ids: Sequence[str]) -> list[Job]:
        """Jobs in the order requested, skipping unknown ids."""
        ids = unique(job_ids)
        if not ids:
            return []
        found: dict[str, Job] = {}
        with self._connection() as conn:
            for chunk in chunks(ids):
                rows = conn.execute(
                    f"SELECT {JOB_SELECT} FROM jobs WHERE job_id IN ({placeholders(len(chunk))})",
                    list(chunk),
                ).fetchall()
                for row in rows:
                    job = self.row_to_job(row)
                    found[job.job_id] = job
        return [found[job_id] for job_id in ids if job_id in found]

    def iter_jobs(self, *, include_blacklisted: bool = False) -> Generator[Job, None, None]:
        where = "" if include_blacklisted else f"WHERE jobs.status != '{_BLACKLISTED}'"
        with self._connection() as conn:
            rows = conn.execute(f"SELECT {JOB_SELECT} FROM jobs {where}").fetchall()
        for row in rows:
            yield self.row_to_job(row)

    def count_jobs(self) -> int:
        with self._connection() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE status != '{_BLACKLISTED}'"
                ).fetchone()[0]
            )

    def _build_where(self, query: JobQuery) -> tuple[str, list[Any]]:
        where: list[str] = []
        params: list[Any] = []

        statuses = unique(query.statuses)
        if statuses:
            where.append(f"jobs.status IN ({placeholders(len(statuses))})")
            params.extend(status.lower() for status in statuses)
        else:
            where.append(f"jobs.status != '{_BLACKLISTED}'")
        sources = unique(query.sources)
        if sources:
            where.append(
                "(LOWER(jobs.source) IN ({0}) OR jobs.job_id IN "
                "(SELECT job_id FROM postings WHERE LOWER(source) IN ({0})))".format(
                    placeholders(len(sources))
                )
            )
            params.extend(source.lower() for source in sources)
            params.extend(source.lower() for source in sources)
        labels = unique(query.labels)
        if labels:
            where.append(
                "jobs.job_id IN (SELECT job_id FROM job_labels "
                f"WHERE LOWER(label) IN ({placeholders(len(labels))}))"
            )
            params.extend(label.lower() for label in labels)
        if query.company:
            where.append("LOWER(jobs.company) LIKE ?")
            params.append(f"%{query.company.lower()}%")
        if query.location:
            where.append("LOWER(jobs.location) LIKE ?")
            params.append(f"%{query.location.lower()}%")
        locations = unique(query.locations)
        if locations:
            where.append(f"LOWER(jobs.location) IN ({placeholders(len(locations))})")
            params.extend(location.lower() for location in locations)
        job_types = unique(query.job_types)
        if job_types:
            where.append(f"LOWER(jobs.job_type) IN ({placeholders(len(job_types))})")
            params.extend(job_type.lower() for job_type in job_types)
        if query.remote is not None:
            where.append("jobs.is_remote = ?")
            params.append(bool(query.remote))
        if query.min_score is not None:
            where.append("jobs.relevance_score >= ?")
            params.append(int(query.min_score))
        if query.max_score is not None:
            where.append("jobs.relevance_score <= ?")
            params.append(int(query.max_score))
        if query.min_salary is not None:
            where.append("COALESCE(jobs.max_amount, jobs.min_amount) >= ?")
            params.append(float(query.min_salary))
        if query.max_salary is not None:
            where.append("COALESCE(jobs.min_amount, jobs.max_amount) <= ?")
            params.append(float(query.max_salary))
        for column, start, end in (
            ("date_posted", query.date_posted_from, query.date_posted_to),
            ("first_seen", query.first_seen_from, query.first_seen_to),
            ("last_seen", query.last_seen_from, query.last_seen_to),
            ("status_changed_at", query.status_changed_from, query.status_changed_to),
        ):
            start_value = _date_value(start)
            end_value = _date_value(end)
            if start_value is not None:
                where.append(f"date(jobs.{column}) >= date(?)")
                params.append(start_value)
            if end_value is not None:
                where.append(f"date(jobs.{column}) <= date(?)")
                params.append(end_value)
        if query.has_attachments is not None:
            clause = "jobs.job_id IN (SELECT job_id FROM attachments)"
            where.append(clause if query.has_attachments else f"NOT {clause}")
        if query.without_labels:
            where.append("jobs.job_id NOT IN (SELECT job_id FROM job_labels)")
        if query.text:
            like = f"%{query.text.lower()}%"
            where.append(
                "(LOWER(jobs.title) LIKE ? OR LOWER(jobs.company) LIKE ? "
                "OR LOWER(jobs.location) LIKE ? "
                "OR LOWER(COALESCE(jobs.description, '')) LIKE ? "
                "OR jobs.job_id IN (SELECT job_id FROM notes WHERE LOWER(body) LIKE ? "
                "OR LOWER(COALESCE(title, '')) LIKE ?))"
            )
            params.extend([like] * 6)
        return (f"WHERE {' AND '.join(where)}" if where else ""), params

    @staticmethod
    def _order_sql(query: JobQuery) -> str:
        expression, natural = _ORDER_BY.get(query.sort, _ORDER_BY["score"])
        direction = (query.direction or natural).lower()
        direction = direction if direction in SORT_DIRECTIONS else natural
        tie = "jobs.relevance_score DESC, jobs.last_seen DESC, jobs.job_id ASC"
        return f"ORDER BY {expression} {direction.upper()}, {tie}"

    def query_jobs(self, query: JobQuery) -> tuple[list[Job], int]:
        """Filtered, sorted, paginated jobs plus the unpaginated total."""
        limit = max(1, min(int(query.limit), MAX_QUERY_LIMIT))
        offset = max(0, int(query.offset))
        where_sql, params = self._build_where(query)
        with self._connection() as conn:
            total = int(
                conn.execute(f"SELECT COUNT(*) FROM jobs {where_sql}", params).fetchone()[0]
            )
            rows = conn.execute(
                f"SELECT {JOB_SELECT} FROM jobs {where_sql} {self._order_sql(query)} "
                "LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [self.row_to_job(row) for row in rows], total

    def get_statistics(self) -> dict[str, Any]:
        today = date.today()
        active = f"status != '{_BLACKLISTED}'"
        with self._connection() as conn:
            by_status = {
                row["status"]: int(row["count"])
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
                ).fetchall()
            }
            total = int(conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {active}").fetchone()[0])
            new_today = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE first_seen = ? AND {active}", (today,)
                ).fetchone()[0]
            )
            seen_today = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE last_seen = ? AND {active}", (today,)
                ).fetchone()[0]
            )
            avg_score = conn.execute(
                f"SELECT AVG(relevance_score) FROM jobs WHERE {active}"
            ).fetchone()[0]
            attachments = int(conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0])
            notes = int(conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0])
        return {
            "total_jobs": total,
            "by_status": {status.value: by_status.get(status.value, 0) for status in JobStatus},
            "new_today": new_today,
            "seen_today": seen_today,
            "avg_relevance_score": round(float(avg_score or 0.0), 1),
            "blacklisted": by_status.get(_BLACKLISTED, 0),
            "attachments": attachments,
            "notes": notes,
        }

    def get_score_distribution(self, bin_size: int = 5) -> list[list[int]]:
        bin_size = max(1, int(bin_size))
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT (relevance_score / ?) * ? AS bin_start, COUNT(*) AS count "
                f"FROM jobs WHERE status != '{_BLACKLISTED}' GROUP BY bin_start ORDER BY bin_start",
                (bin_size, bin_size),
            ).fetchall()
        return [[int(row["bin_start"]), int(row["count"])] for row in rows]

    def get_facets(self, limit: int = 50, q: str | None = None) -> dict[str, list[dict[str, Any]]]:
        like = f"%{q.lower()}%" if q else None

        def facet(column: str, table: str = "jobs", extra: str = "") -> list[dict[str, Any]]:
            where = [f"{column} IS NOT NULL"]
            params: list[Any] = []
            if table == "jobs":
                where.append(f"status != '{_BLACKLISTED}'")
            if extra:
                where.append(extra)
            if like:
                where.append(f"LOWER({column}) LIKE ?")
                params.append(like)
            sql = (
                f"SELECT {column} AS value, COUNT(*) AS count FROM {table} "
                f"WHERE {' AND '.join(where)} GROUP BY {column} "
                f"ORDER BY count DESC, {column} ASC LIMIT ?"
            )
            with self._connection() as conn:
                rows = conn.execute(sql, [*params, max(1, int(limit))]).fetchall()
            return [{"value": row["value"], "count": int(row["count"])} for row in rows]

        return {
            "statuses": facet("status"),
            "sources": facet("source"),
            "companies": facet("company"),
            "locations": facet("location"),
            "job_types": facet("job_type"),
            "labels": facet("label", "job_labels"),
        }

    _ACTIVE_SOURCES = (
        "SELECT jobs.job_id AS job_id, jobs.company AS company, LOWER(jobs.source) AS source "
        f"FROM jobs WHERE jobs.status != '{_BLACKLISTED}' "
        "UNION "
        "SELECT jobs.job_id, jobs.company, LOWER(postings.source) FROM postings "
        f"JOIN jobs ON jobs.job_id = postings.job_id WHERE jobs.status != '{_BLACKLISTED}'"
    )

    def company_source_counts(self) -> dict[tuple[str, str], int]:
        """Active jobs per ``(company, source)`` for the sources view."""
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT company, source, COUNT(DISTINCT job_id) AS count FROM ({self._ACTIVE_SOURCES}) "
                "GROUP BY company, source"
            ).fetchall()
        return {(row["company"], row["source"]): int(row["count"]) for row in rows}

    def source_counts(self) -> dict[str, int]:
        """Active jobs per source, counting the job's own source and its postings."""
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT source, COUNT(DISTINCT job_id) AS count FROM ({self._ACTIVE_SOURCES}) "
                "GROUP BY source"
            ).fetchall()
        return {row["source"]: int(row["count"]) for row in rows}

    def company_status_counts(self, company: str) -> dict[str, int]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM jobs WHERE LOWER(company) = ? "
                "GROUP BY status",
                (company.lower(),),
            ).fetchall()
        return {row["status"]: int(row["count"]) for row in rows}
