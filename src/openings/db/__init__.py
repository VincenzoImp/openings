"""SQLite persistence for Openings.

The database owns every job and everything the user attaches to it. Only rows
in status ``new`` are ever removed automatically; every other status is
protected at the SQL level. ``JobDatabase`` composes one store per concern.
"""

from __future__ import annotations

from pathlib import Path

from openings.db.base import MAX_QUERY_LIMIT, SQLITE_VAR_LIMIT, Store
from openings.db.embeddings import EmbeddingsMixin
from openings.db.events import EventsMixin
from openings.db.jobs import (
    JOB_SORTS,
    SORT_DIRECTIONS,
    JobQuery,
    JobsMixin,
    MergeResult,
    UpsertResult,
)
from openings.db.material import MaterialMixin
from openings.db.retention import ReconciliationReport, RetentionMixin
from openings.db.runs import RunsMixin
from openings.db.schema import SCHEMA

__all__ = [
    "JOB_SORTS",
    "MAX_QUERY_LIMIT",
    "SORT_DIRECTIONS",
    "SQLITE_VAR_LIMIT",
    "JobDatabase",
    "JobQuery",
    "MergeResult",
    "ReconciliationReport",
    "UpsertResult",
]


class JobDatabase(
    JobsMixin, MaterialMixin, EventsMixin, EmbeddingsMixin, RunsMixin, RetentionMixin, Store
):
    """SQLite store for jobs, tracking state, embeddings and run history."""

    MAX_QUERY_LIMIT = MAX_QUERY_LIMIT
    SQLITE_VAR_LIMIT = SQLITE_VAR_LIMIT

    def __init__(self, db_path: Path):
        super().__init__(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            conn.commit()

    def reset_all(self) -> None:
        """Delete everything, including protected jobs and run history."""
        with self._connection() as conn:
            for table in (
                "events",
                "attachments",
                "notes",
                "job_labels",
                "embeddings",
                "postings",
                "jobs",
                "runs",
            ):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
