"""Templates: user-owned document packages with their rules."""

from __future__ import annotations

from ..common import check_version, decode_record, encode, new_id, now
from ..errors import missing
from .models import TemplateCreate, TemplateUpdate
from .records import _get, _page, values


class TemplateOperations:
    """Listing, reading and writing templates."""

    def list_templates(
        self,
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ) -> dict:
        """List template packages/defaults. summary=true omits TeX, guidance and rules; get the template before editing or compiling externally."""
        _page(limit, offset)
        where, params = [], []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if q:
            where.append("(name LIKE ? OR guidance LIKE ?)")
            params.extend([f"%{q}%"] * 2)
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,name,kind,is_default,version,created_at,updated_at,"
            "(SELECT COUNT(*) FROM files WHERE template_id=templates.id) AS file_count"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM templates{clause} ORDER BY is_default DESC,created_at,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        items = []
        for row in rows:
            row = row if summary else decode_record(row, ["rules"])
            row["is_default"] = bool(row["is_default"])
            items.append(row)
        return {
            "items": items,
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM templates{clause}", params)["n"],
        }

    def get_template(self, template_id: str) -> dict:
        """Read raw template source, guidance and rules (typed limits, rule statements, free-form rest); fetch attached assets separately."""
        row = self.db.one("SELECT * FROM templates WHERE id=?", (template_id,))
        if not row:
            missing("Template")
        row = decode_record(row, ["rules"])
        row["is_default"] = bool(row["is_default"])
        return row

    def create_template(self, value: TemplateCreate) -> dict:
        """Store a user template and optional rules. The first template of a kind becomes its default."""
        record_id, timestamp = new_id(), now()
        with self.db.transaction() as conn:
            is_default = (
                value.is_default
                or not conn.execute(
                    "SELECT 1 FROM templates WHERE kind=? AND is_default=1", (value.kind,)
                ).fetchone()
            )
            if is_default:
                conn.execute(
                    "UPDATE templates SET is_default=0,version=version+1,updated_at=? WHERE kind=? AND is_default=1",
                    (timestamp, value.kind),
                )
            conn.execute(
                "INSERT INTO templates(id,name,kind,tex,guidance,rules,is_default,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.name,
                    value.kind,
                    value.tex,
                    value.guidance,
                    encode(value.rules),
                    int(is_default),
                    timestamp,
                    timestamp,
                ),
            )
            self._record(conn, "template_created", "template", record_id, kind=value.kind)
        return self.get_template(record_id)

    def update_template(self, template_id: str, value: TemplateUpdate) -> dict:
        """Revise template source/default/guidance with optimistic version checking; old contexts stay frozen."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = _get(conn, "templates", template_id, "Template")
            check_version(row, expected)
            previous = decode_record(row, ["rules"])
            previous["is_default"] = bool(previous["is_default"])
            merged = {**previous, **data}
            changed = [
                key
                for key in ["name", "kind", "tex", "guidance", "rules", "is_default"]
                if previous[key] != merged[key]
            ]
            if changed:
                self._record(
                    conn,
                    "template_updated",
                    "template",
                    template_id,
                    fields=changed,
                    version=row["version"] + 1,
                )
                if merged["is_default"]:
                    conn.execute(
                        "UPDATE templates SET is_default=0,version=version+1,updated_at=? WHERE kind=? AND id<>? AND is_default=1",
                        (now(), merged["kind"], template_id),
                    )
                conn.execute(
                    "UPDATE templates SET name=?,kind=?,tex=?,guidance=?,rules=?,is_default=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        merged["name"],
                        merged["kind"],
                        merged["tex"],
                        merged["guidance"],
                        encode(merged["rules"]),
                        int(merged["is_default"]),
                        now(),
                        template_id,
                    ),
                )
        return self.get_template(template_id)

    def delete_template(self, template_id: str, expected_version: int) -> dict:
        """Delete a live template and assets; prior application contexts retain their exact template/asset copies."""
        with self.db.transaction() as conn:
            row = _get(conn, "templates", template_id, "Template")
            check_version(row, expected_version)
            conn.execute("DELETE FROM templates WHERE id=?", (template_id,))
            self._record(conn, "template_deleted", "template", template_id)
            if row["is_default"]:
                other = conn.execute(
                    "SELECT id FROM templates WHERE kind=? ORDER BY created_at,id LIMIT 1",
                    (row["kind"],),
                ).fetchone()
                if other:
                    conn.execute(
                        "UPDATE templates SET is_default=1,version=version+1,updated_at=? WHERE id=?",
                        (now(), other["id"]),
                    )
        self.db.collect_blobs()
        return {"deleted": True, "id": template_id}
