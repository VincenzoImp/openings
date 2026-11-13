"""Schema 10: a workspace without employer responses and the no_response outcome."""

import sqlite3
from contextlib import closing

# Columns schema 11 added to existing tables.
SCHEMA_ELEVEN_COLUMNS = {"applications": ("concluded_on",)}
# The applications table and its indexes as released with schema 10 (0.19).
APPLICATIONS_TEN = """CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','applied','interview','offer','closed')),
 outcome TEXT CHECK(outcome IS NULL OR outcome IN ('accepted','rejected','not_pursued')),
 note TEXT NOT NULL DEFAULT '', questions TEXT NOT NULL DEFAULT '[]', answers TEXT NOT NULL DEFAULT '{}',
 version INTEGER NOT NULL DEFAULT 1, idempotency_key TEXT UNIQUE, applied_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 priority INTEGER CHECK(priority IS NULL OR priority BETWEEN 1 AND 5),
 deadline TEXT CHECK(deadline IS NULL OR (length(deadline)=10 AND date(deadline)=deadline)),
 requirements TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(requirements) AND json_type(requirements)='array'),
 ready_at TEXT, ready_by_kind TEXT, ready_by_id TEXT, ready_by_name TEXT, ready_by_token_kind TEXT
)"""
INDEXES_TEN = (
    "CREATE INDEX applications_job ON applications(job_id,created_at DESC,id DESC)",
    "CREATE UNIQUE INDEX applications_active_job ON applications(job_id) WHERE status<>'closed'",
    "CREATE INDEX applications_status ON applications(status,updated_at)",
    "CREATE INDEX applications_deadline ON applications(deadline)",
    "CREATE INDEX applications_ready ON applications(ready_at) WHERE ready_at IS NOT NULL",
)
COLUMNS_TEN = (
    "id,job_id,status,outcome,note,questions,answers,version,idempotency_key,applied_at,"
    "created_at,updated_at,priority,deadline,requirements,ready_at,ready_by_kind,ready_by_id,"
    "ready_by_name,ready_by_token_kind"
)


def make_schema_ten(path):
    """Remove what schema 11 added from a current workspace file, keeping every other value.

    The applications table is built again with the released definition, so the
    file is what 0.19 wrote: an upgrade test then sees the table it rebuilds.
    """
    with closing(sqlite3.connect(path)) as conn:
        if conn.execute("SELECT count(*) FROM applications WHERE outcome='no_response'").fetchone()[
            0
        ]:
            raise ValueError("A schema 10 workspace cannot hold the no_response outcome.")
        conn.execute("DROP TABLE responses")
        # Schema 10 never recorded a response, so it has no event of one either.
        conn.execute("DELETE FROM events WHERE subject_type='response'")
        # Keep the references other tables hold to "applications" while it is rebuilt.
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("ALTER TABLE applications RENAME TO applications_current")
        conn.execute(APPLICATIONS_TEN)
        conn.execute(
            f"INSERT INTO applications(rowid,{COLUMNS_TEN}) "
            f"SELECT rowid,{COLUMNS_TEN} FROM applications_current ORDER BY rowid"
        )
        conn.execute("DROP TABLE applications_current")
        for index in INDEXES_TEN:
            conn.execute(index)
        conn.execute("PRAGMA legacy_alter_table=OFF")
        conn.execute("PRAGMA user_version=10")
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")
