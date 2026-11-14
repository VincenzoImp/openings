"""Career entries: detailed evidence with dates, organizations, skills and order."""

from __future__ import annotations

from .. import events
from ..common import check_version, decode_record, encode, new_id, now
from ..errors import missing
from ..idempotency import fingerprint, remember, replay
from .models import KnowledgeCreate, KnowledgeUpdate
from .records import _get, _page, values


class EntryOperations:
    """Listing, reading and writing Career entries."""

    def list_knowledge(
        self,
        q: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
    ) -> dict:
        """Search Career entries by q (title, organization, narrative) and kind. summary=true (the default) returns bounded previews and counts; summary=false returns full records. Read knowledge_get for one entry's full narrative and metadata."""
        _page(limit, offset)
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
            "(SELECT substr(text,1,240) FROM claims WHERE knowledge_id=knowledge.id ORDER BY position,created_at,id LIMIT 1) AS claim_preview,"
            "(SELECT COUNT(*) FROM claims WHERE knowledge_id=knowledge.id) AS claim_count,"
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

    def get_knowledge(self, knowledge_id: str) -> dict:
        """Read one career evidence record with its full narrative and metadata."""
        row = self.db.one("SELECT * FROM knowledge WHERE id=?", (knowledge_id,))
        if not row:
            missing("Career knowledge")
        return decode_record(row, ["metadata", "dates", "skills"])

    def create_knowledge(self, value: KnowledgeCreate) -> dict:
        """Add detailed career evidence. Facts should come from the user, not a job posting."""
        with self.db.transaction() as conn:
            record_id = self._insert_knowledge(conn, value, now())
        return self.get_knowledge(record_id)

    @staticmethod
    def _next_position(conn, table, knowledge_id=None):
        if table == "claims":
            row = conn.execute(
                "SELECT MAX(position) FROM claims WHERE knowledge_id=?", (knowledge_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT MAX(position) FROM knowledge").fetchone()
        return (row[0] + 1) if row[0] is not None else 0

    def _insert_knowledge(self, conn, value, timestamp):
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
        events.record(conn, "knowledge_created", ("knowledge", record_id), {"kind": value.kind})
        remember(conn, "knowledge", value.idempotency_key, digest, record_id)
        return record_id

    def update_knowledge(self, knowledge_id: str, value: KnowledgeUpdate) -> dict:
        """Revise entry fields with version protection; dates=null clears dates; document revisions keep the ids they cite."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = _get(conn, "knowledge", knowledge_id, "Career knowledge")
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
                        knowledge_id,
                    ),
                )
                events.record(
                    conn,
                    "knowledge_updated",
                    ("knowledge", knowledge_id),
                    {
                        "fields": [key for key in fields if previous[key] != merged[key]],
                        "version": row["version"] + 1,
                    },
                )
        return self.get_knowledge(knowledge_id)

    def delete_knowledge(self, knowledge_id: str, expected_version: int) -> dict:
        """Permanently delete a career record and its reusable claims/live assets; document revisions are unchanged."""
        with self.db.transaction() as conn:
            check_version(
                _get(conn, "knowledge", knowledge_id, "Career knowledge"), expected_version
            )
            conn.execute("DELETE FROM knowledge WHERE id=?", (knowledge_id,))
            events.record(conn, "knowledge_deleted", ("knowledge", knowledge_id))
        self.db.collect_blobs()
        return {"deleted": True, "id": knowledge_id}
