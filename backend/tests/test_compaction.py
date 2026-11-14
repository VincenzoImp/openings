"""Free pages left by an upgrade or large deletions go back to the data volume at start."""

import shutil
import sqlite3
from contextlib import closing

from openings import compaction
from openings.workspace import Workspace


def test_startup_compacts_a_mostly_free_file_and_keeps_search_working(tmp_path, monkeypatch):
    path = tmp_path / "compact.sqlite"
    workspace = Workspace(path)
    kept = workspace.ingest_job({"title": "Retained synthetic role", "posting": "Search me."})
    doomed = [
        workspace.ingest_job({"title": f"Removed role {index}", "posting": "Bulk. " * 30000})
        for index in range(12)
    ]
    for job in doomed:
        workspace.forget_job(job["id"], job["version"])
    with workspace.db.connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    large = path.stat().st_size
    with closing(sqlite3.connect(path)) as conn:
        free, total = compaction.free_space(conn)
    assert free * 4 >= total

    # Below the configured minimum nothing is rewritten.
    assert compaction.compact(workspace.db) == 0 and path.stat().st_size == large
    # Without room for the copy the file is left as it is.
    monkeypatch.setenv("OPENINGS_COMPACT_MIN_MB", "0")
    monkeypatch.setattr(
        compaction.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10, 10, 0)
    )
    assert compaction.compact(workspace.db) == 0 and path.stat().st_size == large
    monkeypatch.undo()

    monkeypatch.setenv("OPENINGS_COMPACT_MIN_MB", "0")
    reopened = Workspace(path)
    assert path.stat().st_size < large / 2
    assert not list(tmp_path.glob(".openings-temp-*"))
    with reopened.db.connect() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA freelist_count").fetchone()[0] == 0
    assert [item["id"] for item in reopened.list_jobs(q="Retained")["items"]] == [kept["id"]]
    added = reopened.ingest_job({"title": "Later synthetic role", "posting": "Still writable."})
    assert reopened.list_jobs(q="Later")["items"][0]["id"] == added["id"]
