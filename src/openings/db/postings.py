"""Postings: the appearances of a job on its sources."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Sequence

from openings.db.base import Store, chunks, placeholders, unique
from openings.models import Posting


class PostingsMixin(Store):
    def list_postings(self, job_id: str) -> list[Posting]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM postings WHERE job_id = ? ORDER BY first_seen ASC, id ASC",
                (job_id,),
            ).fetchall()
        return [self.row_to_posting(row) for row in rows]

    def jobs_for_posting_keys(self, keys: Sequence[str]) -> dict[str, str]:
        """``posting key -> job_id`` for every key already known."""
        found: dict[str, str] = {}
        clean = unique(keys)
        if not clean:
            return found
        with self._connection() as conn:
            for chunk in chunks(clean):
                rows = conn.execute(
                    f"SELECT key, job_id FROM postings WHERE key IN ({placeholders(len(chunk))})",
                    list(chunk),
                ).fetchall()
                found.update({row["key"]: row["job_id"] for row in rows})
        return found

    def known_external_ids(self, source: str, external_ids: Sequence[str]) -> set[str]:
        """Which of ``external_ids`` already have a posting on ``source``."""
        clean = unique(external_ids)
        found: set[str] = set()
        if not clean:
            return found
        with self._connection() as conn:
            for chunk in chunks(clean):
                rows = conn.execute(
                    "SELECT external_id FROM postings WHERE source = ? "
                    f"AND external_id IN ({placeholders(len(chunk))})",
                    [source, *chunk],
                ).fetchall()
                found.update(row["external_id"] for row in rows)
        return found

    @staticmethod
    def _touch_posting(
        conn: sqlite3.Connection,
        job_id: str,
        key: str,
        source: str,
        external_id: str | None,
        url: str | None,
        seen: date,
    ) -> bool:
        """Insert the posting or refresh its ``last_seen``; True when it was new."""
        row = conn.execute("SELECT id, job_id FROM postings WHERE key = ?", (key,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO postings (job_id, key, source, external_id, url, first_seen, "
                "last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, key, source, external_id, url, seen, seen),
            )
            return True
        if row["job_id"] == job_id:
            conn.execute(
                "UPDATE postings SET last_seen = ?, url = COALESCE(url, ?), "
                "external_id = COALESCE(external_id, ?) WHERE id = ?",
                (seen, url, external_id, row["id"]),
            )
        return False
