"""Schema 11: a workspace without skill notes, ingest signals, dismissal records and listing observations."""

import sqlite3
from contextlib import closing

from timeline_fixtures import make_schema_twelve

# What schema 12 (0.21) added to a schema 11 file.
# skill_notes is the local notes of skills (#168), job_signals the ingest signals (#166).
SCHEMA_TWELVE_TABLES = ("job_signals", "skill_notes")
SCHEMA_TWELVE_INDEXES = (
    "job_signals_duplicate",
    "job_signals_language",
    "postings_unlisted",
    "jobs_dismissed_rule",
)
SCHEMA_TWELVE_COLUMNS = {
    "jobs": (
        "dismissed_at",
        "dismissed_by_kind",
        "dismissed_by_id",
        "dismissed_by_name",
        "dismissed_by_token_kind",
        "dismissed_rule_id",
        "dismissed_rule_label",
        "dismissed_reason",
    ),
    "postings": ("unlisted_at",),
}


def make_schema_eleven(path):
    """Remove what schema 12 added from a current workspace file, keeping every other value."""
    make_schema_twelve(path)  # first undo schema 13
    with closing(sqlite3.connect(path)) as conn:
        if conn.execute(
            "SELECT count(*) FROM events WHERE kind IN ('duplicate_cleared','skill_notes_updated') OR "
            "(kind='triage_changed' AND json_extract(payload,'$.rule') IS NOT NULL)"
        ).fetchone()[0]:
            raise ValueError("A schema 11 workspace holds no rule dismissal or duplicate decision.")
        for index in SCHEMA_TWELVE_INDEXES:
            conn.execute(f"DROP INDEX IF EXISTS {index}")
        for table in SCHEMA_TWELVE_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        for table, names in SCHEMA_TWELVE_COLUMNS.items():
            for name in names:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")
        conn.execute("PRAGMA user_version=11")
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")
