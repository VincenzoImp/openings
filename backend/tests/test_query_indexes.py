"""Hot reads and cascade deletes use indexes instead of full table scans."""

import sqlite3

from openings.discovery.sources import SOURCE_COUNTS

QUERIES = [
    (
        (
            "SELECT d.id FROM documents d WHERE d.application_id=? "
            "AND NOT EXISTS(SELECT 1 FROM documents child WHERE child.previous_id=d.id)"
        ),
        "child",
    ),
    ("SELECT * FROM events ORDER BY created_at DESC LIMIT 12", "events"),
    ("SELECT id FROM events WHERE job_id=?", "events"),
    ("SELECT * FROM notes WHERE job_id=? ORDER BY created_at DESC", "notes"),
    ("SELECT id FROM notes WHERE application_id=?", "notes"),
    ("SELECT id FROM files WHERE job_id=?", "files"),
    ("SELECT id FROM files WHERE sha256=?", "files"),
    ("SELECT id FROM tasks WHERE job_id=?", "tasks"),
    ("SELECT id FROM tasks WHERE source_id=?", "tasks"),
    ("SELECT id FROM postings WHERE source_id=?", "postings"),
    # Per-source counts of sources_list (#211).
    (SOURCE_COUNTS.format(ids="?"), "p"),
    # The default order of the jobs list (jobs_list sort=newest).
    ("SELECT j.id FROM jobs j ORDER BY j.created_at DESC,j.id LIMIT 50 OFFSET 0", "j"),
    # Attribution: the changes of one call, and of one record.
    ("SELECT * FROM events WHERE batch_id=? ORDER BY created_at DESC LIMIT 50", "events"),
    (
        "SELECT * FROM events WHERE subject_type=? AND subject_id=? ORDER BY created_at DESC",
        "events",
    ),
]


def test_queries_do_not_scan_their_table(database_path):
    with sqlite3.connect(database_path) as conn:
        for sql, table in QUERIES:
            plan = conn.execute("EXPLAIN QUERY PLAN " + sql, ("x",) * sql.count("?")).fetchall()
            details = [row[-1] for row in plan]
            full_scans = [d for d in details if d.startswith(f"SCAN {table}") and "USING" not in d]
            assert not full_scans, (sql, details)
            assert not any("TEMP B-TREE" in detail for detail in details), (sql, details)
