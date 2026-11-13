"""Schema 9 to 10: the policy tables and the Profile values copied into them."""

from __future__ import annotations

import json

from ..actors import SYSTEM
from ..common import new_id, now
from .models import STRUCTURED
from .records import label_from_key

# Mirrored in schema.sql; the 9 -> 10 migration creates the same objects.
SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_sections (
 section TEXT PRIMARY KEY CHECK(section IN ('decision','eligibility','writing','facts')),
 version INTEGER NOT NULL DEFAULT 0, updated_at TEXT,
 updated_by_kind TEXT, updated_by_id TEXT, updated_by_name TEXT, updated_by_token_kind TEXT
);
CREATE TABLE IF NOT EXISTS policy_items (
 id TEXT PRIMARY KEY, section TEXT NOT NULL REFERENCES policy_sections(section),
 position INTEGER NOT NULL DEFAULT 0 CHECK(position>=0),
 label TEXT NOT NULL, statement TEXT NOT NULL DEFAULT '',
 value TEXT CHECK(value IS NULL OR json_valid(value)),
 value_type TEXT CHECK(value_type IS NULL OR value_type IN ('text','number','date','boolean','list','structured')),
 note TEXT NOT NULL DEFAULT '',
 scope TEXT CHECK(scope IS NULL OR scope IN ('cv','letter','all')),
 rule TEXT CHECK(rule IS NULL OR json_valid(rule)),
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 origin TEXT, origin_key TEXT,
 confirmed_at TEXT, confirmed_by_kind TEXT, confirmed_by_id TEXT, confirmed_by_name TEXT, confirmed_by_token_kind TEXT,
 created_by_kind TEXT, created_by_id TEXT, created_by_name TEXT, created_by_token_kind TEXT,
 updated_by_kind TEXT, updated_by_id TEXT, updated_by_name TEXT, updated_by_token_kind TEXT,
 idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((value IS NULL)=(value_type IS NULL))
);
CREATE INDEX IF NOT EXISTS policy_items_section ON policy_items(section,position);
INSERT OR IGNORE INTO policy_sections(section) VALUES ('decision'),('eligibility'),('writing'),('facts');
"""


def migrate_profile(conn):
    """Schema 9 to 10: create the policy and copy the Profile's free-form values into it.

    Every top-level Profile ``metadata`` key becomes one unconfirmed ``facts`` item
    holding the original value; ``preferences`` and ``roles`` text become one
    unconfirmed ``decision`` item each. The Profile row is not touched.
    """
    # executescript would commit the surrounding upgrade, so run each statement.
    for statement in SCHEMA.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    row = conn.execute("SELECT data,updated_at FROM settings WHERE key='profile'").fetchone()
    if row is None:
        return
    try:
        profile = json.loads(row[0])
    except ValueError:
        return
    if not isinstance(profile, dict):
        return
    stamp = now()
    insert = (
        "INSERT INTO policy_items(id,section,position,label,statement,value,value_type,origin,origin_key,"
        "created_by_kind,updated_by_kind,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    written = set()
    metadata = profile.get("metadata")
    for position, (key, value) in enumerate(metadata.items() if isinstance(metadata, dict) else ()):
        if isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, (int, float)):
            kind = "number"
        elif isinstance(value, str):
            kind = "text"
        else:
            kind = STRUCTURED
        conn.execute(
            insert,
            (
                new_id(),
                "facts",
                position,
                label_from_key(key),
                "",
                # The original value, in its own key order.
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                kind,
                "profile_metadata",
                key,
                SYSTEM.kind,
                SYSTEM.kind,
                stamp,
                stamp,
            ),
        )
        written.add("facts")
    position = 0
    for key, label in (("preferences", "Preferences"), ("roles", "Target roles")):
        text = profile.get(key)
        if isinstance(text, str) and text.strip():
            conn.execute(
                insert,
                (
                    new_id(),
                    "decision",
                    position,
                    label,
                    text,
                    None,
                    None,
                    "profile_" + key,
                    key,
                    SYSTEM.kind,
                    SYSTEM.kind,
                    stamp,
                    stamp,
                ),
            )
            position += 1
            written.add("decision")
    for section in written:
        conn.execute(
            "UPDATE policy_sections SET version=1,updated_at=?,updated_by_kind=? WHERE section=?",
            (stamp, SYSTEM.kind, section),
        )
