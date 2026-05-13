"""
SQLite database for job persistence and tracking.

Stores job history to identify new jobs between search runs
and track application status.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pandas as pd

if TYPE_CHECKING:
    from job_search_tool.config import Config

from job_search_tool.logger import get_logger
from job_search_tool.models import (
    BlacklistedJobRecord,
    Job,
    JobDBRecord,
    generate_job_id,
)
from job_search_tool.scoring import calculate_relevance_score

_JOB_FIELD_NAMES = (
    "job_id",
    "title",
    "company",
    "location",
    "job_url",
    "site",
    "job_type",
    "is_remote",
    "job_level",
    "description",
    "date_posted",
    "min_amount",
    "max_amount",
    "currency",
    "company_url",
    "first_seen",
    "last_seen",
    "relevance_score",
    "applied",
    "bookmarked",
)
_JOB_COLUMNS = ", ".join(_JOB_FIELD_NAMES)

_DELETED_JOB_FIELD_NAMES = (
    "job_id",
    "title",
    "company",
    "location",
    "blacklisted_at",
)
_DELETED_JOB_COLUMNS = ", ".join(_DELETED_JOB_FIELD_NAMES)


@dataclass
class ReconciliationReport:
    """Outcome of ``JobDatabase.reconcile_with_config``."""

    deleted_below_score: int = 0
    deleted_stale: int = 0
    purged_blacklist: int = 0
    protected_bookmarked: int = 0
    protected_applied: int = 0

    @property
    def total_deleted(self) -> int:
        return self.deleted_below_score + self.deleted_stale + self.purged_blacklist


class JobDatabase:
    """
    SQLite database manager for job persistence.

    Provides methods to save jobs, identify new jobs, and track application status.
    """

    # SQL statements
    CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            job_url TEXT,
            site TEXT,
            job_type TEXT,
            is_remote BOOLEAN,
            job_level TEXT,
            description TEXT,
            date_posted DATE,
            min_amount REAL,
            max_amount REAL,
            currency TEXT,
            company_url TEXT,
            first_seen DATE NOT NULL,
            last_seen DATE NOT NULL,
            relevance_score INTEGER DEFAULT 0,
            applied BOOLEAN DEFAULT FALSE,
            bookmarked BOOLEAN DEFAULT FALSE
        )
    """

    CREATE_INDEX = """
        CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen)
    """

    CREATE_SCORE_INDEX = """
        CREATE INDEX IF NOT EXISTS idx_jobs_relevance_score
        ON jobs(relevance_score)
    """

    CREATE_DELETED_TABLE = """
        CREATE TABLE IF NOT EXISTS deleted_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            blacklisted_at TEXT NOT NULL
        )
    """

    CREATE_DELETED_INDEX = """
        CREATE INDEX IF NOT EXISTS idx_deleted_jobs_blacklisted_at
        ON deleted_jobs(blacklisted_at)
    """

    INSERT_OR_UPDATE = """
        INSERT INTO jobs (job_id, title, company, location, job_url,
                          site, job_type, is_remote, job_level, description,
                          date_posted, min_amount, max_amount, currency, company_url,
                          first_seen, last_seen, relevance_score, applied, bookmarked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            last_seen = excluded.last_seen,
            relevance_score = CASE
                WHEN excluded.relevance_score > jobs.relevance_score
                THEN excluded.relevance_score
                ELSE jobs.relevance_score
            END,
            site = COALESCE(excluded.site, jobs.site),
            job_type = COALESCE(excluded.job_type, jobs.job_type),
            is_remote = COALESCE(excluded.is_remote, jobs.is_remote),
            job_level = COALESCE(excluded.job_level, jobs.job_level),
            description = COALESCE(excluded.description, jobs.description),
            date_posted = COALESCE(excluded.date_posted, jobs.date_posted),
            min_amount = COALESCE(excluded.min_amount, jobs.min_amount),
            max_amount = COALESCE(excluded.max_amount, jobs.max_amount),
            currency = COALESCE(excluded.currency, jobs.currency),
            company_url = COALESCE(excluded.company_url, jobs.company_url)
    """

    SELECT_BY_ID = "SELECT job_id FROM jobs WHERE job_id = ?"

    SELECT_ALL = f"""
        SELECT {_JOB_COLUMNS}
        FROM jobs
        ORDER BY last_seen DESC, relevance_score DESC
    """

    SELECT_NEW = f"""
        SELECT {_JOB_COLUMNS}
        FROM jobs
        WHERE first_seen = ?
        ORDER BY relevance_score DESC
    """

    MARK_APPLIED = "UPDATE jobs SET applied = TRUE WHERE job_id = ?"
    MARK_UNAPPLIED = "UPDATE jobs SET applied = FALSE WHERE job_id = ?"

    def __init__(self, db_path: Path):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self.logger = get_logger("database")
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the current database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Enable WAL mode for better concurrency (readers don't block writers)
            cursor.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout to avoid immediate failures on concurrent access
            cursor.execute("PRAGMA busy_timeout=5000")

            cursor.execute(self.CREATE_TABLE)
            cursor.execute(self.CREATE_DELETED_TABLE)
            self._validate_current_schema(cursor)

            cursor.execute(self.CREATE_INDEX)
            cursor.execute(self.CREATE_SCORE_INDEX)
            cursor.execute(self.CREATE_DELETED_INDEX)

            conn.commit()

    def close(self) -> None:
        """Close the persistent database connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # SQLite has a limit of 999 variables per query (SQLITE_MAX_VARIABLE_NUMBER)
    # We use a conservative chunk size to stay well under this limit
    SQLITE_VAR_LIMIT = 500

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get database connection with context manager.

        Uses a persistent connection for better performance. The connection
        is reused across calls and only created once.

        Yields:
            SQLite connection.
        """
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    self.db_path,
                    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                    check_same_thread=False,
                )
                self._conn.row_factory = sqlite3.Row
            try:
                yield self._conn
            except sqlite3.Error:
                # Discard the connection so next call gets a fresh one.
                self.close()
                raise

    def _batch_query_existing_ids(self, job_ids: list[str]) -> set[str]:
        """
        Query existing job IDs in batches to avoid SQLite variable limit.

        SQLite has a limit of 999 variables per query. This method chunks
        the input list to stay under that limit.

        Args:
            job_ids: List of job IDs to check.

        Returns:
            Set of job IDs that exist in the database.
        """
        if not job_ids:
            return set()

        existing_ids: set[str] = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(job_ids), self.SQLITE_VAR_LIMIT):
                chunk = job_ids[i : i + self.SQLITE_VAR_LIMIT]
                placeholders = ",".join("?" * len(chunk))
                query = f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders})"
                cursor.execute(query, chunk)
                existing_ids.update(row[0] for row in cursor.fetchall())

        return existing_ids

    @staticmethod
    def _table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
        """Return column names for a table."""
        table_info_queries = {
            "jobs": "PRAGMA table_info(jobs)",
            "deleted_jobs": "PRAGMA table_info(deleted_jobs)",
        }
        cursor.execute(table_info_queries[table_name])
        return {str(row[1]) for row in cursor.fetchall()}

    @classmethod
    def _validate_table_columns(
        cls,
        cursor: sqlite3.Cursor,
        table_name: str,
        required_columns: tuple[str, ...],
    ) -> None:
        actual_columns = cls._table_columns(cursor, table_name)
        missing_columns = [
            column for column in required_columns if column not in actual_columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise RuntimeError(
                "Database does not match the current database schema: "
                f"table '{table_name}' is missing required columns: {missing}. "
                "Start with a fresh database or restore a current-format backup."
            )

    @classmethod
    def _validate_current_schema(cls, cursor: sqlite3.Cursor) -> None:
        """Verify that existing tables match the current runtime schema."""
        cls._validate_table_columns(cursor, "jobs", _JOB_FIELD_NAMES)
        cls._validate_table_columns(
            cursor,
            "deleted_jobs",
            _DELETED_JOB_FIELD_NAMES,
        )

    def _batch_query_blacklisted_ids(self, job_ids: list[str]) -> set[str]:
        """
        Query blacklisted job IDs in batches to avoid SQLite variable limits.

        Args:
            job_ids: List of job IDs to check.

        Returns:
            Set of job IDs that are currently blacklisted.
        """
        if not job_ids:
            return set()

        blacklisted_ids: set[str] = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(job_ids), self.SQLITE_VAR_LIMIT):
                chunk = job_ids[i : i + self.SQLITE_VAR_LIMIT]
                placeholders = ",".join("?" * len(chunk))
                query = (
                    f"SELECT job_id FROM deleted_jobs WHERE job_id IN ({placeholders})"
                )
                cursor.execute(query, chunk)
                blacklisted_ids.update(row[0] for row in cursor.fetchall())

        return blacklisted_ids

    def _add_job_ids_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of *df* with a computed ``job_id`` column."""
        df_with_ids = df.copy()
        df_with_ids["job_id"] = df_with_ids.apply(
            lambda row: generate_job_id(
                str(row.get("title", "")),
                str(row.get("company", "")),
                str(row.get("location", "")),
            ),
            axis=1,
        )
        return df_with_ids

    @staticmethod
    def _date_filter_value(value: date | datetime | str | None) -> str | None:
        """Return an ISO-ish date string suitable for SQLite date comparisons."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _unique_non_empty(values: list[str] | tuple[str, ...] | None) -> list[str]:
        """Return deduplicated, truthy string values while preserving order."""
        if not values:
            return []
        return list(dict.fromkeys(value for value in values if value))

    def job_exists(self, job_id: str) -> bool:
        """
        Check if job exists in database.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if job exists, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.SELECT_BY_ID, (job_id,))
            return cursor.fetchone() is not None

    def is_job_blacklisted(self, job_id: str) -> bool:
        """
        Check whether a job ID is present in the deleted-job blacklist.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if blacklisted, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT job_id FROM deleted_jobs WHERE job_id = ?",
                (job_id,),
            )
            return cursor.fetchone() is not None

    def get_blacklisted_job_ids(self, job_ids: list[str] | None = None) -> set[str]:
        """
        Return blacklisted job IDs.

        Args:
            job_ids: Optional subset of IDs to check. If omitted, returns all.

        Returns:
            Set of blacklisted job IDs.
        """
        if job_ids is not None:
            return self._batch_query_blacklisted_ids(job_ids)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM deleted_jobs")
            return {row[0] for row in cursor.fetchall()}

    def save_job(
        self,
        job: Job,
        site: str | None = None,
        job_level: str | None = None,
        company_url: str | None = None,
    ) -> bool:
        """
        Save or update a job in the database.

        Args:
            job: Job to save.
            site: Job board source (indeed, linkedin, etc.).
            job_level: Seniority level (from LinkedIn).
            company_url: Company page URL.

        Returns:
            True if job is new, False if updated.
        """
        if self.is_job_blacklisted(job.job_id):
            self.logger.info("Skipping blacklisted job: %s", job.job_id)
            return False

        today = date.today()
        is_new = not self.job_exists(job.job_id)

        # Convert date_posted to string for SQLite
        date_posted_str = None
        if job.date_posted:
            date_posted_str = (
                job.date_posted.isoformat()
                if hasattr(job.date_posted, "isoformat")
                else str(job.date_posted)
            )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self.INSERT_OR_UPDATE,
                (
                    job.job_id,
                    job.title,
                    job.company,
                    job.location,
                    job.job_url,
                    site,
                    job.job_type,
                    job.is_remote,
                    job_level,
                    job.description,
                    date_posted_str,
                    job.min_amount,
                    job.max_amount,
                    job.currency,
                    company_url,
                    today,
                    today,
                    job.relevance_score,
                    False,
                    False,
                ),
            )
            conn.commit()

        return is_new

    def save_jobs(self, jobs: list[Job]) -> tuple[int, int]:
        """
        Save multiple jobs to database.

        Args:
            jobs: List of jobs to save.

        Returns:
            Tuple of (new_count, updated_count).
        """
        new_count = 0
        updated_count = 0

        for job in jobs:
            if self.is_job_blacklisted(job.job_id):
                continue
            if self.save_job(job):
                new_count += 1
            else:
                updated_count += 1

        return new_count, updated_count

    def save_jobs_from_dataframe(self, df: pd.DataFrame) -> tuple[int, int]:
        """
        Save jobs from DataFrame to database using batch operations.

        Uses a single query to check existing jobs and executemany for inserts,
        reducing database round-trips from O(2n) to O(2).

        Args:
            df: DataFrame with job data.

        Returns:
            Tuple of (new_count, updated_count).
        """
        if df.empty:
            return 0, 0

        df_with_ids = self._add_job_ids_to_dataframe(df)
        blacklisted_ids = self._batch_query_blacklisted_ids(
            df_with_ids["job_id"].tolist()
        )
        if blacklisted_ids:
            df_with_ids = df_with_ids[
                ~df_with_ids["job_id"].isin(blacklisted_ids)
            ].copy()
            self.logger.info(
                "Skipped %d blacklisted job(s) while saving search results",
                len(blacklisted_ids),
            )

        if df_with_ids.empty:
            return 0, 0

        today = date.today()

        # Prepare all job data first
        jobs_data = []
        job_ids = []

        records = df_with_ids.to_dict("records")
        for record in records:
            job = Job.from_dict(record)

            # Convert date_posted to string for SQLite
            date_posted_str = None
            if job.date_posted:
                date_posted_str = (
                    job.date_posted.isoformat()
                    if hasattr(job.date_posted, "isoformat")
                    else str(job.date_posted)
                )

            jobs_data.append(
                (
                    job.job_id,
                    job.title,
                    job.company,
                    job.location,
                    job.job_url,
                    record.get("site"),
                    job.job_type,
                    job.is_remote,
                    record.get("job_level"),
                    job.description,
                    date_posted_str,
                    job.min_amount,
                    job.max_amount,
                    job.currency,
                    record.get("company_url"),
                    today,
                    today,
                    job.relevance_score,
                    False,
                    False,
                )
            )
            job_ids.append(job.job_id)

        # Query existing job IDs using batch method to handle SQLite variable limit
        existing_ids = self._batch_query_existing_ids(job_ids)

        # Batch insert/update all jobs
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(self.INSERT_OR_UPDATE, jobs_data)
            conn.commit()

        new_count = len(job_ids) - len(existing_ids)
        updated_count = len(existing_ids)

        return new_count, updated_count

    def get_new_job_ids(self, job_ids: list[str]) -> set[str]:
        """
        Identify which job IDs are new (not in database).

        Uses batch querying to handle SQLite's variable limit.

        Args:
            job_ids: List of job IDs to check.

        Returns:
            Set of job IDs that are not in the database.
        """
        if not job_ids:
            return set()

        existing_ids = self._batch_query_existing_ids(job_ids)
        blacklisted_ids = self._batch_query_blacklisted_ids(job_ids)
        return set(job_ids) - existing_ids - blacklisted_ids

    def filter_new_jobs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter DataFrame to only include new jobs.

        Uses the generate_job_id utility directly for efficiency
        instead of creating full Job objects.

        Args:
            df: DataFrame with job data.

        Returns:
            DataFrame with only new jobs.
        """
        if df.empty:
            return df

        df = self._add_job_ids_to_dataframe(df)

        # Get new job IDs (uses batch querying internally)
        new_ids = self.get_new_job_ids(df["job_id"].tolist())

        # Filter and remove temporary column
        return df[df["job_id"].isin(new_ids)].drop(columns=["job_id"])

    def exclude_blacklisted(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove blacklisted jobs from a DataFrame using the internal job identifier.

        Args:
            df: DataFrame with job data.

        Returns:
            DataFrame without blacklisted jobs.
        """
        if df.empty:
            return df

        df_with_ids = self._add_job_ids_to_dataframe(df)
        blacklisted_ids = self._batch_query_blacklisted_ids(
            df_with_ids["job_id"].tolist()
        )
        if not blacklisted_ids:
            return df

        filtered = df_with_ids[~df_with_ids["job_id"].isin(blacklisted_ids)].copy()
        return filtered.drop(columns=["job_id"])

    def get_all_jobs(self) -> list[JobDBRecord]:
        """
        Get all jobs from database.

        Returns:
            List of JobDBRecord instances.
        """
        records = []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.SELECT_ALL)

            for row in cursor.fetchall():
                records.append(self._row_to_record(row))

        return records

    def query_jobs(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        min_score: int | None = None,
        max_score: int | None = None,
        site: str | None = None,
        sites: list[str] | None = None,
        company: str | None = None,
        location: str | None = None,
        locations: list[str] | None = None,
        bookmarked: bool | None = None,
        applied: bool | None = None,
        remote: bool | None = None,
        job_type: str | None = None,
        job_types: list[str] | None = None,
        min_salary: float | None = None,
        max_salary: float | None = None,
        date_posted_from: date | datetime | str | None = None,
        date_posted_to: date | datetime | str | None = None,
        first_seen_from: date | datetime | str | None = None,
        first_seen_to: date | datetime | str | None = None,
        last_seen_from: date | datetime | str | None = None,
        last_seen_to: date | datetime | str | None = None,
        text: str | None = None,
        sort: str = "score",
    ) -> tuple[list[JobDBRecord], int]:
        """Query active jobs with SQL-backed filtering and pagination."""
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))

        where: list[str] = []
        params: list[object] = []

        if min_score is not None:
            where.append("relevance_score >= ?")
            params.append(min_score)
        if max_score is not None:
            where.append("relevance_score <= ?")
            params.append(max_score)
        site_values = self._unique_non_empty([site] if site else []) + (
            self._unique_non_empty(sites)
        )
        if site_values:
            placeholders = ",".join("?" * len(site_values))
            where.append(f"LOWER(site) IN ({placeholders})")
            params.extend(value.lower() for value in site_values)
        if company:
            where.append("LOWER(company) LIKE ?")
            params.append(f"%{company.lower()}%")
        if location:
            where.append("LOWER(location) LIKE ?")
            params.append(f"%{location.lower()}%")
        location_values = self._unique_non_empty(locations)
        if location_values:
            placeholders = ",".join("?" * len(location_values))
            where.append(f"LOWER(location) IN ({placeholders})")
            params.extend(value.lower() for value in location_values)
        if bookmarked is not None:
            where.append("bookmarked = ?")
            params.append(bool(bookmarked))
        if applied is not None:
            where.append("applied = ?")
            params.append(bool(applied))
        if remote is not None:
            where.append("is_remote = ?")
            params.append(bool(remote))
        job_type_values = self._unique_non_empty([job_type] if job_type else []) + (
            self._unique_non_empty(job_types)
        )
        if job_type_values:
            placeholders = ",".join("?" * len(job_type_values))
            where.append(f"LOWER(job_type) IN ({placeholders})")
            params.extend(value.lower() for value in job_type_values)
        if min_salary is not None:
            where.append("COALESCE(max_amount, min_amount) >= ?")
            params.append(min_salary)
        if max_salary is not None:
            where.append("COALESCE(min_amount, max_amount) <= ?")
            params.append(max_salary)
        for column, start, end in (
            ("date_posted", date_posted_from, date_posted_to),
            ("first_seen", first_seen_from, first_seen_to),
            ("last_seen", last_seen_from, last_seen_to),
        ):
            start_value = self._date_filter_value(start)
            end_value = self._date_filter_value(end)
            if start_value is not None:
                where.append(f"date({column}) >= date(?)")
                params.append(start_value)
            if end_value is not None:
                where.append(f"date({column}) <= date(?)")
                params.append(end_value)
        if text:
            like = f"%{text.lower()}%"
            where.append(
                "("
                "LOWER(title) LIKE ? OR "
                "LOWER(company) LIKE ? OR "
                "LOWER(location) LIKE ? OR "
                "LOWER(COALESCE(description, '')) LIKE ?"
                ")"
            )
            params.extend([like, like, like, like])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order_sql = {
            "company": "ORDER BY LOWER(company) ASC, relevance_score DESC, last_seen DESC",
            "date": (
                "ORDER BY COALESCE(date_posted, first_seen, last_seen) DESC, "
                "relevance_score DESC"
            ),
            "salary": (
                "ORDER BY COALESCE(max_amount, min_amount, 0) DESC, "
                "COALESCE(min_amount, max_amount, 0) DESC, relevance_score DESC"
            ),
            "score": "ORDER BY relevance_score DESC, last_seen DESC",
            "title": "ORDER BY LOWER(title) ASC, relevance_score DESC, last_seen DESC",
        }.get(sort, "ORDER BY relevance_score DESC, last_seen DESC")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM jobs {where_sql}", params)
            total = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                SELECT {_JOB_COLUMNS}
                FROM jobs
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            records = [self._row_to_record(row) for row in cursor.fetchall()]

        return records, total

    def list_blacklisted_jobs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        text: str | None = None,
        company: str | None = None,
        location: str | None = None,
    ) -> tuple[list[BlacklistedJobRecord], int]:
        """Return blacklisted jobs with SQL-backed search and pagination."""
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))

        where: list[str] = []
        params: list[object] = []

        if text:
            like = f"%{text.lower()}%"
            where.append(
                "("
                "LOWER(job_id) LIKE ? OR "
                "LOWER(title) LIKE ? OR "
                "LOWER(company) LIKE ? OR "
                "LOWER(location) LIKE ?"
                ")"
            )
            params.extend([like, like, like, like])
        if company:
            where.append("LOWER(company) LIKE ?")
            params.append(f"%{company.lower()}%")
        if location:
            where.append("LOWER(location) LIKE ?")
            params.append(f"%{location.lower()}%")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM deleted_jobs {where_sql}", params)
            total = int(cursor.fetchone()[0])
            cursor.execute(
                f"""
                SELECT {_DELETED_JOB_COLUMNS}
                FROM deleted_jobs
                {where_sql}
                ORDER BY blacklisted_at DESC, LOWER(title) ASC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            records = [
                BlacklistedJobRecord(
                    job_id=row["job_id"],
                    title=row["title"],
                    company=row["company"],
                    location=row["location"],
                    blacklisted_at=row["blacklisted_at"],
                )
                for row in cursor.fetchall()
            ]

        return records, total

    def get_facets(self) -> dict[str, list[dict[str, object]]]:
        """Return value/count summaries for dashboard filter controls."""

        def facet_counts(
            cursor: sqlite3.Cursor,
            column: str,
            *,
            limit: int = 50,
        ) -> list[dict[str, object]]:
            cursor.execute(
                f"""
                SELECT {column} AS value, COUNT(*) AS count
                FROM jobs
                WHERE {column} IS NOT NULL
                  AND TRIM(CAST({column} AS TEXT)) != ''
                GROUP BY {column}
                ORDER BY count DESC, LOWER(CAST({column} AS TEXT)) ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                {"value": row["value"], "count": int(row["count"])}
                for row in cursor.fetchall()
            ]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT is_remote AS value, COUNT(*) AS count
                FROM jobs
                WHERE is_remote IS NOT NULL
                GROUP BY is_remote
                ORDER BY count DESC, is_remote ASC
                """
            )
            remote: list[dict[str, object]] = [
                {"value": bool(row["value"]), "count": int(row["count"])}
                for row in cursor.fetchall()
            ]

            return {
                "sites": facet_counts(cursor, "site"),
                "companies": facet_counts(cursor, "company"),
                "locations": facet_counts(cursor, "location"),
                "job_types": facet_counts(cursor, "job_type"),
                "remote": remote,
            }

    def get_top_jobs(self, limit: int = 10, min_score: int = 0) -> list[JobDBRecord]:
        """
        Get top jobs from database ordered by relevance score.

        Args:
            limit: Maximum number of jobs to return.
            min_score: Minimum relevance score to include.

        Returns:
            List of JobDBRecord instances sorted by score descending.
        """
        records = []

        query = f"""
            SELECT {_JOB_COLUMNS}
            FROM jobs
            WHERE relevance_score >= ?
            ORDER BY relevance_score DESC
            LIMIT ?
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (min_score, limit))

            for row in cursor.fetchall():
                records.append(self._row_to_record(row))

        return records

    def get_job_count(self) -> int:
        """
        Get total count of jobs in database.

        Returns:
            Total number of jobs.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            return cursor.fetchone()[0]

    def get_jobs_first_seen_today(self) -> list[JobDBRecord]:
        """
        Get jobs that were first seen today.

        Returns:
            List of JobDBRecord instances.
        """
        records = []
        today = date.today()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.SELECT_NEW, (today,))

            for row in cursor.fetchall():
                records.append(self._row_to_record(row))

        return records

    def mark_as_applied(self, job_id: str) -> bool:
        """
        Mark a job as applied.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if job was updated, False if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.MARK_APPLIED, (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mark_as_unapplied(self, job_id: str) -> bool:
        """
        Mark a job as unapplied.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if job was updated, False if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.MARK_UNAPPLIED, (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_applied(self, job_id: str) -> bool:
        """
        Toggle applied status for a job.

        Args:
            job_id: Unique job identifier.

        Returns:
            New applied state (True if now applied, False if unapplied).

        Raises:
            ValueError: If job_id is not found in the database.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT applied FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Job not found: {job_id}")

            new_state = not bool(row[0])
            cursor.execute(
                "UPDATE jobs SET applied = ? WHERE job_id = ?",
                (new_state, job_id),
            )
            conn.commit()
            return new_state

    def set_applied(self, job_id: str, applied: bool) -> bool:
        """Set applied status for a job idempotently."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,))
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                "UPDATE jobs SET applied = ? WHERE job_id = ?",
                (applied, job_id),
            )
            conn.commit()
            return True

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a single job from the database.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if job was deleted, False if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def blacklist_job(self, job_id: str) -> bool:
        """
        Delete a job from the main table and persist its ID in the blacklist.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if the job was blacklisted and removed, False otherwise.
        """
        return self.blacklist_jobs([job_id]) > 0

    def delete_jobs(self, job_ids: list[str]) -> int:
        """
        Delete multiple jobs from the database.

        Args:
            job_ids: List of job IDs to delete.

        Returns:
            Number of jobs deleted.
        """
        if not job_ids:
            return 0

        total_deleted = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(job_ids), self.SQLITE_VAR_LIMIT):
                chunk = job_ids[i : i + self.SQLITE_VAR_LIMIT]
                placeholders = ",".join("?" * len(chunk))
                cursor.execute(
                    f"DELETE FROM jobs WHERE job_id IN ({placeholders})", chunk
                )
                total_deleted += cursor.rowcount

            conn.commit()

        return total_deleted

    def unblacklist_jobs(self, job_ids: list[str]) -> int:
        """
        Remove job IDs from the blacklist without restoring active job rows.

        Args:
            job_ids: List of job IDs to unblock for future imports.

        Returns:
            Number of blacklist rows removed.
        """
        if not job_ids:
            return 0

        total_removed = 0
        unique_job_ids = list(dict.fromkeys(job_ids))

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(unique_job_ids), self.SQLITE_VAR_LIMIT):
                chunk = unique_job_ids[i : i + self.SQLITE_VAR_LIMIT]
                placeholders = ",".join("?" * len(chunk))
                cursor.execute(
                    f"DELETE FROM deleted_jobs WHERE job_id IN ({placeholders})",
                    chunk,
                )
                total_removed += cursor.rowcount

            conn.commit()

        return total_removed

    def blacklist_jobs(self, job_ids: list[str]) -> int:
        """
        Blacklist multiple jobs and remove them from the active job table.

        Future searches will skip blacklisted IDs when saving results.

        Args:
            job_ids: List of job IDs to blacklist.

        Returns:
            Number of active jobs removed and blacklisted.
        """
        if not job_ids:
            return 0

        total_blacklisted = 0
        unique_job_ids = list(dict.fromkeys(job_ids))
        blacklisted_at = datetime.now().isoformat(timespec="seconds")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(unique_job_ids), self.SQLITE_VAR_LIMIT):
                chunk = unique_job_ids[i : i + self.SQLITE_VAR_LIMIT]
                placeholders = ",".join("?" * len(chunk))

                cursor.execute(
                    f"""
                    INSERT OR REPLACE INTO deleted_jobs ({_DELETED_JOB_COLUMNS})
                    SELECT job_id, title, company, location, ?
                    FROM jobs
                    WHERE job_id IN ({placeholders})
                    """,
                    [blacklisted_at, *chunk],
                )
                cursor.execute(
                    f"DELETE FROM jobs WHERE job_id IN ({placeholders})",
                    chunk,
                )
                total_blacklisted += cursor.rowcount

            conn.commit()

        return total_blacklisted

    def toggle_bookmark(self, job_id: str) -> bool:
        """
        Toggle bookmark status for a job.

        Args:
            job_id: Unique job identifier.

        Returns:
            New bookmark state (True if now bookmarked, False if unbookmarked).

        Raises:
            ValueError: If job_id is not found in the database.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bookmarked FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Job not found: {job_id}")

            new_state = not bool(row[0])
            cursor.execute(
                "UPDATE jobs SET bookmarked = ? WHERE job_id = ?",
                (new_state, job_id),
            )
            conn.commit()
            return new_state

    def set_bookmarked(self, job_id: str, bookmarked: bool) -> bool:
        """Set bookmark status for a job idempotently."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,))
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                "UPDATE jobs SET bookmarked = ? WHERE job_id = ?",
                (bookmarked, job_id),
            )
            conn.commit()
            return True

    def get_job_by_id(self, job_id: str) -> JobDBRecord | None:
        """
        Get a single job by its ID.

        Args:
            job_id: Unique job identifier.

        Returns:
            JobDBRecord if found, None otherwise.
        """
        query = f"""
            SELECT {_JOB_COLUMNS}
            FROM jobs
            WHERE job_id = ?
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (job_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def get_jobs_by_ids(self, job_ids: list[str]) -> list[JobDBRecord]:
        """
        Get multiple jobs by their IDs, preserving the requested order.

        Args:
            job_ids: List of unique job identifiers.

        Returns:
            List of matching JobDBRecord instances.
        """
        if not job_ids:
            return []

        unique_job_ids = list(dict.fromkeys(job_ids))
        records_by_id: dict[str, JobDBRecord] = {}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for i in range(0, len(unique_job_ids), self.SQLITE_VAR_LIMIT):
                chunk = unique_job_ids[i : i + self.SQLITE_VAR_LIMIT]
                placeholders = ",".join("?" * len(chunk))
                query = f"""
                    SELECT {_JOB_COLUMNS}
                    FROM jobs
                    WHERE job_id IN ({placeholders})
                """
                cursor.execute(query, chunk)
                for row in cursor.fetchall():
                    record = self._row_to_record(row)
                    records_by_id[record.job_id] = record

        return [
            records_by_id[job_id]
            for job_id in unique_job_ids
            if job_id in records_by_id
        ]

    def get_statistics(self) -> dict[str, int | float]:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total jobs
            cursor.execute("SELECT COUNT(*) FROM jobs")
            total = cursor.fetchone()[0]

            # Jobs seen today
            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE last_seen = ?", (date.today(),)
            )
            seen_today = cursor.fetchone()[0]

            # New today
            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE first_seen = ?", (date.today(),)
            )
            new_today = cursor.fetchone()[0]

            # Applied
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE applied = TRUE")
            applied = cursor.fetchone()[0]

            # Blacklisted
            cursor.execute("SELECT COUNT(*) FROM deleted_jobs")
            blacklisted = cursor.fetchone()[0]

            # Average relevance score
            cursor.execute("SELECT AVG(relevance_score) FROM jobs")
            avg_score = cursor.fetchone()[0] or 0

        return {
            "total_jobs": total,
            "seen_today": seen_today,
            "new_today": new_today,
            "applied": applied,
            "blacklisted": blacklisted,
            "avg_relevance_score": round(avg_score, 1),
        }

    def export_to_dataframe(self) -> pd.DataFrame:
        """
        Export all jobs to DataFrame.

        Returns:
            DataFrame with all jobs.
        """
        records = self.get_all_jobs()

        if not records:
            return pd.DataFrame()

        data = []
        for record in records:
            data.append(
                {
                    "job_id": record.job_id,
                    "title": record.title,
                    "company": record.company,
                    "location": record.location,
                    "job_url": record.job_url,
                    "site": record.site,
                    "job_type": record.job_type,
                    "is_remote": record.is_remote,
                    "job_level": record.job_level,
                    "description": record.description,
                    "date_posted": record.date_posted,
                    "min_amount": record.min_amount,
                    "max_amount": record.max_amount,
                    "currency": record.currency,
                    "company_url": record.company_url,
                    "first_seen": record.first_seen,
                    "last_seen": record.last_seen,
                    "relevance_score": record.relevance_score,
                    "applied": record.applied,
                    "bookmarked": record.bookmarked,
                }
            )

        return pd.DataFrame(data)

    def _row_to_record(self, row: sqlite3.Row) -> JobDBRecord:
        """
        Convert database row to JobDBRecord.

        Args:
            row: SQLite row.

        Returns:
            JobDBRecord instance.
        """
        return JobDBRecord(
            job_id=row["job_id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            job_url=row["job_url"],
            site=row["site"],
            job_type=row["job_type"],
            is_remote=row["is_remote"],
            job_level=row["job_level"],
            description=row["description"],
            date_posted=row["date_posted"],
            min_amount=row["min_amount"],
            max_amount=row["max_amount"],
            currency=row["currency"],
            company_url=row["company_url"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            relevance_score=row["relevance_score"],
            applied=bool(row["applied"]),
            bookmarked=bool(row["bookmarked"]),
        )

    def update_scores_batch(self, updates: list[tuple[str, int]]) -> int:
        """
        Batch update relevance scores for multiple jobs.

        Args:
            updates: List of (job_id, new_score) tuples.

        Returns:
            Number of jobs updated.
        """
        if not updates:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # SQLite executemany expects (score, job_id) order to match UPDATE SET ? WHERE ?
            cursor.executemany(
                "UPDATE jobs SET relevance_score = ? WHERE job_id = ?",
                [(score, job_id) for job_id, score in updates],
            )
            conn.commit()
            return cursor.rowcount

    def delete_stale_jobs(self, max_age_days: int) -> int:
        """Delete jobs whose ``last_seen`` is older than ``max_age_days``.

        Bookmarked and applied jobs are protected at the SQL level.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM jobs WHERE last_seen < date('now', ?) "
                "AND bookmarked = 0 AND applied = 0",
                (f"-{max_age_days} days",),
            )
            conn.commit()
            return cursor.rowcount

    def delete_jobs_below_score(self, score: int) -> int:
        """Delete jobs with ``relevance_score`` strictly below ``score``.

        Bookmarked and applied jobs are protected at the SQL level.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM jobs WHERE relevance_score < ? "
                "AND bookmarked = 0 AND applied = 0",
                (score,),
            )
            conn.commit()
            return cursor.rowcount

    def purge_blacklist(self, older_than_days: int | None = None) -> int:
        """Delete rows from the blacklist table.

        If ``older_than_days`` is given, only rows blacklisted earlier than
        that cutoff are removed; otherwise the whole table is cleared.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if older_than_days is None:
                cursor.execute("DELETE FROM deleted_jobs")
            else:
                cursor.execute(
                    "DELETE FROM deleted_jobs WHERE blacklisted_at < datetime('now', ?)",
                    (f"-{older_than_days} days",),
                )
            conn.commit()
            return cursor.rowcount

    def get_score_distribution(self, bin_size: int = 5) -> list[tuple[int, int]]:
        """Return a list of ``(bin_start, count)`` pairs for histogramming.

        Each bin covers ``[bin_start, bin_start + bin_size)`` of the score
        axis. The range is derived from the actual min/max in the database.
        """
        if bin_size <= 0:
            raise ValueError(f"bin_size must be positive, got {bin_size}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MIN(relevance_score), MAX(relevance_score), COUNT(*) FROM jobs"
            )
            row = cursor.fetchone()
            if row is None or row[2] == 0:
                return []
            lo, hi = int(row[0]), int(row[1])

            start = (lo // bin_size) * bin_size
            bins: list[tuple[int, int]] = []
            edge = start
            while edge <= hi:
                cursor.execute(
                    "SELECT COUNT(*) FROM jobs WHERE relevance_score >= ? "
                    "AND relevance_score < ?",
                    (edge, edge + bin_size),
                )
                bins.append((edge, cursor.fetchone()[0]))
                edge += bin_size
            return bins

    def count_jobs_below_score(self, score: int) -> int:
        """Preview for ``delete_jobs_below_score`` (bookmarks/applied excluded)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE relevance_score < ? "
                "AND bookmarked = 0 AND applied = 0",
                (score,),
            )
            return int(cursor.fetchone()[0])

    def count_stale_jobs(self, days: int) -> int:
        """Preview for ``delete_stale_jobs`` (bookmarks/applied excluded)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE last_seen < date('now', ?) "
                "AND bookmarked = 0 AND applied = 0",
                (f"-{days} days",),
            )
            return int(cursor.fetchone()[0])

    def count_blacklist_older_than(self, days: int) -> int:
        """Preview for ``purge_blacklist``."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM deleted_jobs "
                "WHERE blacklisted_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            return int(cursor.fetchone()[0])

    def preview_reconcile_with_config(self, config: Config) -> ReconciliationReport:
        """Preview reconciliation counts using the same deletion order as runtime.

        The first pass deletes jobs below the save threshold. The stale-job
        preview therefore excludes rows that would already be removed by the
        score pass, so preview totals match actual execution totals.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE bookmarked = 1")
            protected_bookmarked = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE applied = 1")
            protected_applied = int(cursor.fetchone()[0])

            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE relevance_score < ? "
                "AND bookmarked = 0 AND applied = 0",
                (config.scoring.save_threshold,),
            )
            deleted_below_score = int(cursor.fetchone()[0])

            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE relevance_score >= ? "
                "AND last_seen < date('now', ?) "
                "AND bookmarked = 0 AND applied = 0",
                (
                    config.scoring.save_threshold,
                    f"-{config.database.retention.max_age_days} days",
                ),
            )
            deleted_stale = int(cursor.fetchone()[0])

            cursor.execute(
                "SELECT COUNT(*) FROM deleted_jobs "
                "WHERE blacklisted_at < datetime('now', ?)",
                (f"-{config.database.retention.purge_blacklist_after_days} days",),
            )
            purged_blacklist = int(cursor.fetchone()[0])

        return ReconciliationReport(
            deleted_below_score=deleted_below_score,
            deleted_stale=deleted_stale,
            purged_blacklist=purged_blacklist,
            protected_bookmarked=protected_bookmarked,
            protected_applied=protected_applied,
        )

    def reconcile_with_config(self, config: Config) -> ReconciliationReport:
        """Align the DB with the current settings.yaml retention rules.

        Runs three cleanup passes, in order:
          1. drop jobs below ``scoring.save_threshold``
          2. drop stale jobs older than ``database.retention.max_age_days``
          3. purge blacklist rows older than ``database.retention.purge_blacklist_after_days``

        Bookmarked/applied jobs are always protected. The operation is
        idempotent: calling it twice in a row yields zeros the second time.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE bookmarked = 1")
            protected_bookmarked = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE applied = 1")
            protected_applied = int(cursor.fetchone()[0])

        report = ReconciliationReport(
            protected_bookmarked=protected_bookmarked,
            protected_applied=protected_applied,
        )
        report.deleted_below_score = self.delete_jobs_below_score(
            config.scoring.save_threshold
        )
        report.deleted_stale = self.delete_stale_jobs(
            config.database.retention.max_age_days
        )
        report.purged_blacklist = self.purge_blacklist(
            older_than_days=config.database.retention.purge_blacklist_after_days
        )

        self.logger.info(
            "Reconciled DB: %d below score, %d stale, %d blacklist purged "
            "(protected: %d bookmarked, %d applied)",
            report.deleted_below_score,
            report.deleted_stale,
            report.purged_blacklist,
            protected_bookmarked,
            protected_applied,
        )
        return report

    def reset_all(self) -> tuple[int, int]:
        """Truncate both ``jobs`` and ``deleted_jobs``. Danger zone escape hatch.

        This is the only path that bypasses the bookmark/applied protection.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            jobs_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM deleted_jobs")
            blacklist_count = int(cursor.fetchone()[0])
            cursor.execute("DELETE FROM jobs")
            cursor.execute("DELETE FROM deleted_jobs")
            conn.commit()
        return jobs_count, blacklist_count


def get_database(config: Config) -> JobDatabase:
    """
    Get database instance for given configuration.

    Args:
        config: Configuration object.

    Returns:
        JobDatabase instance.
    """
    return JobDatabase(config.database_path)


def recalculate_all_scores(db: JobDatabase, config: Config) -> int:
    """
    Recalculate relevance scores for all jobs in the database.

    Uses the current scoring configuration from settings.yaml to
    recalculate scores for all existing jobs.

    Args:
        db: Database instance.
        config: Configuration with current scoring settings.

    Returns:
        Number of jobs updated.
    """
    logger = get_logger("database")

    # Get all jobs
    all_jobs = db.get_all_jobs()

    if not all_jobs:
        logger.info("No jobs in database to recalculate")
        return 0

    logger.info(f"Recalculating scores for {len(all_jobs)} jobs...")

    # Calculate new scores and collect updates
    updates = []
    for job in all_jobs:
        # Build a dict-like object for scoring calculation
        job_data = {
            "title": job.title or "",
            "description": job.description or "",
            "company": job.company or "",
            "location": job.location or "",
        }

        # Calculate new score
        new_score = calculate_relevance_score(job_data, config)

        # Only update if different
        if new_score != job.relevance_score:
            updates.append((job.job_id, new_score))

    # Batch update using public method
    updated = db.update_scores_batch(updates) if updates else 0

    logger.info(f"Recalculated scores: {updated} jobs updated")
    return updated
