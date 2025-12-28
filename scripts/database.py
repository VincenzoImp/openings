"""
SQLite database for job persistence and tracking.

Stores job history to identify new jobs between search runs
and track application status.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pandas as pd

if TYPE_CHECKING:
    from config import Config

from models import Job, JobDBRecord


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
            applied BOOLEAN DEFAULT FALSE
        )
    """

    CREATE_INDEX = """
        CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen)
    """

    # Migration: Add new columns to existing databases
    MIGRATE_COLUMNS = [
        "ALTER TABLE jobs ADD COLUMN site TEXT",
        "ALTER TABLE jobs ADD COLUMN job_type TEXT",
        "ALTER TABLE jobs ADD COLUMN is_remote BOOLEAN",
        "ALTER TABLE jobs ADD COLUMN job_level TEXT",
        "ALTER TABLE jobs ADD COLUMN description TEXT",
        "ALTER TABLE jobs ADD COLUMN date_posted DATE",
        "ALTER TABLE jobs ADD COLUMN min_amount REAL",
        "ALTER TABLE jobs ADD COLUMN max_amount REAL",
        "ALTER TABLE jobs ADD COLUMN currency TEXT",
        "ALTER TABLE jobs ADD COLUMN company_url TEXT",
    ]

    INSERT_OR_UPDATE = """
        INSERT INTO jobs (job_id, title, company, location, job_url,
                          site, job_type, is_remote, job_level, description,
                          date_posted, min_amount, max_amount, currency, company_url,
                          first_seen, last_seen, relevance_score, applied)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    SELECT_ALL = """
        SELECT job_id, title, company, location, job_url,
               site, job_type, is_remote, job_level, description,
               date_posted, min_amount, max_amount, currency, company_url,
               first_seen, last_seen, relevance_score, applied
        FROM jobs
        ORDER BY last_seen DESC, relevance_score DESC
    """

    SELECT_NEW = """
        SELECT job_id, title, company, location, job_url,
               site, job_type, is_remote, job_level, description,
               date_posted, min_amount, max_amount, currency, company_url,
               first_seen, last_seen, relevance_score, applied
        FROM jobs
        WHERE first_seen = ?
        ORDER BY relevance_score DESC
    """

    MARK_APPLIED = "UPDATE jobs SET applied = TRUE WHERE job_id = ?"

    def __init__(self, db_path: Path):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema and run migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.CREATE_TABLE)
            cursor.execute(self.CREATE_INDEX)

            # Run migrations for existing databases
            for migration in self.MIGRATE_COLUMNS:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    # Only ignore "duplicate column" errors
                    if "duplicate column" not in error_msg and "already exists" not in error_msg:
                        self.logger.error(f"Migration failed: {migration}")
                        raise

            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get database connection with context manager.

        Yields:
            SQLite connection.
        """
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

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

    def save_job(self, job: Job, site: str | None = None,
                 job_level: str | None = None,
                 company_url: str | None = None) -> bool:
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
        today = date.today()
        is_new = not self.job_exists(job.job_id)

        # Convert date_posted to string for SQLite
        date_posted_str = None
        if job.date_posted:
            date_posted_str = job.date_posted.isoformat() if hasattr(job.date_posted, 'isoformat') else str(job.date_posted)

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
            if self.save_job(job):
                new_count += 1
            else:
                updated_count += 1

        return new_count, updated_count

    def save_jobs_from_dataframe(self, df: pd.DataFrame) -> tuple[int, int]:
        """
        Save jobs from DataFrame to database.

        Args:
            df: DataFrame with job data.

        Returns:
            Tuple of (new_count, updated_count).
        """
        new_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            row_dict = row.to_dict()
            job = Job.from_dict(row_dict)

            # Extract additional fields not in Job dataclass
            site = row_dict.get("site")
            job_level = row_dict.get("job_level")
            company_url = row_dict.get("company_url")

            if self.save_job(job, site=site, job_level=job_level, company_url=company_url):
                new_count += 1
            else:
                updated_count += 1

        return new_count, updated_count

    def get_new_job_ids(self, job_ids: list[str]) -> set[str]:
        """
        Identify which job IDs are new (not in database).

        Args:
            job_ids: List of job IDs to check.

        Returns:
            Set of job IDs that are not in the database.
        """
        if not job_ids:
            return set()

        existing_ids = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Use batch query instead of N+1 queries
            placeholders = ",".join("?" * len(job_ids))
            query = f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders})"
            cursor.execute(query, job_ids)
            existing_ids = {row[0] for row in cursor.fetchall()}
            cursor.close()

        return set(job_ids) - existing_ids

    def filter_new_jobs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter DataFrame to only include new jobs.

        Args:
            df: DataFrame with job data.

        Returns:
            DataFrame with only new jobs.
        """
        if df.empty:
            return df

        # Generate job IDs
        def generate_job_id(row: pd.Series) -> str:
            job = Job.from_dict(row.to_dict())
            return job.job_id

        df = df.copy()
        df["job_id"] = df.apply(generate_job_id, axis=1)

        # Get new job IDs
        new_ids = self.get_new_job_ids(df["job_id"].tolist())

        # Filter
        return df[df["job_id"].isin(new_ids)].drop(columns=["job_id"])

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

    def get_statistics(self) -> dict[str, int]:
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

            # Average relevance score
            cursor.execute("SELECT AVG(relevance_score) FROM jobs")
            avg_score = cursor.fetchone()[0] or 0

        return {
            "total_jobs": total,
            "seen_today": seen_today,
            "new_today": new_today,
            "applied": applied,
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
        # Helper to safely get column value (handles missing columns in old DBs)
        def get_col(name: str, default=None):
            try:
                return row[name]
            except (IndexError, KeyError):
                return default

        return JobDBRecord(
            job_id=row["job_id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            job_url=get_col("job_url"),
            site=get_col("site"),
            job_type=get_col("job_type"),
            is_remote=get_col("is_remote"),
            job_level=get_col("job_level"),
            description=get_col("description"),
            date_posted=get_col("date_posted"),
            min_amount=get_col("min_amount"),
            max_amount=get_col("max_amount"),
            currency=get_col("currency"),
            company_url=get_col("company_url"),
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            relevance_score=row["relevance_score"],
            applied=bool(row["applied"]),
        )


def get_database(config: Config) -> JobDatabase:
    """
    Get database instance for given configuration.

    Args:
        config: Configuration object.

    Returns:
        JobDatabase instance.
    """
    return JobDatabase(config.database_path)
