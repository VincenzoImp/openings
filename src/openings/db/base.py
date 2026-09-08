"""Connection handling, row mapping and small helpers shared by the stores."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Generator, Iterable, Sequence

from openings.logger import get_logger
from openings.models import (
    Attachment,
    AttachmentKind,
    Event,
    EventKind,
    Job,
    Note,
    NoteKind,
    Posting,
    RunSummary,
    SourceRunStats,
    parse_datetime,
    utcnow,
)


def _register_sqlite_handlers() -> None:
    """ISO 8601 in, aware datetimes out. The built-in adapters are deprecated."""
    sqlite3.register_adapter(date, lambda value: value.isoformat())
    sqlite3.register_adapter(datetime, lambda value: value.isoformat())
    sqlite3.register_converter("date", lambda raw: date.fromisoformat(raw.decode()))
    sqlite3.register_converter("timestamp", lambda raw: parse_datetime(raw.decode()))


_register_sqlite_handlers()

# SQLite's default variable cap is 999; stay well under it.
SQLITE_VAR_LIMIT = 500
# Largest page one query may return; callers page for the whole set.
MAX_QUERY_LIMIT = 1000

JOB_COLUMNS = (
    "job_id",
    "identity",
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

JOB_SELECT = ", ".join(f"jobs.{column}" for column in JOB_COLUMNS) + (
    ", (SELECT COUNT(*) FROM postings WHERE postings.job_id = jobs.job_id) AS postings_count"
    ", (SELECT COUNT(*) FROM notes WHERE notes.job_id = jobs.job_id) AS notes_count"
    ", (SELECT COUNT(*) FROM attachments WHERE attachments.job_id = jobs.job_id)"
    " AS attachments_count"
)


def chunks(
    values: Sequence[Any], size: int = SQLITE_VAR_LIMIT
) -> Generator[Sequence[Any], None, None]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def unique(values: Iterable[str] | None) -> list[str]:
    seen: dict[str, None] = {}
    for value in values or ():
        text = str(value).strip()
        if text:
            seen.setdefault(text, None)
    return list(seen)


def placeholders(count: int) -> str:
    return ",".join("?" * count)


class Store:
    """One serialized SQLite connection shared by every mixin."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.logger = get_logger("database")
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    def __enter__(self) -> Store:
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
                self._conn.execute("PRAGMA busy_timeout=5000")
            try:
                yield self._conn
            except Exception:
                self._conn.rollback()
                raise

    # ------------------------------------------------------------------
    # Row mapping
    # ------------------------------------------------------------------

    @staticmethod
    def row_to_job(row: sqlite3.Row) -> Job:
        data = {key: row[key] for key in row.keys()}
        if data.get("is_remote") is not None:
            data["is_remote"] = bool(data["is_remote"])
        return Job.from_row(data)

    @staticmethod
    def row_to_posting(row: sqlite3.Row) -> Posting:
        return Posting(
            id=int(row["id"]),
            job_id=row["job_id"],
            key=row["key"],
            source=row["source"],
            external_id=row["external_id"],
            url=row["url"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
        )

    @staticmethod
    def row_to_note(row: sqlite3.Row) -> Note:
        return Note(
            id=int(row["id"]),
            job_id=row["job_id"],
            kind=NoteKind(row["kind"]),
            title=row["title"],
            body=row["body"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def row_to_attachment(row: sqlite3.Row) -> Attachment:
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
    def row_to_event(row: sqlite3.Row) -> Event:
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
    def row_to_run(row: sqlite3.Row) -> RunSummary:
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

    @staticmethod
    def job_params(job: Job) -> tuple:
        return (
            job.job_id,
            job.identity,
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
            job.status_changed_at or utcnow(),
        )

    # ------------------------------------------------------------------
    # Events (used by every store)
    # ------------------------------------------------------------------

    @staticmethod
    def _insert_event(
        conn: sqlite3.Connection,
        job_id: str,
        kind: EventKind,
        summary: str,
        data: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> int:
        cursor = conn.execute(
            "INSERT INTO events (job_id, kind, summary, data_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_id, kind.value, summary, json.dumps(data) if data else None, at or utcnow()),
        )
        return int(cursor.lastrowid or 0)
