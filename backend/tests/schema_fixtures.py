"""Turn a current workspace file into an earlier released layout, keeping its rows."""

import sqlite3
from contextlib import closing

SCHEMA_EIGHT_TABLES = ("questions", "runs")
SCHEMA_EIGHT_COLUMNS = {
    "events": ("subject_type", "subject_id", "actor_kind", "actor_id", "actor_name", "run_id"),
    "notes": ("author_kind", "author_id", "author_name"),
    "applications": ("ready_at", "ready_by_kind", "ready_by_id", "ready_by_name"),
}
SCHEMA_EIGHT_INDEXES = ("events_run", "events_subject", "applications_ready")
# The events table as released with schema 7.
EVENTS_SEVEN = """CREATE TABLE events (
 id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
)"""


def make_schema_seven(path):
    """Remove attribution, runs, questions and the Ready step (schema 8) from a current workspace file."""
    with closing(sqlite3.connect(path)) as conn:
        for table in SCHEMA_EIGHT_TABLES:
            conn.execute(f"DROP TABLE {table}")
        for index in SCHEMA_EIGHT_INDEXES:
            conn.execute(f"DROP INDEX {index}")
        # A column with a foreign key cannot be dropped, so the table is rebuilt.
        conn.execute("ALTER TABLE events RENAME TO events_current")
        conn.execute(EVENTS_SEVEN)
        conn.execute(
            "INSERT INTO events SELECT id,job_id,application_id,kind,payload,created_at "
            "FROM events_current ORDER BY rowid"
        )
        conn.execute("DROP TABLE events_current")
        conn.execute("CREATE INDEX events_app ON events(application_id,created_at)")
        conn.execute("CREATE INDEX events_job ON events(job_id)")
        conn.execute("CREATE INDEX events_created ON events(created_at)")
        for table in ("notes", "applications"):
            for column in SCHEMA_EIGHT_COLUMNS[table]:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        conn.execute("PRAGMA user_version=7")
        conn.commit()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")


def columns(conn, table):
    return [tuple(row)[1:] for row in conn.execute(f"PRAGMA table_info({table})")]


def table_names(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def index_names(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
    }
