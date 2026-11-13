"""Schema 13 to 14, the jobs part: the manual availability field becomes a note.

``jobs.availability`` was a manual value (``open``, ``closed`` or the default
``unknown``) that nothing read; 0.21 deprecated it in favour of the "no longer
listed" signal and 0.23 drops the column. A job whose value is anything but
``unknown`` (or empty) keeps it as one note on the job, ``origin='upgrade'``,
whose text names the value exactly (``note_body``). The note is attributed to
the actor and run of the last recorded change that set the field (the last
``job_edited`` event naming ``availability``) and dated by it, else by the
job's last change; a change recorded before 0.17 has no author. The note is not
pinned. No event is written and no other value changes.
"""

import sqlite3

from ..common import new_id

# Values that carry no information: the column's default, and an empty text.
EMPTY = ("unknown", "")

# The change that last set a job's availability: the newest edit naming the field.
_LAST_CHANGE = (
    "SELECT e.created_at,e.actor_kind,e.actor_id,e.actor_name,e.actor_token_kind,e.run_id "
    "FROM events e WHERE e.job_id=? AND e.application_id IS NULL AND e.kind='job_edited' "
    "AND json_valid(e.payload) AND json_type(e.payload,'$.fields')='array' AND "
    "EXISTS(SELECT 1 FROM json_each(e.payload,'$.fields') f WHERE f.value='availability') "
    "ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1"
)


def note_body(value):
    """The note that keeps a job's availability, with the value exactly as stored."""
    return (
        f"Availability (recorded by hand before 0.23): {value}\n\n"
        "0.23 removed this field. Whether the source still lists the posting is "
        "the No longer listed signal."
    )


def kept(conn):
    """The jobs whose availability carries a value, as (id, value, updated_at)."""
    marks = ",".join("?" for _ in EMPTY)
    return conn.execute(
        f"SELECT id,availability,updated_at FROM jobs WHERE availability IS NOT NULL "
        f"AND availability NOT IN ({marks}) ORDER BY rowid",
        EMPTY,
    ).fetchall()


def migrate(conn):
    """Keep each job's availability value as a note, check every copy, then drop the column."""
    if "availability" not in {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}:
        return 0
    jobs = kept(conn)
    notes = {}
    for job_id, value, updated_at in jobs:
        change = conn.execute(_LAST_CHANGE, (job_id,)).fetchone()
        stamp = change[0] if change else updated_at
        author = tuple(change[1:5]) if change else (None, None, None, None)
        run_id = change[5] if change else None
        note_id = new_id()
        conn.execute(
            "INSERT INTO notes(id,job_id,application_id,body,version,created_at,updated_at,"
            "author_kind,author_id,author_name,author_token_kind,run_id,pinned_at,origin) "
            "VALUES(?,?,NULL,?,1,?,?,?,?,?,?,?,NULL,'upgrade')",
            (note_id, job_id, note_body(value), stamp, stamp, *author, run_id),
        )
        notes[note_id] = note_body(value)
    # Every value must be readable from its note, byte for byte, before the column goes.
    for note_id, body in notes.items():
        stored = conn.execute(
            "SELECT CAST(body AS BLOB) FROM notes WHERE id=?", (note_id,)
        ).fetchone()
        if stored is None or stored[0] != body.encode():
            raise sqlite3.IntegrityError("A job's availability was not kept exactly.")
    conn.execute("ALTER TABLE jobs DROP COLUMN availability")
    return len(jobs)
