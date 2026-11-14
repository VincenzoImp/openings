"""Backup copies stay on the data volume and leave no sidecars."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from openings.app import create_app
from openings.db import TEMP_PREFIX


def test_temp_copies_live_beside_the_database_and_leave_nothing_behind(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    stale = data / (TEMP_PREFIX + "restore-crashed.sqlite")
    stale.write_bytes(b"partial")
    app = create_app(data / "live.sqlite", start_worker=False)
    assert not stale.exists()
    name = Path(app.state.workspace.db.temp_file("backup"))
    assert name.parent == data and name.name.startswith(TEMP_PREFIX)
    name.unlink()
    app.state.workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})

    system_temp = set(Path(tempfile.gettempdir()).glob("openings-backup-*"))
    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        client.headers["X-CSRF-Token"] = session.json()["csrf_token"]
        response = client.get("/api/v1/backup")
        assert response.status_code == 200
        assert response.content.startswith(b"SQLite format 3\x00")
        assert set(Path(tempfile.gettempdir()).glob("openings-backup-*")) == system_temp
        assert not list(data.glob(TEMP_PREFIX + "*"))
        # The restore route leaves no WAL sidecars of its upload.
        restored = client.post(
            "/api/v1/backup/restore",
            content=response.content,
            headers={"Content-Type": "application/vnd.sqlite3"},
        )
        assert restored.status_code == 200, restored.text
    assert not list(data.glob(TEMP_PREFIX + "*"))
