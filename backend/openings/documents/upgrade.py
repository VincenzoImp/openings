"""The schema 12 to 13 step of documents: a CV or letter revision becomes its source.

Every revision keeps its id, files, hashes, review state and version. A CV or
letter revision's structured content moves, unchanged, to ``legacy_content``
(read-only; ``content`` becomes ``{}``), the evidence ids it cited are copied to
``claim_ids`` and ``knowledge_ids``, and its text is derived from its attached
.tex source. Form answers and other kinds keep their content and gain the cited
ids and, when a .tex source is attached, the derived text. Files gain
``source_sha256``, which stays NULL for every existing file: a PDF uploaded
before did not name its source. Nothing is deleted.
"""

from __future__ import annotations

import json

from .models import SOURCE_KINDS
from .sources import refresh_text

DOCUMENT_COLUMNS = (
    "text TEXT",
    "legacy_content TEXT CHECK(legacy_content IS NULL OR json_valid(legacy_content))",
    "note TEXT NOT NULL DEFAULT ''",
    "claim_ids TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(claim_ids) AND json_type(claim_ids)='array')",
    "knowledge_ids TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(knowledge_ids) AND json_type(knowledge_ids)='array')",
)
# The file views of schema.sql, with the PDF's source; the step builds them again.
FILE_VIEWS = """
CREATE VIEW context_files AS
 SELECT cp.file_id AS id, p.blob AS sha256, json_extract(p.content,'$.path') AS name,
  json_extract(p.content,'$.media_type') AS media_type, json_extract(p.content,'$.size') AS size,
  NULL AS knowledge_id, NULL AS template_id, cp.context_id AS context_id,
  NULL AS document_id, NULL AS job_id, coalesce(cp.file_created_at,c.created_at) AS created_at,
  NULL AS source_sha256
 FROM context_parts cp JOIN snapshot_parts p ON p.id=cp.part_id JOIN contexts c ON c.id=cp.context_id
 WHERE cp.file_id IS NOT NULL;
CREATE VIEW all_files AS
 SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at,source_sha256 FROM files
 UNION ALL SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at,source_sha256 FROM context_files
"""


def cited_ids(content) -> tuple[list[str], list[str]]:
    """The claim and Career entry ids structured content cites, in first-seen order."""
    claims: dict[str, None] = {}
    entries: dict[str, None] = {}

    def collect(target, value):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    target.setdefault(item, None)

    def walk(item):
        if isinstance(item, dict):
            collect(claims, item.get("claim_ids"))
            collect(entries, item.get("evidence_ids"))
            collect(entries, item.get("knowledge_ids"))
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(content)
    return list(claims), list(entries)


def migrate_to_13(conn):
    """Add the source-canonical columns and fill them from each existing revision."""
    for column in DOCUMENT_COLUMNS:
        conn.execute("ALTER TABLE documents ADD COLUMN " + column)
    conn.execute("ALTER TABLE files ADD COLUMN source_sha256 TEXT")
    conn.execute("DROP VIEW IF EXISTS all_files")
    conn.execute("DROP VIEW IF EXISTS context_files")
    for statement in FILE_VIEWS.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    marks = ",".join("?" for _ in SOURCE_KINDS)
    for document_id, content in conn.execute(
        "SELECT id,content FROM documents WHERE json_valid(content)"
    ).fetchall():
        claims, entries = cited_ids(json.loads(content))
        if claims or entries:
            conn.execute(
                "UPDATE documents SET claim_ids=?,knowledge_ids=? WHERE id=?",
                (json.dumps(claims), json.dumps(entries), document_id),
            )
    # Content that was not empty is kept as it was stored, byte for byte. Content
    # that is not JSON (never written by Openings) is left where it is.
    conn.execute(
        "UPDATE documents SET legacy_content=CASE WHEN content<>'{}' THEN content END,"
        f"content='{{}}' WHERE kind IN ({marks}) AND json_valid(content)",
        tuple(sorted(SOURCE_KINDS)),
    )
    for (document_id,) in conn.execute(
        "SELECT DISTINCT document_id FROM files WHERE document_id IS NOT NULL"
    ).fetchall():
        refresh_text(conn, document_id)
