"""Schema 13: a workspace whose jobs keep a manual availability and whose Profile keeps
preferences and roles, as 0.22 stored them."""

import json
import sqlite3
from contextlib import closing

from openings.db import encode


def undo_compat(conn, availability=None, profile=None):
    """Put back what schema 14 removed: ``jobs.availability`` and the two Profile fields.

    ``availability`` maps job ids to the value each one had (every other job has
    the default ``unknown``); ``profile`` gives the stored Profile ``preferences``
    and ``roles`` (a Profile saved by 0.22 stored both, empty by default).
    """
    conn.execute("ALTER TABLE jobs ADD COLUMN availability TEXT NOT NULL DEFAULT 'unknown'")
    for job_id, value in (availability or {}).items():
        conn.execute("UPDATE jobs SET availability=? WHERE id=?", (value, job_id))
    if profile is None:
        return
    row = conn.execute("SELECT data FROM settings WHERE key='profile'").fetchone()
    data = {**(json.loads(row[0]) if row else {}), "preferences": "", "roles": "", **profile}
    if row is None:
        conn.execute(
            "INSERT INTO settings(key,data,version,updated_at) VALUES('profile',?,1,"
            "'2026-11-01T08:00:00.000000+00:00')",
            (encode(data),),
        )
    else:
        conn.execute("UPDATE settings SET data=? WHERE key='profile'", (encode(data),))


def make_schema_thirteen(path, availability=None, profile=None):
    """Remove what schema 14 removed from a current workspace file, keeping every other value."""
    with closing(sqlite3.connect(path)) as conn:
        undo_compat(conn, availability, profile)
        conn.execute("PRAGMA user_version=13")
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")
