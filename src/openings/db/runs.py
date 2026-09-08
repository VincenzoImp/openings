"""Collection runs: opened at start, closed at the end."""

from __future__ import annotations

import json

from openings.db.base import Store
from openings.models import RunSummary


class RunsMixin(Store):
    def start_run(self, summary: RunSummary) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (started_at, finished_at, success) VALUES (?, NULL, 1)",
                (summary.started_at,),
            )
            conn.commit()
        summary.id = int(cursor.lastrowid or 0)
        return summary.id

    def finish_run(self, summary: RunSummary) -> int:
        """Write the final numbers; inserts the row when the run was never started."""
        if summary.id is None:
            self.start_run(summary)
        with self._connection() as conn:
            conn.execute(
                "UPDATE runs SET finished_at = ?, total_found = ?, unique_found = ?, saved = ?, "
                "new_jobs = ?, notified = ?, success = ?, sources_json = ?, errors_json = ? "
                "WHERE id = ?",
                (
                    summary.finished_at,
                    summary.total_found,
                    summary.unique_found,
                    summary.saved,
                    summary.new_jobs,
                    summary.notified,
                    summary.success,
                    json.dumps([source.to_dict() for source in summary.sources]),
                    json.dumps(list(summary.errors)),
                    summary.id,
                ),
            )
            conn.commit()
        return int(summary.id or 0)

    def list_runs(self, limit: int = 20) -> list[RunSummary]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC, id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [self.row_to_run(row) for row in rows]

    def open_run(self) -> RunSummary | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE finished_at IS NULL ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return self.row_to_run(row) if row else None

    def close_stale_runs(self) -> int:
        """Mark runs left open by a crashed process as failed."""
        with self._connection() as conn:
            cursor = conn.execute(
                "UPDATE runs SET finished_at = started_at, success = 0, "
                "errors_json = '[\"run: process ended before the run finished\"]' "
                "WHERE finished_at IS NULL"
            )
            conn.commit()
        return cursor.rowcount
