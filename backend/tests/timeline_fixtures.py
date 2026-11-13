"""Schema 12: a workspace whose application note is a column and whose notes have no pin or run."""

import sqlite3
from contextlib import closing

from openings.db import APPLICATIONS

# What schema 13 added to the notes of a schema 12 file (the timeline part).
SCHEMA_THIRTEEN_NOTE_COLUMNS = ("run_id", "pinned_at", "origin")
SCHEMA_THIRTEEN_INDEXES = ("notes_pinned_application", "notes_pinned_job", "notes_run")
# The notes table as released with schema 8 to 12.
NOTES_TWELVE = """CREATE TABLE notes (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 application_id TEXT REFERENCES applications(id) ON DELETE CASCADE, body TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 author_kind TEXT, author_id TEXT, author_name TEXT, author_token_kind TEXT
)"""
NOTE_COLUMNS_TWELVE = (
    "id,job_id,application_id,body,version,created_at,updated_at,"
    "author_kind,author_id,author_name,author_token_kind"
)


def undo_timeline(conn):
    """Move each application's pinned note back into applications.note, as schema 12 kept it.

    The pinned note and the record of writing it are removed: in schema 12 the
    text was a field of the application. Notes lose their run, pin and origin.
    """
    if (
        conn.execute(
            "SELECT count(*) FROM notes WHERE pinned_at IS NOT NULL AND application_id IS NULL"
        ).fetchone()[0]
        or conn.execute(
            "SELECT count(*) FROM events WHERE kind IN ('note_pinned','note_unpinned')"
        ).fetchone()[0]
    ):
        raise ValueError("A schema 12 workspace has no pinned job note and no pin change.")
    columns = [row[1] for row in conn.execute("PRAGMA table_info(applications)")]
    indexes = conn.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name='applications' AND type='index' "
        "AND sql IS NOT NULL ORDER BY rowid"
    ).fetchall()
    # Keep the references other tables hold to "applications" while it is rebuilt.
    conn.execute("PRAGMA legacy_alter_table=ON")
    conn.execute("ALTER TABLE applications RENAME TO applications_current")
    conn.execute(APPLICATIONS.format(name="applications"))
    names = ",".join(columns)
    conn.execute(
        f"INSERT INTO applications(rowid,{names},note) SELECT a.rowid,"
        + ",".join("a." + name for name in columns)
        + ",coalesce((SELECT n.body FROM notes n WHERE n.application_id=a.id "
        "AND n.pinned_at IS NOT NULL),'') FROM applications_current a ORDER BY a.rowid"
    )
    conn.execute("DROP TABLE applications_current")
    for (sql,) in indexes:
        conn.execute(sql)
    pinned = "SELECT id FROM notes WHERE pinned_at IS NOT NULL"
    conn.execute(f"DELETE FROM events WHERE subject_type='note' AND subject_id IN ({pinned})")
    conn.execute(f"DELETE FROM notes WHERE id IN ({pinned})")
    for index in SCHEMA_THIRTEEN_INDEXES:
        conn.execute(f"DROP INDEX IF EXISTS {index}")
    # A column with a foreign key cannot be dropped, so the table is rebuilt.
    conn.execute("ALTER TABLE notes RENAME TO notes_current")
    conn.execute(NOTES_TWELVE)
    conn.execute(
        f"INSERT INTO notes(rowid,{NOTE_COLUMNS_TWELVE}) "
        f"SELECT rowid,{NOTE_COLUMNS_TWELVE} FROM notes_current ORDER BY rowid"
    )
    conn.execute("DROP TABLE notes_current")
    conn.execute("CREATE INDEX notes_job ON notes(job_id,created_at)")
    conn.execute("CREATE INDEX notes_app ON notes(application_id)")
    conn.execute("PRAGMA legacy_alter_table=OFF")


def older_rows(conn, table, added=()):
    """Rows of a table as an upgrade to schema 13 must keep them, ordered by the first column.

    Columns in ``added`` (added since the older schema), the notes columns of
    schema 13, ``applications.note`` (moved to a pinned note) and the notes the
    upgrade copied from it are left out, so the same call compares an older file
    with its upgraded copy.
    """
    present = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    skipped = set(added) | set(SCHEMA_THIRTEEN_NOTE_COLUMNS if table == "notes" else ())
    if table == "applications":
        skipped.add("note")
    names = ",".join(f'"{name}"' for name in present if name not in skipped)
    copied = " WHERE origin<>'upgrade'" if table == "notes" and "origin" in present else ""
    return conn.execute(f"SELECT {names} FROM {table}{copied} ORDER BY 1").fetchall()


def make_schema_twelve(path):
    """Remove what schema 13 added from a current workspace file, keeping every other value."""
    with closing(sqlite3.connect(path)) as conn:
        undo_timeline(conn)
        conn.execute("PRAGMA user_version=12")
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")
