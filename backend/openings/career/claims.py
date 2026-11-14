"""Claims: reusable, approved wording tied to a Career entry."""

from __future__ import annotations

from .. import events
from ..common import check_version, encode, new_id, now
from ..errors import missing
from ..idempotency import fingerprint, remember, replay
from .models import ClaimCreate, ClaimUpdate
from .records import _claim, _get, _page, values


class ClaimOperations:
    """Listing, reading and writing claims."""

    def list_claims(
        self,
        knowledge_id: str = "",
        approved: bool | None = None,
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
        q: str = "",
    ) -> dict:
        """List reusable claims by evidence (knowledge_id), approval or text (q). summary=true (the default) omits metadata and bounds wording previews; summary=false returns full claims. always_include is always returned."""
        _page(limit, offset)
        where, params = [], []
        if knowledge_id:
            where.append("knowledge_id=?")
            params.append(knowledge_id)
        if approved is not None:
            where.append("approved=?")
            params.append(int(approved))
        if q:
            where.append(
                "(text LIKE ? OR EXISTS(SELECT 1 FROM knowledge WHERE knowledge.id=claims.knowledge_id AND (title LIKE ? OR organization LIKE ?)))"
            )
            params.extend([f"%{q}%"] * 3)
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,knowledge_id,approved,position,always_include,version,created_at,updated_at,substr(text,1,240) AS text_preview,"
            "(SELECT title FROM knowledge WHERE knowledge.id=claims.knowledge_id) AS knowledge_title,"
            "(SELECT organization FROM knowledge WHERE knowledge.id=claims.knowledge_id) AS knowledge_organization"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM claims{clause} ORDER BY position,created_at,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": [_claim(row, full=not summary) for row in rows],
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM claims{clause}", params)["n"],
            "limit": limit,
            "offset": offset,
        }

    def get_claim(self, claim_id: str) -> dict:
        """Read a reusable claim and its evidence ID."""
        row = self.db.one("SELECT * FROM claims WHERE id=?", (claim_id,))
        if not row:
            missing("Claim")
        return _claim(row)

    def create_claim(self, value: ClaimCreate) -> dict:
        """Create reusable claim wording tied to evidence. Approval defaults to false. always_include marks a claim to include in every CV unless the job gives a reason to leave it out; any other selection hints go in metadata."""
        record_id, timestamp, digest = new_id(), now(), fingerprint(value)
        with self.db.transaction() as conn:
            replayed = replay(conn, "claims", value.idempotency_key, digest)
            if replayed:
                record_id = replayed
            else:
                self._insert_claim(conn, value, record_id, timestamp)
                remember(conn, "claims", value.idempotency_key, digest, record_id)
        return self.get_claim(record_id)

    def _insert_claim(self, conn, value, record_id, timestamp):
        _get(conn, "knowledge", value.knowledge_id, "Career knowledge")
        conn.execute(
            "INSERT INTO claims(id,knowledge_id,text,approved,position,always_include,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                value.knowledge_id,
                value.text,
                int(value.approved),
                value.position
                if value.position is not None
                else self._next_position(conn, "claims", value.knowledge_id),
                int(value.always_include),
                encode(value.metadata),
                timestamp,
                timestamp,
            ),
        )
        events.record(
            conn,
            "claim_created",
            ("claim", record_id),
            {"knowledge_id": value.knowledge_id, "approved": value.approved},
        )

    def update_claim(self, claim_id: str, value: ClaimUpdate) -> dict:
        """Revise or approve a claim with version checking; document generation does not silently approve new facts."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = _get(conn, "claims", claim_id, "Claim")
            check_version(row, expected)
            previous = _claim(row)
            merged = {**previous, **data}
            _get(conn, "knowledge", merged["knowledge_id"], "Career knowledge")
            if previous["knowledge_id"] != merged["knowledge_id"] and "position" not in data:
                merged["position"] = self._next_position(conn, "claims", merged["knowledge_id"])
            changed = [
                key
                for key in [
                    "knowledge_id",
                    "text",
                    "approved",
                    "position",
                    "always_include",
                    "metadata",
                ]
                if previous[key] != merged[key]
            ]
            if changed:
                events.record(
                    conn,
                    "claim_updated",
                    ("claim", claim_id),
                    {
                        "knowledge_id": merged["knowledge_id"],
                        "fields": changed,
                        "version": row["version"] + 1,
                    },
                )
                conn.execute(
                    "UPDATE claims SET knowledge_id=?,text=?,approved=?,position=?,always_include=?,metadata=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        merged["knowledge_id"],
                        merged["text"],
                        int(merged["approved"]),
                        merged["position"],
                        int(merged["always_include"]),
                        encode(merged["metadata"]),
                        now(),
                        claim_id,
                    ),
                )
        return self.get_claim(claim_id)

    def delete_claim(self, claim_id: str, expected_version: int) -> dict:
        """Permanently delete a reusable claim; document revisions keep the ids they cite."""
        with self.db.transaction() as conn:
            row = _get(conn, "claims", claim_id, "Claim")
            check_version(row, expected_version)
            conn.execute("DELETE FROM claims WHERE id=?", (claim_id,))
            events.record(
                conn, "claim_deleted", ("claim", claim_id), {"knowledge_id": row["knowledge_id"]}
            )
        return {"deleted": True, "id": claim_id}
