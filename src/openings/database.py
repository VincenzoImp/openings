"""SQLite persistence for Openings.

The database owns every job and everything the user attaches to it. Only rows
in status ``new`` are ever removed automatically; every other status is
protected at the SQL level, so retention and reconciliation cannot touch a job
the user has acted on.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Iterable, Sequence

from openings.logger import get_logger
from openings.models import (
    PROTECTED_STATUSES,
    Attachment,
    AttachmentKind,
    BlacklistEntry,
    Event,
    EventKind,
    Job,
    JobStatus,
    Note,
    NoteKind,
    RunSummary,
    SourceRunStats,
)

if TYPE_CHECKING:
    from openings.config import Config


def _register_sqlite_date_handlers() -> None:
    """Explicit ISO 8601 adapters; the built-in ones are deprecated on 3.12+."""
    sqlite3.register_adapter(date, lambda value: value.isoformat())
    sqlite3.register_adapter(datetime, lambda value: value.isoformat())
    sqlite3.register_converter("date", lambda raw: date.fromisoformat(raw.decode()))
    sqlite3.register_converter("timestamp", lambda raw: datetime.fromisoformat(raw.decode()))


_register_sqlite_date_handlers()


JOB_COLUMNS = (
    "job_id",
    "title",
    "company",
    "location",
    "source",
    "external_id",
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
    "raw_json",
    "first_seen",
    "last_seen",
    "relevance_score",
    "status",
    "status_changed_at",
)
_JOB_SELECT = ", ".join(f"jobs.{column}" for column in JOB_COLUMNS)

PROTECTED_SQL = "status IN ({})".format(
    ",".join(f"'{status.value}'" for status in sorted(PROTECTED_STATUSES))
)
UNPROTECTED_SQL = f"status = '{JobStatus.NEW.value}'"

JOB_SORTS = ("score", "date", "company", "title", "salary", "first_seen", "updated")


@dataclass(frozen=True)
class JobQuery:
    """Filter and pagination parameters shared by the dashboard, REST and MCP."""

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
    text: str | None = None
    sort: str = "score"


@dataclass(frozen=True)
class BlacklistQuery:
    limit: int = 100
    offset: int = 0
    text: str | None = None
    company: str | None = None
    location: str | None = None


@dataclass
class UpsertResult:
    new_ids: list[str] = field(default_factory=list)
    updated_ids: list[str] = field(default_factory=list)
    skipped_blacklisted: int = 0

    @property
    def new_count(self) -> int:
        return len(self.new_ids)

    @property
    def updated_count(self) -> int:
        return len(self.updated_ids)


@dataclass
class ReconciliationReport:
    """Outcome of :meth:`JobDatabase.reconcile`."""

    deleted_below_score: int = 0
    deleted_stale: int = 0
    purged_blacklist: int = 0
    protected: int = 0

    @property
    def total_deleted(self) -> int:
        return self.deleted_below_score + self.deleted_stale + self.purged_blacklist

    def to_dict(self) -> dict[str, int]:
        return {
            "deleted_below_score": self.deleted_below_score,
            "deleted_stale": self.deleted_stale,
            "purged_blacklist": self.purged_blacklist,
            "protected": self.protected,
            "total_deleted": self.total_deleted,
        }


def _chunks(values: Sequence[Any], size: int) -> Generator[Sequence[Any], None, None]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _unique(values: Iterable[str] | None) -> list[str]:
    seen: dict[str, None] = {}
    for value in values or ():
        text = str(value).strip()
        if text:
            seen.setdefault(text, None)
    return list(seen)


class JobDatabase:
    """SQLite store for jobs, tracking state and run history."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT,
            job_url TEXT,
            description TEXT,
            date_posted DATE,
            job_type TEXT,
            is_remote BOOLEAN,
            job_level TEXT,
            min_amount REAL,
            max_amount REAL,
            currency TEXT,
            salary_interval TEXT,
            company_url TEXT,
            raw_json TEXT,
            first_seen DATE NOT NULL,
            last_seen DATE NOT NULL,
            relevance_score INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'new',
            status_changed_at TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(relevance_score);
        CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen);
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);

        CREATE TABLE IF NOT EXISTS job_labels (
            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            PRIMARY KEY (job_id, label)
        );
        CREATE INDEX IF NOT EXISTS idx_job_labels_label ON job_labels(label);

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            title TEXT,
            body TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_notes_job ON notes(job_id);

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            note TEXT,
            created_at TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_attachments_job ON attachments(job_id);

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            summary TEXT NOT NULL,
            data_json TEXT,
            created_at TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id, created_at);

        CREATE TABLE IF NOT EXISTS blacklist (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            blacklisted_at TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_blacklist_at ON blacklist(blacklisted_at);

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            total_found INTEGER NOT NULL DEFAULT 0,
            unique_found INTEGER NOT NULL DEFAULT 0,
            saved INTEGER NOT NULL DEFAULT 0,
            new_jobs INTEGER NOT NULL DEFAULT 0,
            notified INTEGER NOT NULL DEFAULT 0,
            success BOOLEAN NOT NULL DEFAULT 1,
            sources_json TEXT NOT NULL DEFAULT '[]',
            errors_json TEXT NOT NULL DEFAULT '[]'
        );
    """

    UPSERT_JOB = f"""
        INSERT INTO jobs ({", ".join(JOB_COLUMNS)})
        VALUES ({", ".join("?" for _ in JOB_COLUMNS)})
        ON CONFLICT(job_id) DO UPDATE SET
            last_seen = excluded.last_seen,
            relevance_score = excluded.relevance_score,
            source = COALESCE(jobs.source, excluded.source),
            external_id = COALESCE(excluded.external_id, jobs.external_id),
            job_url = COALESCE(excluded.job_url, jobs.job_url),
            description = COALESCE(excluded.description, jobs.description),
            date_posted = COALESCE(excluded.date_posted, jobs.date_posted),
            job_type = COALESCE(excluded.job_type, jobs.job_type),
            is_remote = COALESCE(excluded.is_remote, jobs.is_remote),
            job_level = COALESCE(excluded.job_level, jobs.job_level),
            min_amount = COALESCE(excluded.min_amount, jobs.min_amount),
            max_amount = COALESCE(excluded.max_amount, jobs.max_amount),
            currency = COALESCE(excluded.currency, jobs.currency),
            salary_interval = COALESCE(excluded.salary_interval, jobs.salary_interval),
            company_url = COALESCE(excluded.company_url, jobs.company_url),
            raw_json = COALESCE(excluded.raw_json, jobs.raw_json)
    """

    # SQLite's default variable cap is 999; stay well under it.
    SQLITE_VAR_LIMIT = 500
    # Largest page one query may return; callers page for the whole set.
    MAX_QUERY_LIMIT = 1000

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.logger = get_logger("database")
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.executescript(self.SCHEMA)
            conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    def __enter__(self) -> JobDatabase:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Serialized access to one persistent connection.

        FastAPI runs sync endpoints in a thread pool, so the connection must
        be shareable across threads; the re-entrant lock serializes use and
        WAL mode keeps readers from blocking the scheduler's writes.
        """
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    str(self.db_path),
                    detect_types=sqlite3.PARSE_DECLTYPES,
                    check_same_thread=False,
                )
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield self._conn
            except Exception:
                self._conn.rollback()
                raise

    # ------------------------------------------------------------------
    # Row mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        data = {key: row[key] for key in row.keys()}
        if data.get("is_remote") is not None:
            data["is_remote"] = bool(data["is_remote"])
        return Job.from_row(data)

    @staticmethod
    def _job_to_params(job: Job) -> tuple:
        return (
            job.job_id,
            job.title,
            job.company,
            job.location,
            job.source,
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
            job.first_seen,
            job.last_seen,
            job.relevance_score,
            job.status.value,
            job.status_changed_at or datetime.now(),
        )

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> Note:
        return Note(
            id=int(row["id"]),
            job_id=row["job_id"],
            kind=NoteKind(row["kind"]),
            title=row["title"],
            body=row["body"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_attachment(row: sqlite3.Row) -> Attachment:
        return Attachment(
            id=int(row["id"]),
            job_id=row["job_id"],
            kind=AttachmentKind(row["kind"]),
            filename=row["filename"],
            stored_name=row["stored_name"],
            sha256=row["sha256"],
            size_bytes=int(row["size_bytes"]),
            note=row["note"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        raw = row["data_json"]
        return Event(
            id=int(row["id"]),
            job_id=row["job_id"],
            kind=EventKind(row["kind"]),
            summary=row["summary"],
            data=json.loads(raw) if raw else None,
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunSummary:
        sources = [SourceRunStats(**item) for item in json.loads(row["sources_json"] or "[]")]
        return RunSummary(
            id=int(row["id"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            total_found=int(row["total_found"]),
            unique_found=int(row["unique_found"]),
            saved=int(row["saved"]),
            new_jobs=int(row["new_jobs"]),
            notified=int(row["notified"]),
            success=bool(row["success"]),
            sources=sources,
            errors=json.loads(row["errors_json"] or "[]"),
        )

    # ------------------------------------------------------------------
    # Jobs: write
    # ------------------------------------------------------------------

    def upsert_jobs(self, jobs: Iterable[Job]) -> UpsertResult:
        """Insert new jobs and refresh existing ones, never touching status.

        Blacklisted identities are skipped. New rows get an ``ingested``
        event so the timeline starts at first sight.
        """
        result = UpsertResult()
        pending: dict[str, Job] = {}
        for job in jobs:
            pending.setdefault(job.job_id, job)
        if not pending:
            return result

        ids = list(pending)
        blacklisted = self.blacklisted_ids(ids)
        result.skipped_blacklisted = len(blacklisted)
        ids = [job_id for job_id in ids if job_id not in blacklisted]
        if not ids:
            return result

        existing = self.existing_ids(ids)
        with self._connection() as conn:
            conn.executemany(
                self.UPSERT_JOB, [self._job_to_params(pending[job_id]) for job_id in ids]
            )
            now = datetime.now()
            events = [
                (
                    job_id,
                    EventKind.INGESTED.value,
                    f"First seen via {pending[job_id].source}",
                    json.dumps({"source": pending[job_id].source}),
                    now,
                )
                for job_id in ids
                if job_id not in existing
            ]
            if events:
                conn.executemany(
                    "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    events,
                )
            conn.commit()

        result.new_ids = [job_id for job_id in ids if job_id not in existing]
        result.updated_ids = [job_id for job_id in ids if job_id in existing]
        return result

    def existing_ids(self, job_ids: Sequence[str]) -> set[str]:
        found: set[str] = set()
        with self._connection() as conn:
            for chunk in _chunks(list(job_ids), self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders})", list(chunk)
                ).fetchall()
                found.update(row["job_id"] for row in rows)
        return found

    def set_status(
        self, job_ids: Sequence[str], status: JobStatus, *, note: str | None = None
    ) -> list[str]:
        """Move jobs to ``status`` and record an event for each change.

        Returns the ids whose status actually changed.
        """
        ids = _unique(job_ids)
        if not ids:
            return []
        now = datetime.now()
        changed: list[str] = []
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT job_id, status FROM jobs WHERE job_id IN ({placeholders})",
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
                    conn.execute(
                        "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            row["job_id"],
                            EventKind.STATUS.value,
                            summary,
                            json.dumps({"from": previous, "to": status.value}),
                            now,
                        ),
                    )
                    changed.append(row["job_id"])
            conn.commit()
        return changed

    def delete_jobs(self, job_ids: Sequence[str]) -> int:
        """Permanently delete jobs of any status without blacklisting them."""
        ids = _unique(job_ids)
        if not ids:
            return 0
        deleted = 0
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                cursor = conn.execute(
                    f"DELETE FROM jobs WHERE job_id IN ({placeholders})", list(chunk)
                )
                deleted += cursor.rowcount
            conn.commit()
        return deleted

    def rescore_all(self, config: Config) -> int:
        """Recompute every stored score against the current configuration."""
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
    # Jobs: read
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Job | None:
        with self._connection() as conn:
            row = conn.execute(
                f"SELECT {_JOB_SELECT} FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row) if row else None

    def get_jobs(self, job_ids: Sequence[str]) -> list[Job]:
        """Jobs in the order requested, skipping unknown ids."""
        ids = _unique(job_ids)
        if not ids:
            return []
        found: dict[str, Job] = {}
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT {_JOB_SELECT} FROM jobs WHERE job_id IN ({placeholders})",
                    list(chunk),
                ).fetchall()
                for row in rows:
                    job = self._row_to_job(row)
                    found[job.job_id] = job
        return [found[job_id] for job_id in ids if job_id in found]

    def iter_jobs(self) -> Generator[Job, None, None]:
        with self._connection() as conn:
            rows = conn.execute(f"SELECT {_JOB_SELECT} FROM jobs").fetchall()
        for row in rows:
            yield self._row_to_job(row)

    def count_jobs(self) -> int:
        with self._connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    def get_top_jobs(self, limit: int = 10, min_score: int = 0) -> list[Job]:
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT {_JOB_SELECT} FROM jobs WHERE relevance_score >= ? "
                "ORDER BY relevance_score DESC, last_seen DESC LIMIT ?",
                (min_score, max(1, int(limit))),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    @staticmethod
    def _date_value(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _build_where(self, query: JobQuery) -> tuple[str, list[Any]]:
        where: list[str] = []
        params: list[Any] = []

        statuses = _unique(query.statuses)
        if statuses:
            placeholders = ",".join("?" * len(statuses))
            where.append(f"jobs.status IN ({placeholders})")
            params.extend(status.lower() for status in statuses)
        sources = _unique(query.sources)
        if sources:
            placeholders = ",".join("?" * len(sources))
            where.append(f"LOWER(jobs.source) IN ({placeholders})")
            params.extend(source.lower() for source in sources)
        labels = _unique(query.labels)
        if labels:
            placeholders = ",".join("?" * len(labels))
            where.append(
                "jobs.job_id IN (SELECT job_id FROM job_labels "
                f"WHERE LOWER(label) IN ({placeholders}))"
            )
            params.extend(label.lower() for label in labels)
        if query.company:
            where.append("LOWER(jobs.company) LIKE ?")
            params.append(f"%{query.company.lower()}%")
        if query.location:
            where.append("LOWER(jobs.location) LIKE ?")
            params.append(f"%{query.location.lower()}%")
        locations = _unique(query.locations)
        if locations:
            placeholders = ",".join("?" * len(locations))
            where.append(f"LOWER(jobs.location) IN ({placeholders})")
            params.extend(location.lower() for location in locations)
        job_types = _unique(query.job_types)
        if job_types:
            placeholders = ",".join("?" * len(job_types))
            where.append(f"LOWER(jobs.job_type) IN ({placeholders})")
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
        ):
            start_value = self._date_value(start)
            end_value = self._date_value(end)
            if start_value is not None:
                where.append(f"date(jobs.{column}) >= date(?)")
                params.append(start_value)
            if end_value is not None:
                where.append(f"date(jobs.{column}) <= date(?)")
                params.append(end_value)
        if query.text:
            like = f"%{query.text.lower()}%"
            where.append(
                "(LOWER(jobs.title) LIKE ? OR LOWER(jobs.company) LIKE ? "
                "OR LOWER(jobs.location) LIKE ? "
                "OR LOWER(COALESCE(jobs.description, '')) LIKE ?)"
            )
            params.extend([like, like, like, like])
        return (f"WHERE {' AND '.join(where)}" if where else ""), params

    def query_jobs(self, query: JobQuery) -> tuple[list[Job], int]:
        """Filtered, sorted, paginated jobs plus the unpaginated total."""
        limit = max(1, min(int(query.limit), self.MAX_QUERY_LIMIT))
        offset = max(0, int(query.offset))
        where_sql, params = self._build_where(query)
        order_sql = {
            "score": "ORDER BY jobs.relevance_score DESC, jobs.last_seen DESC",
            "date": (
                "ORDER BY COALESCE(jobs.date_posted, jobs.first_seen) DESC, "
                "jobs.relevance_score DESC"
            ),
            "first_seen": "ORDER BY jobs.first_seen DESC, jobs.relevance_score DESC",
            "updated": "ORDER BY jobs.status_changed_at DESC, jobs.relevance_score DESC",
            "company": (
                "ORDER BY LOWER(jobs.company) ASC, jobs.relevance_score DESC, jobs.last_seen DESC"
            ),
            "title": (
                "ORDER BY LOWER(jobs.title) ASC, jobs.relevance_score DESC, jobs.last_seen DESC"
            ),
            "salary": (
                "ORDER BY COALESCE(jobs.max_amount, jobs.min_amount, 0) DESC, "
                "COALESCE(jobs.min_amount, jobs.max_amount, 0) DESC, "
                "jobs.relevance_score DESC"
            ),
        }.get(query.sort, "ORDER BY jobs.relevance_score DESC, jobs.last_seen DESC")
        with self._connection() as conn:
            total = int(
                conn.execute(f"SELECT COUNT(*) FROM jobs {where_sql}", params).fetchone()[0]
            )
            rows = conn.execute(
                f"SELECT {_JOB_SELECT} FROM jobs {where_sql} {order_sql} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [self._row_to_job(row) for row in rows], total

    def get_statistics(self) -> dict[str, Any]:
        today = date.today()
        with self._connection() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            by_status = {
                row["status"]: int(row["count"])
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
                ).fetchall()
            }
            new_today = int(
                conn.execute("SELECT COUNT(*) FROM jobs WHERE first_seen = ?", (today,)).fetchone()[
                    0
                ]
            )
            seen_today = int(
                conn.execute("SELECT COUNT(*) FROM jobs WHERE last_seen = ?", (today,)).fetchone()[
                    0
                ]
            )
            avg_score = conn.execute("SELECT AVG(relevance_score) FROM jobs").fetchone()[0]
            blacklisted = int(conn.execute("SELECT COUNT(*) FROM blacklist").fetchone()[0])
        return {
            "total_jobs": total,
            "by_status": {status.value: by_status.get(status.value, 0) for status in JobStatus},
            "new_today": new_today,
            "seen_today": seen_today,
            "avg_relevance_score": round(float(avg_score or 0.0), 1),
            "blacklisted": blacklisted,
        }

    def get_score_distribution(self, bin_size: int = 5) -> list[list[int]]:
        bin_size = max(1, int(bin_size))
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT (relevance_score / ?) * ? AS bin_start, COUNT(*) AS count "
                "FROM jobs GROUP BY bin_start ORDER BY bin_start",
                (bin_size, bin_size),
            ).fetchall()
        return [[int(row["bin_start"]), int(row["count"])] for row in rows]

    def get_facets(self, limit: int = 50) -> dict[str, list[dict[str, Any]]]:
        def facet(sql: str) -> list[dict[str, Any]]:
            with self._connection() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
            return [{"value": row[0], "count": int(row[1])} for row in rows if row[0] is not None]

        return {
            "statuses": facet(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY COUNT(*) DESC LIMIT ?"
            ),
            "sources": facet(
                "SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC LIMIT ?"
            ),
            "companies": facet(
                "SELECT company, COUNT(*) FROM jobs GROUP BY company "
                "ORDER BY COUNT(*) DESC, company ASC LIMIT ?"
            ),
            "locations": facet(
                "SELECT location, COUNT(*) FROM jobs GROUP BY location "
                "ORDER BY COUNT(*) DESC, location ASC LIMIT ?"
            ),
            "job_types": facet(
                "SELECT job_type, COUNT(*) FROM jobs WHERE job_type IS NOT NULL "
                "GROUP BY job_type ORDER BY COUNT(*) DESC LIMIT ?"
            ),
            "labels": facet(
                "SELECT label, COUNT(*) FROM job_labels GROUP BY label "
                "ORDER BY COUNT(*) DESC, label ASC LIMIT ?"
            ),
        }

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def get_labels(self, job_id: str) -> list[str]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT label FROM job_labels WHERE job_id = ? ORDER BY label", (job_id,)
            ).fetchall()
        return [row["label"] for row in rows]

    def get_labels_for(self, job_ids: Sequence[str]) -> dict[str, list[str]]:
        ids = _unique(job_ids)
        result: dict[str, list[str]] = {job_id: [] for job_id in ids}
        if not ids:
            return result
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT job_id, label FROM job_labels WHERE job_id IN ({placeholders}) "
                    "ORDER BY label",
                    list(chunk),
                ).fetchall()
                for row in rows:
                    result[row["job_id"]].append(row["label"])
        return result

    def add_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> int:
        existing = self.existing_ids(_unique(job_ids))
        ids = [job_id for job_id in _unique(job_ids) if job_id in existing]
        clean_labels = [label.strip() for label in _unique(labels)]
        if not ids or not clean_labels:
            return 0
        now = datetime.now()
        added = 0
        with self._connection() as conn:
            for job_id in ids:
                for label in clean_labels:
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO job_labels (job_id, label) VALUES (?, ?)",
                        (job_id, label),
                    )
                    if cursor.rowcount:
                        added += 1
                        conn.execute(
                            "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (
                                job_id,
                                EventKind.LABEL.value,
                                f"Label added: {label}",
                                json.dumps({"label": label, "action": "add"}),
                                now,
                            ),
                        )
            conn.commit()
        return added

    def remove_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> int:
        ids = _unique(job_ids)
        clean_labels = _unique(labels)
        if not ids or not clean_labels:
            return 0
        now = datetime.now()
        removed = 0
        with self._connection() as conn:
            for job_id in ids:
                for label in clean_labels:
                    cursor = conn.execute(
                        "DELETE FROM job_labels WHERE job_id = ? AND label = ?",
                        (job_id, label),
                    )
                    if cursor.rowcount:
                        removed += 1
                        conn.execute(
                            "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (
                                job_id,
                                EventKind.LABEL.value,
                                f"Label removed: {label}",
                                json.dumps({"label": label, "action": "remove"}),
                                now,
                            ),
                        )
            conn.commit()
        return removed

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def add_note(
        self, job_id: str, kind: NoteKind, body: str, *, title: str | None = None
    ) -> Note | None:
        if self.get_job(job_id) is None:
            return None
        now = datetime.now()
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO notes (job_id, kind, title, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, kind.value, title, body, now),
            )
            note_id = int(cursor.lastrowid or 0)
            label = title or body.strip().splitlines()[0][:80] if body.strip() else kind.value
            conn.execute(
                "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    job_id,
                    EventKind.NOTE.value,
                    f"{'Q&A' if kind is NoteKind.QA else 'Note'} added: {label}",
                    json.dumps({"note_id": note_id, "kind": kind.value}),
                    now,
                ),
            )
            conn.commit()
        return Note(id=note_id, job_id=job_id, kind=kind, title=title, body=body, created_at=now)

    def list_notes(self, job_id: str) -> list[Note]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, job_id, kind, title, body, created_at FROM notes "
                "WHERE job_id = ? ORDER BY created_at ASC, id ASC",
                (job_id,),
            ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def delete_note(self, job_id: str, note_id: int) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM notes WHERE job_id = ? AND id = ?", (job_id, note_id)
            )
            conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Attachments (metadata only; bytes live on disk)
    # ------------------------------------------------------------------

    def add_attachment(
        self,
        job_id: str,
        *,
        kind: AttachmentKind,
        filename: str,
        stored_name: str,
        sha256: str,
        size_bytes: int,
        note: str | None = None,
    ) -> Attachment | None:
        if self.get_job(job_id) is None:
            return None
        now = datetime.now()
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO attachments (job_id, kind, filename, stored_name, sha256, "
                "size_bytes, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, kind.value, filename, stored_name, sha256, size_bytes, note, now),
            )
            attachment_id = int(cursor.lastrowid or 0)
            conn.execute(
                "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    job_id,
                    EventKind.ATTACHMENT.value,
                    f"Attachment added ({kind.value}): {filename}",
                    json.dumps({"attachment_id": attachment_id, "kind": kind.value}),
                    now,
                ),
            )
            conn.commit()
        return Attachment(
            id=attachment_id,
            job_id=job_id,
            kind=kind,
            filename=filename,
            stored_name=stored_name,
            sha256=sha256,
            size_bytes=size_bytes,
            note=note,
            created_at=now,
        )

    def list_attachments(self, job_id: str) -> list[Attachment]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM attachments WHERE job_id = ? ORDER BY created_at ASC, id ASC",
                (job_id,),
            ).fetchall()
        return [self._row_to_attachment(row) for row in rows]

    def get_attachment(self, job_id: str, attachment_id: int) -> Attachment | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM attachments WHERE job_id = ? AND id = ?",
                (job_id, attachment_id),
            ).fetchone()
        return self._row_to_attachment(row) if row else None

    def delete_attachment(self, job_id: str, attachment_id: int) -> Attachment | None:
        attachment = self.get_attachment(job_id, attachment_id)
        if attachment is None:
            return None
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM attachments WHERE job_id = ? AND id = ?", (job_id, attachment_id)
            )
            conn.execute(
                "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    job_id,
                    EventKind.ATTACHMENT.value,
                    f"Attachment removed: {attachment.filename}",
                    json.dumps({"attachment_id": attachment_id}),
                    datetime.now(),
                ),
            )
            conn.commit()
        return attachment

    def all_attachments(self) -> list[Attachment]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM attachments").fetchall()
        return [self._row_to_attachment(row) for row in rows]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def list_events(self, job_id: str) -> list[Event]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE job_id = ? ORDER BY created_at ASC, id ASC",
                (job_id,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    # ------------------------------------------------------------------
    # Blacklist
    # ------------------------------------------------------------------

    def blacklisted_ids(self, job_ids: Sequence[str]) -> set[str]:
        ids = _unique(job_ids)
        found: set[str] = set()
        if not ids:
            return found
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT job_id FROM blacklist WHERE job_id IN ({placeholders})",
                    list(chunk),
                ).fetchall()
                found.update(row["job_id"] for row in rows)
        return found

    def blacklist_jobs(self, job_ids: Sequence[str]) -> int:
        """Suppress jobs from future ingestion and delete their rows."""
        ids = _unique(job_ids)
        if not ids:
            return 0
        now = datetime.now()
        affected = 0
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO blacklist (job_id, title, company, location, blacklisted_at) "
                    f"SELECT job_id, title, company, location, ? FROM jobs WHERE job_id IN ({placeholders})",
                    [now, *chunk],
                )
                affected += cursor.rowcount
                conn.execute(f"DELETE FROM jobs WHERE job_id IN ({placeholders})", list(chunk))
            conn.commit()
        return affected

    def blacklist_identities(self, entries: Iterable[BlacklistEntry]) -> int:
        """Add blacklist entries directly (identities that need not be active)."""
        rows = [
            (entry.job_id, entry.title, entry.company, entry.location, entry.blacklisted_at)
            for entry in entries
        ]
        if not rows:
            return 0
        with self._connection() as conn:
            cursor = conn.executemany(
                "INSERT OR IGNORE INTO blacklist (job_id, title, company, location, blacklisted_at) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        return cursor.rowcount if cursor.rowcount >= 0 else len(rows)

    def unblacklist_jobs(self, job_ids: Sequence[str]) -> int:
        ids = _unique(job_ids)
        if not ids:
            return 0
        removed = 0
        with self._connection() as conn:
            for chunk in _chunks(ids, self.SQLITE_VAR_LIMIT):
                placeholders = ",".join("?" * len(chunk))
                cursor = conn.execute(
                    f"DELETE FROM blacklist WHERE job_id IN ({placeholders})", list(chunk)
                )
                removed += cursor.rowcount
            conn.commit()
        return removed

    def list_blacklist(self, query: BlacklistQuery) -> tuple[list[BlacklistEntry], int]:
        limit = max(1, min(int(query.limit), self.MAX_QUERY_LIMIT))
        offset = max(0, int(query.offset))
        where: list[str] = []
        params: list[Any] = []
        if query.text:
            like = f"%{query.text.lower()}%"
            where.append(
                "(LOWER(job_id) LIKE ? OR LOWER(title) LIKE ? OR LOWER(company) LIKE ? "
                "OR LOWER(location) LIKE ?)"
            )
            params.extend([like, like, like, like])
        if query.company:
            where.append("LOWER(company) LIKE ?")
            params.append(f"%{query.company.lower()}%")
        if query.location:
            where.append("LOWER(location) LIKE ?")
            params.append(f"%{query.location.lower()}%")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connection() as conn:
            total = int(
                conn.execute(f"SELECT COUNT(*) FROM blacklist {where_sql}", params).fetchone()[0]
            )
            rows = conn.execute(
                f"SELECT * FROM blacklist {where_sql} "
                "ORDER BY blacklisted_at DESC, LOWER(title) ASC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        entries = [
            BlacklistEntry(
                job_id=row["job_id"],
                title=row["title"],
                company=row["company"],
                location=row["location"],
                blacklisted_at=row["blacklisted_at"],
            )
            for row in rows
        ]
        return entries, total

    def count_blacklist_older_than(self, days: int) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        with self._connection() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM blacklist WHERE blacklisted_at < ?", (cutoff,)
                ).fetchone()[0]
            )

    def purge_blacklist(self, older_than_days: int | None = None) -> int:
        with self._connection() as conn:
            if older_than_days is None:
                cursor = conn.execute("DELETE FROM blacklist")
            else:
                cutoff = datetime.now() - timedelta(days=older_than_days)
                cursor = conn.execute("DELETE FROM blacklist WHERE blacklisted_at < ?", (cutoff,))
            conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Retention (only `new` rows are ever touched)
    # ------------------------------------------------------------------

    def count_below_score(self, score: int) -> int:
        with self._connection() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE relevance_score < ? AND {UNPROTECTED_SQL}",
                    (score,),
                ).fetchone()[0]
            )

    def delete_below_score(self, score: int) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM jobs WHERE relevance_score < ? AND {UNPROTECTED_SQL}", (score,)
            )
            conn.commit()
        return cursor.rowcount

    def count_stale(self, days: int) -> int:
        cutoff = date.today() - timedelta(days=days)
        with self._connection() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE last_seen < ? AND {UNPROTECTED_SQL}",
                    (cutoff,),
                ).fetchone()[0]
            )

    def delete_stale(self, days: int) -> int:
        cutoff = date.today() - timedelta(days=days)
        with self._connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM jobs WHERE last_seen < ? AND {UNPROTECTED_SQL}", (cutoff,)
            )
            conn.commit()
        return cursor.rowcount

    def count_protected(self) -> int:
        with self._connection() as conn:
            return int(
                conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {PROTECTED_SQL}").fetchone()[0]
            )

    def preview_reconcile(self, config: Config) -> ReconciliationReport:
        return ReconciliationReport(
            deleted_below_score=self.count_below_score(config.scoring.save_threshold),
            deleted_stale=self.count_stale(config.retention.max_age_days),
            purged_blacklist=self.count_blacklist_older_than(
                config.retention.purge_blacklist_after_days
            ),
            protected=self.count_protected(),
        )

    def reconcile(self, config: Config) -> ReconciliationReport:
        """Apply the configured save threshold and retention. Idempotent."""
        report = ReconciliationReport(protected=self.count_protected())
        report.deleted_below_score = self.delete_below_score(config.scoring.save_threshold)
        report.deleted_stale = self.delete_stale(config.retention.max_age_days)
        report.purged_blacklist = self.purge_blacklist(config.retention.purge_blacklist_after_days)
        return report

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def record_run(self, summary: RunSummary) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (started_at, finished_at, total_found, unique_found, saved, "
                "new_jobs, notified, success, sources_json, errors_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    summary.started_at,
                    summary.finished_at,
                    summary.total_found,
                    summary.unique_found,
                    summary.saved,
                    summary.new_jobs,
                    summary.notified,
                    summary.success,
                    json.dumps([source.to_dict() for source in summary.sources]),
                    json.dumps(list(summary.errors)),
                ),
            )
            conn.commit()
        summary.id = int(cursor.lastrowid or 0)
        return summary.id

    def list_runs(self, limit: int = 20) -> list[RunSummary]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC, id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    # ------------------------------------------------------------------
    # Escape hatch
    # ------------------------------------------------------------------

    def reset_all(self) -> None:
        """Delete everything, including protected jobs and the blacklist."""
        with self._connection() as conn:
            for table in (
                "events",
                "attachments",
                "notes",
                "job_labels",
                "jobs",
                "blacklist",
                "runs",
            ):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()


_database: JobDatabase | None = None
_database_lock = threading.Lock()


def get_database(config: Config) -> JobDatabase:
    """Return the process-wide database for ``config.database_path``."""
    global _database
    with _database_lock:
        if _database is None or _database.db_path != config.database_path:
            if _database is not None:
                _database.close()
            _database = JobDatabase(config.database_path)
        return _database


def close_database() -> None:
    global _database
    with _database_lock:
        if _database is not None:
            _database.close()
            _database = None
