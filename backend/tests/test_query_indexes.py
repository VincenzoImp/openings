"""Hot reads and cascade deletes use indexes instead of full table scans."""

import sqlite3

import pytest

from openings.app import create_app

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
    # The default order of the jobs list (jobs_list sort=newest).
    ("SELECT j.id FROM jobs j ORDER BY j.created_at DESC,j.id LIMIT 50 OFFSET 0", "j"),
    # Attribution, runs and questions (schema 8).
    ("SELECT id FROM runs WHERE token_id=? AND status='open'", "runs"),
    ("SELECT * FROM runs WHERE token_id=? ORDER BY started_at DESC LIMIT 50", "runs"),
    ("SELECT * FROM runs WHERE status=? ORDER BY started_at DESC LIMIT 50", "runs"),
    ("SELECT * FROM runs ORDER BY started_at DESC LIMIT 50", "runs"),
    ("SELECT * FROM events WHERE run_id=? ORDER BY created_at DESC LIMIT 50", "events"),
    (
        "SELECT * FROM events WHERE subject_type=? AND subject_id=? ORDER BY created_at DESC",
        "events",
    ),
    ("SELECT * FROM questions WHERE state=? ORDER BY created_at DESC LIMIT 50", "questions"),
    (
        "SELECT * FROM questions WHERE state='answered' AND resolved_at>=? ORDER BY resolved_at",
        "questions",
    ),
    ("SELECT count(*) FROM questions WHERE run_id=?", "questions"),
    ("SELECT id FROM questions WHERE job_id=?", "questions"),
    ("SELECT id FROM questions WHERE application_id=?", "questions"),
    ("SELECT id FROM questions WHERE knowledge_id=?", "questions"),
    # The ready queue and requests for the agent (schema 8).
    ("SELECT * FROM requests WHERE state=? ORDER BY created_at DESC LIMIT 50", "requests"),
    ("SELECT count(*) FROM requests WHERE state='open'", "requests"),
    ("SELECT * FROM requests ORDER BY created_at DESC LIMIT 50", "requests"),
    ("SELECT * FROM requests WHERE updated_at>=? ORDER BY updated_at LIMIT 50", "requests"),
    ("SELECT count(*) FROM requests WHERE run_id=?", "requests"),
    ("SELECT id FROM requests WHERE job_id=?", "requests"),
    ("SELECT id FROM requests WHERE application_id=?", "requests"),
    ("SELECT id FROM requests WHERE knowledge_id=?", "requests"),
]


@pytest.mark.parametrize(("sql", "table"), QUERIES)
def test_query_does_not_scan_table(tmp_path, sql, table):
    path = tmp_path / "indexes.sqlite"
    create_app(path, start_worker=False)
    with sqlite3.connect(path) as conn:
        plan = conn.execute("EXPLAIN QUERY PLAN " + sql, ("x",) * sql.count("?")).fetchall()
    details = [row[-1] for row in plan]
    full_scans = [d for d in details if d.startswith(f"SCAN {table}") and "USING" not in d]
    assert not full_scans, details
    assert not any("TEMP B-TREE" in detail for detail in details), details
