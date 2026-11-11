"""Schema 8 context storage: full payloads and one files row per context asset.

``legacy_prepare_context`` is a private copy of the preparation code released up to
schema 8, so migration tests compare the current read path with bytes the current
write path never produced.
"""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from uuid import uuid4

from policy_fixtures import make_schema_nine

# The contexts table as released with schema 5 to 8.
CONTEXTS_EIGHT = """CREATE TABLE contexts (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 payload TEXT NOT NULL, signature TEXT NOT NULL, idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL
)"""
SCHEMA_NINE_TABLES = ("context_parts", "snapshot_list_items", "snapshot_parts")
SCHEMA_NINE_VIEWS = ("all_files", "context_files")


def make_schema_eight(path):
    """Put context payloads and context file rows back as schema 8 stored them."""
    from openings.snapshots import payload_text

    make_schema_nine(path)  # first undo schema 10

    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute(
            "SELECT id,application_id,signature,idempotency_key,created_at FROM contexts "
            "ORDER BY rowid"
        ).fetchall()
        payloads = {row[0]: payload_text(conn, row[0]) for row in rows}
        conn.execute(
            "INSERT INTO files(id,sha256,name,media_type,size,context_id,created_at) "
            "SELECT id,sha256,name,media_type,size,context_id,created_at FROM context_files"
        )
        for view in SCHEMA_NINE_VIEWS:
            conn.execute(f"DROP VIEW {view}")
        for table in SCHEMA_NINE_TABLES:
            conn.execute(f"DROP TABLE {table}")
        # Keep the references other tables hold to "contexts" while it is rebuilt.
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("ALTER TABLE contexts RENAME TO contexts_current")
        conn.execute(CONTEXTS_EIGHT)
        conn.executemany(
            "INSERT INTO contexts(id,application_id,payload,signature,idempotency_key,created_at) "
            "VALUES(?,?,?,?,?,?)",
            [(row[0], row[1], payloads[row[0]], *row[2:]) for row in rows],
        )
        conn.execute("DROP TABLE contexts_current")
        conn.execute("CREATE INDEX contexts_app ON contexts(application_id,created_at)")
        conn.execute("PRAGMA user_version=8")
        conn.commit()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")


def legacy_encode(value):
    """The serialisation every release up to schema 8 used for context payloads."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def insert_legacy_context(conn, application_id, payload, files=(), key=None, signature=None):
    """Write one schema 8 context row and its per-context file rows; return its id."""
    context_id = uuid4().hex
    timestamp = datetime.now(UTC).isoformat(timespec="microseconds")
    conn.execute(
        "INSERT INTO contexts(id,application_id,payload,signature,idempotency_key,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (
            context_id,
            application_id,
            payload,
            signature or hashlib.sha256(payload.encode()).hexdigest(),
            key,
            timestamp,
        ),
    )
    for asset in files:
        conn.execute(
            "INSERT INTO files(id,sha256,name,media_type,size,context_id,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                asset["id"],
                asset["sha256"],
                asset["path"],
                asset["media_type"],
                asset["size"],
                context_id,
                asset.get("created_at", timestamp),
            ),
        )
    return context_id


def legacy_prepare_context(
    path, application_id, *, knowledge_ids=None, claim_ids=None, template_ids=(), note="", key=None
):
    """Freeze a context exactly as the schema 8 service did, written with plain SQL."""
    from openings.career import DEFAULT_GUIDANCE, DEFAULT_PROFILE

    def decoded(row, fields):
        row = dict(row)
        for name in fields:
            if isinstance(row.get(name), str):
                row[name] = json.loads(row[name])
        return row

    def setting(conn, name, default):
        row = conn.execute("SELECT data,version FROM settings WHERE key=?", (name,)).fetchone()
        if not row:
            return {"data": default, "version": 0}
        return {"data": json.loads(row["data"]), "version": row["version"]}

    request = {
        "application_id": application_id,
        "template_id": None,
        "template_ids": list(template_ids),
        "knowledge_ids": knowledge_ids,
        "claim_ids": claim_ids,
        "note": note,
    }
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        application = decoded(
            conn.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone(),
            ["questions", "answers", "requirements"],
        )
        job = decoded(
            conn.execute("SELECT * FROM jobs WHERE id=?", (application["job_id"],)).fetchone(),
            ["metadata", "overrides"],
        )
        profile = setting(conn, "profile", DEFAULT_PROFILE)
        instructions = setting(conn, "instructions", {"general": DEFAULT_GUIDANCE})
        knowledge = [
            decoded(row, ["metadata", "dates", "skills"])
            for row in conn.execute("SELECT * FROM knowledge ORDER BY position,created_at,id")
        ]
        if knowledge_ids is not None:
            knowledge = [row for row in knowledge if row["id"] in set(knowledge_ids)]
        chosen = {row["id"] for row in knowledge}
        claims = [
            decoded(row, ["metadata"])
            for row in conn.execute(
                "SELECT * FROM claims WHERE approved=1 ORDER BY position,created_at,id"
            )
            if row["knowledge_id"] in chosen
        ]
        for claim in claims:
            claim["approved"] = bool(claim["approved"])
        if claim_ids is not None:
            claims = [row for row in claims if row["id"] in set(claim_ids)]
        if template_ids:
            templates = [
                dict(conn.execute("SELECT * FROM templates WHERE id=?", (item,)).fetchone())
                for item in template_ids
            ]
        else:
            templates = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM templates WHERE is_default=1 ORDER BY kind,id"
                )
            ]
        templates = [decoded(row, ["rules"]) for row in templates]
        for template in templates:
            template["is_default"] = bool(template["is_default"])
        assets = []
        for owner_type, identifiers in (
            ("knowledge", [row["id"] for row in knowledge]),
            ("template", [row["id"] for row in templates]),
        ):
            if not identifiers:
                continue
            column = owner_type + "_id"
            for original in conn.execute(
                f"SELECT * FROM files WHERE {column} IN ("
                + ",".join("?" for _ in identifiers)
                + f") ORDER BY {column},name,id",
                identifiers,
            ).fetchall():
                copied_id = uuid4().hex
                assets.append(
                    {
                        "id": copied_id,
                        "sha256": original["sha256"],
                        "name": original["name"],
                        "path": f"{owner_type}/{original[column]}/{original['name']}",
                        "media_type": original["media_type"],
                        "size": original["size"],
                        "owner_type": owner_type,
                        "owner_id": original[column],
                        "original_file_id": original["id"],
                        "url": f"/api/v1/files/{copied_id}/content",
                    }
                )
        snapshot = {
            "request": request,
            "profile": {**DEFAULT_PROFILE, **profile["data"], "version": profile["version"]},
            "job": job,
            "application": application,
            "knowledge": knowledge,
            "claims": claims,
            "templates": templates,
            "instructions": {
                "general": instructions["data"].get("general", DEFAULT_GUIDANCE),
                "version": instructions["version"],
                "template_append": {row["id"]: row["guidance"] for row in templates},
                "application_note": "\n\n".join(
                    part for part in [application["note"], note] if part
                ),
            },
            "questions": application["questions"],
            "files": assets,
        }
        encoded = legacy_encode(snapshot)
        context_id = insert_legacy_context(conn, application_id, encoded, assets, key)
        conn.commit()
    return {
        "id": context_id,
        "payload": encoded,
        "signature": hashlib.sha256(encoded.encode()).hexdigest(),
        "files": assets,
    }
