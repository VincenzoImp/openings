"""Backup copies stay on the data volume and restores bring current indexes."""

import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from openings.app import create_app
from openings.db import TEMP_PREFIX
from openings.operations import restore_database


def indexes(path):
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}


def test_restore_recreates_indexes_missing_from_an_older_backup(tmp_path):
    app = create_app(tmp_path / "data" / "live.sqlite", start_worker=False)
    workspace = app.state.workspace
    workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    backup = tmp_path / "older.sqlite"
    workspace.db.backup(backup)
    with sqlite3.connect(backup) as conn:
        conn.execute("DROP INDEX jobs_triage")
    assert "jobs_triage" not in indexes(backup)
    restore_database(workspace, backup)
    assert "jobs_triage" in indexes(workspace.db.path)
    assert not list(workspace.db.path.parent.glob(TEMP_PREFIX + "*"))


def test_temp_copies_live_beside_the_database_and_stale_ones_are_removed(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    stale = data / (TEMP_PREFIX + "restore-crashed.sqlite")
    stale.write_bytes(b"partial")
    app = create_app(data / "live.sqlite", start_worker=False)
    assert not stale.exists()
    name = Path(app.state.workspace.db.temp_file("backup"))
    assert name.parent == data and name.name.startswith(TEMP_PREFIX)
    name.unlink()

    system_temp = set(Path(tempfile.gettempdir()).glob("openings-backup-*"))
    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        client.headers["X-CSRF-Token"] = session.json()["csrf_token"]
        response = client.get("/api/v1/backup")
        assert response.status_code == 200
        assert response.content.startswith(b"SQLite format 3\x00")
    assert set(Path(tempfile.gettempdir()).glob("openings-backup-*")) == system_temp
    assert not list(data.glob(TEMP_PREFIX + "*"))
