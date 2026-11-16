"""The demo marker, and the raw-SQL dating that only a file carrying it accepts."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from ..common import encode, now

# The settings key of the demo marker.
MARKER = "demo"
# A workspace with any of these is not new, so it never becomes a demo.
CONTENT = ("jobs", "sources", "applications", "knowledge", "templates")

# Columns stamped with the moment of the change that wrote them.
STAMPED = (
    ("jobs", "created_at"),
    ("jobs", "updated_at"),
    ("jobs", "dismissed_at"),
    ("postings", "first_seen_at"),
    ("postings", "last_seen_at"),
    ("applications", "created_at"),
    ("applications", "updated_at"),
    ("notes", "created_at"),
    ("notes", "updated_at"),
    ("replies", "created_at"),
    ("replies", "updated_at"),
    ("documents", "created_at"),
    ("files", "created_at"),
    ("knowledge", "created_at"),
    ("knowledge", "updated_at"),
    ("claims", "created_at"),
    ("claims", "updated_at"),
    ("templates", "created_at"),
    ("templates", "updated_at"),
    ("sources", "created_at"),
    ("sources", "updated_at"),
    ("sources", "last_scheduled_at"),
)


class NotADemo(RuntimeError):
    """The workspace is not one the demo created: its dates are never rewritten."""


def is_demo(db):
    """Whether this file carries the demo marker."""
    return db.one("SELECT 1 FROM settings WHERE key=?", (MARKER,)) is not None


def mark_demo(workspace):
    """Write the demo marker on a new, empty workspace; refuse any other."""
    if is_demo(workspace.db):
        return
    with workspace.db.transaction() as conn:
        for table in CONTENT:
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise NotADemo("Only a new, empty workspace becomes the demo workspace.")
        conn.execute(
            "INSERT INTO settings(key,data,updated_at) VALUES(?,?,?)",
            (MARKER, encode({"created_at": now()}), now()),
        )


def stamp(db, start, when):
    """Date every record written since ``start`` at ``when``, keeping the order of its events.

    Raw SQL on a demo file only: a workspace without the marker is refused.
    """
    if not is_demo(db):
        raise NotADemo("Dates are rewritten only in a workspace the demo created.")
    with db.transaction() as conn:
        for table, column in STAMPED:
            conn.execute(
                f"UPDATE {table} SET {column}=? WHERE {column}>=?",
                (when.isoformat(timespec="microseconds"), start),
            )
        rows = conn.execute(
            "SELECT id FROM events WHERE created_at>=? ORDER BY rowid", (start,)
        ).fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                "UPDATE events SET created_at=? WHERE id=?",
                ((when + timedelta(seconds=index)).isoformat(timespec="microseconds"), row["id"]),
            )


@contextmanager
def moment(db, **delta):
    """Date what the block writes ``delta`` ago, keeping the order of its events."""
    start = datetime.now(UTC).isoformat(timespec="microseconds")
    yield
    stamp(db, start, datetime.now(UTC) - timedelta(**delta))


def ago(**delta):
    return (datetime.now(UTC) - timedelta(**delta)).isoformat(timespec="microseconds")
