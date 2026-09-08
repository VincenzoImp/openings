"""The append-only timeline."""

from __future__ import annotations

from openings.db.base import Store
from openings.models import Event, EventKind


class EventsMixin(Store):
    def list_events(self, job_id: str) -> list[Event]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE job_id = ? ORDER BY created_at ASC, id ASC",
                (job_id,),
            ).fetchall()
        return [self.row_to_event(row) for row in rows]

    def status_before(self, job_id: str, status: str) -> str | None:
        """The status a job held before its latest move into ``status``."""
        events = [
            event
            for event in self.list_events(job_id)
            if event.kind is EventKind.STATUS and (event.data or {}).get("to") == status
        ]
        if not events:
            return None
        previous = (events[-1].data or {}).get("from")
        return str(previous) if previous else None
