"""Give free pages back to the data volume after a large reduction.

SQLite keeps the pages a deletion or a storage upgrade frees inside the file, and
the online backup copies them. When at least a quarter of the file (and
``OPENINGS_COMPACT_MIN_MB``, default 32) is free, the database is rewritten: a
compact copy is written beside it with ``VACUUM INTO`` and copied back with the
online backup API in one transaction. An interruption at any point leaves the
previous file valid; the next start tries again. Without enough free disk the step
is skipped and the free pages are reused by later writes.
"""

import logging
import os
import shutil
import sqlite3
from contextlib import closing

LOG = logging.getLogger(__name__)
# The copy and the write-ahead log of copying it back each take the compact size.
ROOM_FACTOR = 2
ROOM_MARGIN = 64 * 1024**2


def free_space(conn):
    """Return (free bytes inside the file, file bytes)."""
    page = conn.execute("PRAGMA page_size").fetchone()[0]
    return (
        conn.execute("PRAGMA freelist_count").fetchone()[0] * page,
        conn.execute("PRAGMA page_count").fetchone()[0] * page,
    )


def _job_rows(conn):
    return tuple(conn.execute("SELECT count(*),coalesce(sum(rowid),0) FROM jobs").fetchone())


def compact(db):
    """Rewrite the workspace file without free pages; return the bytes given back."""
    minimum = int(os.environ.get("OPENINGS_COMPACT_MIN_MB", "32")) * 1024**2
    name = None
    try:
        with db.lock, db.connect() as conn:
            free, total = free_space(conn)
            if free < minimum or free * 4 < total:
                return 0
            needed = ROOM_FACTOR * (total - free) + ROOM_MARGIN
            if shutil.disk_usage(db.path.parent).free < needed:
                LOG.warning(
                    "Database not compacted: %d MB are free inside the file, but rewriting it "
                    "needs %d MB of free disk space.",
                    free // 1024**2,
                    needed // 1024**2,
                )
                return 0
            name = db.temp_file("compact")
            os.unlink(name)
            conn.execute("VACUUM INTO ?", (name,))
            with closing(sqlite3.connect(name)) as copy:
                if copy.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError("The compact copy failed its integrity check.")
                if _job_rows(copy) != _job_rows(conn):
                    # The search index addresses jobs by rowid; rebuild it if they moved.
                    copy.execute("INSERT INTO jobs_fts(jobs_fts) VALUES('rebuild')")
                    copy.commit()
                copy.backup(conn)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            LOG.info("Database compacted: %d MB given back to the data volume.", free // 1024**2)
            return free
    except (sqlite3.Error, OSError) as error:
        LOG.warning("Database not compacted: %s", error)
        return 0
    finally:
        if name:
            db.remove_temp(name)
