"""Content-addressed storage of frozen application contexts.

A context payload is one canonical JSON text. Its large shared values (each Career
entry, claim and template, the Profile, the job, the general instructions, each
policy section) are cut out as parts, stored once and keyed by the SHA-256 of their text. A context keeps
the remaining text as a frame of literals with one part between each pair, so the
payload is rebuilt by concatenation alone and is byte-identical by construction.

A list part stands for its items joined by commas. An asset part is one context
file entry without its per-context id and URL; the id lives on the reference, and
the part names the blob, so a context adds no row to ``files``. A payload that does
not have the canonical form is kept whole in the frame.

Every function accepts plain and ``sqlite3.Row`` connections.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

from .db import encode

SHARED_LISTS = ("claims", "knowledge", "templates")
SHARED_VALUES = ("job", "profile")
SHARED_INSTRUCTIONS = ("general", "template_append")
# A shorter value costs more as a reference than as text in the frame.
MIN_PART_CHARS = 200

# Mirrored in schema.sql; the 8 -> 9 migration creates the same objects. The file
# views gain source_sha256 in schema 13 (documents/upgrade.py builds them again).
SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot_parts (
 id INTEGER PRIMARY KEY, hash TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'text' CHECK(kind IN ('text','list','asset')),
 content TEXT NOT NULL, blob TEXT REFERENCES blobs(sha256),
 UNIQUE(hash,kind), CHECK((kind='asset')=(blob IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS snapshot_parts_blob ON snapshot_parts(blob) WHERE blob IS NOT NULL;
CREATE TABLE IF NOT EXISTS snapshot_list_items (
 list_id INTEGER NOT NULL REFERENCES snapshot_parts(id) ON DELETE CASCADE,
 position INTEGER NOT NULL, part_id INTEGER NOT NULL REFERENCES snapshot_parts(id),
 PRIMARY KEY(list_id,position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS snapshot_list_items_part ON snapshot_list_items(part_id);
CREATE TABLE IF NOT EXISTS context_parts (
 context_id TEXT NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
 position INTEGER NOT NULL, part_id INTEGER NOT NULL REFERENCES snapshot_parts(id),
 file_id TEXT, file_created_at TEXT,
 PRIMARY KEY(context_id,position)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS context_parts_part ON context_parts(part_id);
CREATE UNIQUE INDEX IF NOT EXISTS context_parts_file ON context_parts(file_id) WHERE file_id IS NOT NULL;
CREATE VIEW IF NOT EXISTS context_files AS
 SELECT cp.file_id AS id, p.blob AS sha256, json_extract(p.content,'$.path') AS name,
  json_extract(p.content,'$.media_type') AS media_type, json_extract(p.content,'$.size') AS size,
  NULL AS knowledge_id, NULL AS template_id, cp.context_id AS context_id,
  NULL AS document_id, NULL AS job_id, coalesce(cp.file_created_at,c.created_at) AS created_at
 FROM context_parts cp JOIN snapshot_parts p ON p.id=cp.part_id JOIN contexts c ON c.id=cp.context_id
 WHERE cp.file_id IS NOT NULL;
CREATE VIEW IF NOT EXISTS all_files AS
 SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at FROM files
 UNION ALL SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at FROM context_files;
"""
CONTEXT_COLUMNS = (
    "frame TEXT NOT NULL DEFAULT '[]'",
    "job_title",
    "company",
    "note_preview",
    "knowledge_count INTEGER",
    "claim_count INTEGER",
    "template_name",
    "file_count INTEGER NOT NULL DEFAULT 0",
)
# The list summary, computed by SQLite from the payload text bound as ?1, with the
# expressions context lists evaluated on every read before schema 9.
_STORED = (
    "frame,file_count,job_title,company,note_preview,knowledge_count,claim_count,template_name"
)
_SUMMARY = (
    "SELECT json_extract(?1,'$.job.title'),json_extract(?1,'$.job.company'),"
    "substr(json_extract(?1,'$.instructions.application_note'),1,160),"
    "json_array_length(?1,'$.knowledge'),json_array_length(?1,'$.claims'),"
    "json_extract(?1,'$.templates[0].name')"
)
_COLLECT = (
    # Lists are referenced by contexts only; their items go with them.
    (
        "DELETE FROM snapshot_parts WHERE kind='list' AND NOT EXISTS("
        "SELECT 1 FROM context_parts c WHERE c.part_id=snapshot_parts.id)"
    ),
    (
        "DELETE FROM snapshot_parts WHERE NOT EXISTS("
        "SELECT 1 FROM context_parts c WHERE c.part_id=snapshot_parts.id) AND NOT EXISTS("
        "SELECT 1 FROM snapshot_list_items i WHERE i.part_id=snapshot_parts.id)"
    ),
    (
        "DELETE FROM blobs WHERE sha256 NOT IN (SELECT sha256 FROM files) "
        "AND sha256 NOT IN (SELECT blob FROM snapshot_parts WHERE blob IS NOT NULL)"
    ),
)


def collect_unused(conn):
    """Remove parts no context references, then bytes no file or part references."""
    for statement in _COLLECT:
        conn.execute(statement)


def _file_url(file_id):
    return f"/api/v1/files/{file_id}/content"


def _wrap_asset(content, file_id):
    return f'{{"id":"{file_id}",{content[1:-1]},"url":"{_file_url(file_id)}"}}'


def _render(literals, parts):
    out = [literals[0]]
    for spec, literal in zip(parts, literals[1:], strict=True):
        if spec[0] == "list":
            out.append(",".join(spec[1]))
        elif spec[0] == "asset":
            out.append(_wrap_asset(spec[1], spec[2]))
        else:
            out.append(spec[1])
        out.append(literal)
    return "".join(out)


def _asset_parts(entries, files):
    """Asset parts for payload file entries that agree exactly with the stored files."""
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            return None
        row = files.get(entry["id"])
        rest = {key: value for key, value in entry.items() if key not in ("id", "url")}
        if (
            row is None
            or entry.get("url") != _file_url(entry["id"])
            or not all("id" < key < "url" for key in rest)
            or any(
                type(rest.get(key)) is not type(value) or rest.get(key) != value
                for key, value in (
                    ("path", row["name"]),
                    ("sha256", row["sha256"]),
                    ("media_type", row["media_type"]),
                    ("size", row["size"]),
                )
            )
        ):
            return None
        result.append(("asset", encode(rest), entry["id"], row["sha256"]))
    return result


def _split(text, files):
    """Cut a canonical payload into frame literals and parts; None when it is not canonical."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    literals, parts = [""], []

    def literal(value):
        literals[-1] += value

    def part(spec):
        parts.append(spec)
        literals.append("")

    def shared(value):
        encoded = encode(value)
        if len(encoded) >= MIN_PART_CHARS:
            part(("text", encoded))
        else:
            literal(encoded)

    def members(mapping, member):
        literal("{")
        for index, key in enumerate(sorted(mapping)):
            literal(("," if index else "") + encode(key) + ":")
            member(key, mapping[key])
        literal("}")

    def instruction(key, value):
        if key in SHARED_INSTRUCTIONS and isinstance(value, (str, dict)):
            shared(value)
        else:
            literal(encode(value))

    def section(_, value):
        # One policy section with its version: shared until that section changes.
        if isinstance(value, dict):
            shared(value)
        else:
            literal(encode(value))

    def top(key, value):
        if key in SHARED_LISTS and isinstance(value, list) and value:
            items = [encode(item) for item in value]
            literal("[")
            part(("list", items) if len(items) > 1 else ("text", items[0]))
            literal("]")
        elif key in SHARED_VALUES and isinstance(value, dict):
            shared(value)
        elif key == "instructions" and isinstance(value, dict):
            members(value, instruction)
        elif key == "policy" and isinstance(value, dict):
            members(value, section)
        elif (
            key == "files"
            and isinstance(value, list)
            and value
            and (assets := _asset_parts(value, files))
        ):
            literal("[")
            for index, asset in enumerate(assets):
                if index:
                    literal(",")
                part(asset)
            literal("]")
        else:
            literal(encode(value))

    try:
        members(data, top)
        if _render(literals, parts) != text:
            return None
    except TypeError, ValueError:
        return None
    return literals, parts


def _part_id(conn, cache, kind, content, blob=None, items=()):
    digest = hashlib.sha256(content.encode()).hexdigest()
    key = (digest, kind)
    if key in cache:
        return cache[key]
    row = conn.execute(
        "SELECT id FROM snapshot_parts WHERE hash=? AND kind=?", (digest, kind)
    ).fetchone()
    if row:
        identifier = row[0]
    else:
        identifier = conn.execute(
            "INSERT INTO snapshot_parts(hash,kind,content,blob) VALUES(?,?,?,?)",
            (digest, kind, "" if kind == "list" else content, blob),
        ).lastrowid
        conn.executemany(
            "INSERT INTO snapshot_list_items(list_id,position,part_id) VALUES(?,?,?)",
            [
                (identifier, position, _part_id(conn, cache, "text", item))
                for position, item in enumerate(items)
            ],
        )
    cache[key] = identifier
    return identifier


def _store_parts(conn, context_id, created_at, text, files, cache):
    """Insert a context's parts and references; return its ``_STORED`` column values."""
    files = {row["id"]: row for row in files}
    unrendered = dict(files)
    split = _split(text, files)
    literals, parts = split or ([text], [])
    references = []
    for position, spec in enumerate(parts):
        if spec[0] == "list":
            part = _part_id(conn, cache, "list", ",".join(spec[1]), items=spec[1])
            references.append((position, part, None))
        elif spec[0] == "asset":
            part = _part_id(conn, cache, "asset", spec[1], blob=spec[3])
            references.append((position, part, spec[2]))
            unrendered.pop(spec[2])
        else:
            references.append((position, _part_id(conn, cache, "text", spec[1]), None))
    # Files the payload does not render keep their identity and bytes all the same.
    for offset, row in enumerate(unrendered.values(), start=1):
        content = encode(
            {
                "media_type": row["media_type"],
                "path": row["name"],
                "sha256": row["sha256"],
                "size": row["size"],
            }
        )
        part = _part_id(conn, cache, "asset", content, blob=row["sha256"])
        references.append((-offset, part, row["id"]))

    def stamp(file_id):
        value = files[file_id].get("created_at") if file_id else None
        return None if value == created_at else value

    conn.executemany(
        "INSERT INTO context_parts(context_id,position,part_id,file_id,file_created_at) VALUES(?,?,?,?,?)",
        [
            (context_id, position, part, file_id, stamp(file_id))
            for position, part, file_id in references
        ],
    )
    if split or conn.execute("SELECT json_valid(?)", (text,)).fetchone()[0]:
        summary = tuple(conn.execute(_SUMMARY, (text,)).fetchone())
    else:
        summary = (None,) * 6
    return (encode(literals), len(files), *summary)


def store_context(conn, context_id, text, files=(), cache=None):
    """Store the payload text of an inserted context as a frame and shared parts.

    ``files`` are its asset files (id, sha256, name, media_type, size and optionally
    created_at). ``cache`` may carry part ids across calls in one transaction.
    """
    created = conn.execute("SELECT created_at FROM contexts WHERE id=?", (context_id,)).fetchone()[
        0
    ]
    values = _store_parts(conn, context_id, created, text, files, {} if cache is None else cache)
    conn.execute(
        f"UPDATE contexts SET ({_STORED})=(?,?,?,?,?,?,?,?) WHERE id=?", (*values, context_id)
    )


def payload_text(conn, context_id, frame=None):
    """Rebuild the exact payload text of one context."""
    if frame is None:
        row = conn.execute("SELECT frame FROM contexts WHERE id=?", (context_id,)).fetchone()
        if row is None:
            raise LookupError(context_id)
        frame = row[0]
    literals = json.loads(frame)
    out = [literals[0]]
    rows = conn.execute(
        "SELECT c.position,c.file_id,p.id,p.kind,p.content FROM context_parts c "
        "JOIN snapshot_parts p ON p.id=c.part_id WHERE c.context_id=? AND c.position>=0 "
        "ORDER BY c.position",
        (context_id,),
    ).fetchall()
    if len(rows) != len(literals) - 1:
        raise ValueError(f"Context {context_id} does not match its stored parts.")
    for (_, file_id, part, kind, content), literal in zip(rows, literals[1:], strict=True):
        if kind == "list":
            out.append(
                ",".join(
                    item[0]
                    for item in conn.execute(
                        "SELECT p.content FROM snapshot_list_items i JOIN snapshot_parts p "
                        "ON p.id=i.part_id WHERE i.list_id=? ORDER BY i.position",
                        (part,),
                    )
                )
            )
        elif kind == "asset":
            out.append(_wrap_asset(content, file_id))
        else:
            out.append(content)
        out.append(literal)
    return "".join(out)


def migrate_contexts(conn):
    """Schema 8 to 9: move every payload into parts and context files out of ``files``.

    Runs inside the upgrade transaction, one context at a time. Each rebuilt payload
    is compared with the stored text before the old column is dropped. The new column
    values wait in a temporary table: updating a row that still holds its payload
    would rewrite the whole payload each time.
    """
    # executescript would commit the surrounding upgrade, so run each statement.
    for statement in SCHEMA.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    conn.execute(f"CREATE TEMP TABLE context_frames(id TEXT PRIMARY KEY,{_STORED})")
    names = ("id", "sha256", "name", "media_type", "size", "created_at")
    cache = {}
    for context_id, created_at in conn.execute(
        "SELECT id,created_at FROM contexts ORDER BY rowid"
    ).fetchall():
        text = conn.execute("SELECT payload FROM contexts WHERE id=?", (context_id,)).fetchone()[0]
        files = [
            dict(zip(names, row, strict=True))
            for row in conn.execute(
                "SELECT id,sha256,name,media_type,size,created_at FROM files WHERE context_id=? "
                "ORDER BY rowid",
                (context_id,),
            )
        ]
        values = _store_parts(conn, context_id, created_at, text, files, cache)
        if payload_text(conn, context_id, values[0]) != text:
            raise sqlite3.IntegrityError(f"Context {context_id} was not reproduced exactly.")
        conn.execute(
            "INSERT INTO temp.context_frames VALUES(?,?,?,?,?,?,?,?,?)", (context_id, *values)
        )
    conn.execute("DELETE FROM files WHERE context_id IS NOT NULL")
    conn.execute("ALTER TABLE contexts DROP COLUMN payload")
    for column in CONTEXT_COLUMNS:
        conn.execute("ALTER TABLE contexts ADD COLUMN " + column)
    conn.execute(
        f"UPDATE contexts SET ({_STORED})=(SELECT {_STORED} FROM temp.context_frames f "
        "WHERE f.id=contexts.id)"
    )
    conn.execute("DROP TABLE temp.context_frames")
