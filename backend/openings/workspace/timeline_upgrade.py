"""Schema 12 to 13, the timeline part: note authors' runs, pinned notes, the application note.

Notes gain the run their author had open (``run_id``), a pin (``pinned_at``; at
most one pinned note per job and per application, partial unique indexes) and
an ``origin`` (``manual`` or ``upgrade``). Every non-empty ``applications.note``
becomes one pinned note of its application with exactly the same text, and the
column is dropped: the note is now the one place that text lives. The pinned
note is attributed to the actor (and run) of the last recorded change that set
the text: the last ``application_updated`` event naming the ``note`` field,
else the ``application_created`` event. It is dated by that change, else by the
application's last change. Without such an event, or for a change recorded
before 0.17, the author is unknown. No event is written and no other value
changes.
"""

import sqlite3

from ..common import new_id

NOTE_COLUMNS = (
    "run_id TEXT REFERENCES runs(id) ON DELETE SET NULL",
    "pinned_at TEXT",
    "origin TEXT NOT NULL DEFAULT 'manual' CHECK(origin IN ('manual','upgrade'))",
)

# Mirrored in schema.sql.
INDEXES = """
CREATE UNIQUE INDEX IF NOT EXISTS notes_pinned_application ON notes(application_id) WHERE pinned_at IS NOT NULL AND application_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS notes_pinned_job ON notes(job_id) WHERE pinned_at IS NOT NULL AND application_id IS NULL;
CREATE INDEX IF NOT EXISTS notes_run ON notes(run_id);
"""

# The change that last set an application's note: the newest update naming the
# field, else its creation.
_LAST_CHANGE = (
    "SELECT e.created_at,e.actor_kind,e.actor_id,e.actor_name,e.actor_token_kind,e.run_id "
    "FROM events e WHERE e.application_id=? AND (e.kind='application_created' OR "
    "(e.kind='application_updated' AND json_valid(e.payload) AND "
    "json_type(e.payload,'$.fields')='array' AND "
    "EXISTS(SELECT 1 FROM json_each(e.payload,'$.fields') f WHERE f.value='note'))) "
    "ORDER BY e.kind='application_updated' DESC,e.created_at DESC,e.rowid DESC LIMIT 1"
)


def migrate(conn):
    """Add the note columns, move each application note to a pinned note and drop the column."""
    for column in NOTE_COLUMNS:
        conn.execute("ALTER TABLE notes ADD COLUMN " + column)
    applications = conn.execute(
        "SELECT id,job_id,note,updated_at FROM applications WHERE note<>'' ORDER BY rowid"
    ).fetchall()
    for application_id, job_id, text, updated_at in applications:
        change = conn.execute(_LAST_CHANGE, (application_id,)).fetchone()
        stamp = change[0] if change else updated_at
        author = tuple(change[1:5]) if change else (None, None, None, None)
        run_id = change[5] if change else None
        conn.execute(
            "INSERT INTO notes(id,job_id,application_id,body,version,created_at,updated_at,"
            "author_kind,author_id,author_name,author_token_kind,run_id,pinned_at,origin) "
            "VALUES(?,?,?,?,1,?,?,?,?,?,?,?,?,'upgrade')",
            (new_id(), job_id, application_id, text, stamp, stamp, *author, run_id, stamp),
        )
    copied = conn.execute(
        "SELECT count(*) FROM applications a JOIN notes n ON n.application_id=a.id "
        "AND n.origin='upgrade' AND n.pinned_at IS NOT NULL "
        "WHERE CAST(n.body AS BLOB)=CAST(a.note AS BLOB)"
    ).fetchone()[0]
    if copied != len(applications):
        raise sqlite3.IntegrityError("An application note was not copied exactly.")
    conn.execute("ALTER TABLE applications DROP COLUMN note")
    # executescript would commit the surrounding upgrade, so run each statement.
    for statement in INDEXES.split(";\n"):
        if statement.strip():
            conn.execute(statement)
