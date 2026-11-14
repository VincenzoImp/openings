"""Career entries: detailed evidence with dates, organizations, skills and order."""

from __future__ import annotations

from .. import events
from ..common import check_page, check_version, decode_record, encode, get_row, new_id, now
from ..errors import missing
from ..idempotency import fingerprint, remember, replay
from .models import EntryCreate, EntryUpdate
from .records import values


class EntryOperations:
    """Listing, reading and writing career entries."""

    def list_entries(
        self,
        q: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
    ) -> dict:
        """Search career entries by q (title, organization, narrative) and kind. summary=true (the default) returns bounded previews and counts; summary=false returns full records. Read career_get for one entry's full narrative and metadata."""
        check_page(limit, offset)
        where, params = [], []
        if q:
            where.append("(title LIKE ? OR organization LIKE ? OR narrative LIKE ?)")
            params += [f"%{q}%"] * 3
        if kind:
            where.append("kind=?")
            params.append(kind)
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,kind,title,organization,dates,skills,position,version,created_at,updated_at,substr(narrative,1,240) AS narrative_preview,"
            "(SELECT substr(text,1,240) FROM claims WHERE knowledge_id=knowledge.id ORDER BY position,created_at,id LIMIT 1) AS highlight_preview,"
            "(SELECT COUNT(*) FROM claims WHERE knowledge_id=knowledge.id) AS highlight_count,"
            "(SELECT COUNT(*) FROM files WHERE knowledge_id=knowledge.id) AS file_count"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM knowledge{clause} ORDER BY position,created_at,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        total = self.db.one(f"SELECT COUNT(*) AS n FROM knowledge{clause}", params)["n"]
        return {
            "items": [
                decode_record(row, ["dates", "skills"] + ([] if summary else ["metadata"]))
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_entry(self, entry_id: str) -> dict:
        """Read one career evidence record with its full narrative and metadata."""
        row = self.db.one("SELECT * FROM knowledge WHERE id=?", (entry_id,))
        if not row:
            missing("Career entry")
        return decode_record(row, ["metadata", "dates", "skills"])

    def create_entry(self, value: EntryCreate) -> dict:
        """Add detailed career evidence. Facts should come from the user, not a job posting."""
        with self.db.transaction() as conn:
            record_id = self._insert_entry(conn, value, now())
        return self.get_entry(record_id)

    @staticmethod
    def _next_position(conn, table, entry_id=None):
        if table == "claims":
            row = conn.execute(
                "SELECT MAX(position) FROM claims WHERE knowledge_id=?", (entry_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT MAX(position) FROM knowledge").fetchone()
        return (row[0] + 1) if row[0] is not None else 0

    def _insert_entry(self, conn, value, timestamp):
        """Add one entry and return its id, or the id an earlier request with its key created."""
        digest = fingerprint(value)
        replayed = replay(conn, "knowledge", value.idempotency_key, digest)
        if replayed:
            return replayed
        record_id = new_id()
        position = (
            value.position if value.position is not None else self._next_position(conn, "knowledge")
        )
        conn.execute(
            "INSERT INTO knowledge(id,kind,title,organization,dates,skills,position,narrative,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                value.kind,
                value.title,
                value.organization,
                encode(value.dates.model_dump()) if value.dates is not None else None,
                encode(value.skills),
                position,
                value.narrative,
                encode(value.metadata),
                timestamp,
                timestamp,
            ),
        )
        events.record(conn, "career_created", ("career", record_id), {"kind": value.kind})
        remember(conn, "knowledge", value.idempotency_key, digest, record_id)
        return record_id

    def update_entry(self, entry_id: str, value: EntryUpdate) -> dict:
        """Revise entry fields with version protection; dates=null clears dates; document revisions keep the ids they cite."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = get_row(conn, "knowledge", entry_id, "Career entry")
            check_version(row, expected)
            previous = decode_record(row, ["metadata", "dates", "skills"])
            merged = {**previous, **data}
            fields = [
                "kind",
                "title",
                "organization",
                "dates",
                "skills",
                "position",
                "narrative",
                "metadata",
            ]
            if any(previous[key] != merged[key] for key in fields):
                conn.execute(
                    "UPDATE knowledge SET kind=?,title=?,organization=?,dates=?,skills=?,position=?,narrative=?,metadata=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        merged["kind"],
                        merged["title"],
                        merged["organization"],
                        encode(merged["dates"]) if merged["dates"] is not None else None,
                        encode(merged["skills"]),
                        merged["position"],
                        merged["narrative"],
                        encode(merged["metadata"]),
                        now(),
                        entry_id,
                    ),
                )
                events.record(
                    conn,
                    "career_updated",
                    ("career", entry_id),
                    {
                        "fields": [key for key in fields if previous[key] != merged[key]],
                        "version": row["version"] + 1,
                    },
                )
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: str, expected_version: int) -> dict:
        """Permanently delete a career entry and its highlights and files; document revisions are unchanged."""
        with self.db.transaction() as conn:
            check_version(get_row(conn, "knowledge", entry_id, "Career entry"), expected_version)
            conn.execute("DELETE FROM knowledge WHERE id=?", (entry_id,))
            events.record(conn, "career_deleted", ("career", entry_id))
        self.db.collect_blobs()
        return {"deleted": True, "id": entry_id}
