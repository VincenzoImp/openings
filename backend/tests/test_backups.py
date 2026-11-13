"""Pre-upgrade copies, scheduled local backups and the owner's access to them (#205)."""

import asyncio
import os
import shutil
import sqlite3
import stat
import threading
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from openings import backups, compaction, db as db_module
from openings.app import create_app
from openings.db import SCHEMA_VERSION, Database
from openings.errors import DomainError
from openings.worker import Worker
from openings.workspace import Workspace

PASSWORD = "synthetic-password"


def older(path, version=13):
    """A workspace file marked with an earlier schema: what an in-place upgrade copies first."""
    workspace = Workspace(path)
    workspace.ingest_job({"title": "Synthetic engineer", "company": "Example", "posting": "APIs."})
    del workspace
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(f"PRAGMA user_version={version}")
        conn.commit()
        conn.execute("PRAGMA journal_mode=DELETE")
    return path


def no_room(monkeypatch, free=0):
    monkeypatch.setattr(
        compaction.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10, 10, free)
    )


def opened_version(path):
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        return conn.execute("PRAGMA user_version").fetchone()[0]


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


# Pre-upgrade copies


def test_a_verified_private_copy_is_kept_at_the_old_version(tmp_path):
    path = older(tmp_path / "openings.sqlite")
    before = path.read_bytes()
    copy = db_module.copy_before_upgrade(path, 13)
    assert db_module.pre_upgrade_copies(path) == [copy]
    assert copy.name.startswith("openings.pre-schema13-") and copy.suffix == ".sqlite"
    assert opened_version(copy) == 13
    assert mode(copy) == 0o600
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".openings-temp-*"))
    with closing(sqlite3.connect(copy)) as conn:
        assert conn.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_a_fresh_workspace_takes_no_copy(tmp_path):
    Database(tmp_path / "openings.sqlite")
    assert not list(tmp_path.glob("*.pre-*"))


def test_an_unsupported_older_workspace_is_refused_without_a_copy(tmp_path):
    path = older(tmp_path / "openings.sqlite")
    before = path.read_bytes()
    with pytest.raises(DomainError) as refused:
        Database(path)
    assert refused.value.code == "schema_version"
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["openings.sqlite"]


def test_without_room_the_copy_is_refused_and_the_file_is_unchanged(tmp_path, monkeypatch):
    path = older(tmp_path / "openings.sqlite")
    before = path.read_bytes()
    no_room(monkeypatch, free=1024)
    with pytest.raises(DomainError) as refused:
        db_module.copy_before_upgrade(path, 13)
    assert refused.value.code == "upgrade_room"
    assert "MiB of free space" in refused.value.message
    assert refused.value.details["needed_bytes"] >= 2.2 * len(before)
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["openings.sqlite"]


def test_a_copy_that_cannot_be_kept_is_refused(tmp_path, monkeypatch):
    path = older(tmp_path / "openings.sqlite")
    before = path.read_bytes()

    def broken_rename(source, target):
        raise OSError("synthetic rename failure")

    monkeypatch.setattr(db_module.os, "replace", broken_rename)
    with pytest.raises(DomainError) as refused:
        db_module.copy_before_upgrade(path, 13)
    assert refused.value.code == "upgrade_copy"
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["openings.sqlite"]


def test_the_two_most_recent_pre_upgrade_copies_are_kept(tmp_path):
    path = older(tmp_path / "openings.sqlite")
    for stamp in ("20250101T000000Z", "20250201T000000Z", "20250301T000000Z"):
        shutil.copyfile(path, tmp_path / f"openings.pre-schema12-{stamp}.sqlite")
    # Another kind of kept copy (0.24's renamed original) is never rotated here.
    shutil.copyfile(path, tmp_path / "openings.pre-0.24.sqlite")
    db_module.copy_before_upgrade(path, 13)
    kept = [item.name for item in db_module.pre_upgrade_copies(path)]
    assert len(kept) == 2
    assert kept[0].startswith("openings.pre-schema13-")
    assert kept[1] == "openings.pre-schema12-20250301T000000Z.sqlite"
    assert (tmp_path / "openings.pre-0.24.sqlite").is_file()


# Scheduled backups


def test_a_backup_is_verified_private_and_rotated(tmp_path):
    workspace = Workspace(tmp_path / "openings.sqlite")
    directory = tmp_path / "backups"
    directory.mkdir(mode=0o700)
    for day in range(1, 5):
        (directory / f"openings-2025010{day}T000000Z.sqlite").write_bytes(b"old")
    (directory / ".openings-temp-backup-1-1.sqlite").write_bytes(b"interrupted")
    result = backups.run_backup(workspace.db, directory, 3)
    names = sorted(item.name for item in directory.iterdir())
    assert names == [
        "openings-20250103T000000Z.sqlite",
        "openings-20250104T000000Z.sqlite",
        result["name"],
    ]
    copy = directory / result["name"]
    assert opened_version(copy) == SCHEMA_VERSION
    assert mode(copy) == 0o600


def test_the_backup_directory_is_created_private(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "openings.sqlite")
    assert backups.backup_dir(workspace.db) == tmp_path / "backups"
    monkeypatch.setenv("OPENINGS_BACKUP_DIR", str(tmp_path / "elsewhere" / "copies"))
    directory = backups.backup_dir(workspace.db)
    assert directory == tmp_path / "elsewhere" / "copies"
    backups.run_backup(workspace.db, directory, 3)
    assert mode(directory) == 0o700
    assert len(backups.scheduled(directory)) == 1


def test_a_backup_without_room_is_skipped(tmp_path, monkeypatch, caplog):
    workspace = Workspace(tmp_path / "openings.sqlite")
    no_room(monkeypatch)
    assert backups.run_backup(workspace.db, tmp_path / "backups", 3) is None
    assert "Scheduled backup skipped" in caplog.text
    assert backups.scheduled(tmp_path / "backups") == []
    attempt = backups.run_if_due(workspace.db)
    assert attempt["outcome"] == "skipped" and attempt["name"] is None
    assert backups.last_attempt(workspace.db)["outcome"] == "skipped"
    assert backups.status(workspace.db)["ok"] is False


def test_keep_zero_disables_scheduled_backups(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "openings.sqlite")
    monkeypatch.setenv("OPENINGS_BACKUP_KEEP", "0")
    assert backups.due(workspace.db) is False
    assert backups.run_if_due(workspace.db) is None
    assert not (tmp_path / "backups").exists()
    assert backups.status(workspace.db)["enabled"] is False
    monkeypatch.setenv("OPENINGS_BACKUP_KEEP", "not a number")
    assert backups.backup_keep() == backups.DEFAULT_KEEP


def test_a_backup_runs_when_due_and_not_before(tmp_path):
    workspace = Workspace(tmp_path / "openings.sqlite")
    attempt = backups.run_if_due(workspace.db)
    assert attempt["outcome"] == "ok"
    newest = backups.scheduled(tmp_path / "backups")[0][0]
    assert backups.run_if_due(workspace.db, newest + timedelta(hours=23)) is None
    assert len(backups.scheduled(tmp_path / "backups")) == 1
    assert backups.due(workspace.db, newest + timedelta(hours=24))
    status = backups.status(workspace.db)
    assert status["ok"] is True and status["last_at"] and status["age_hours"] < 1
    assert backups.last_attempt(workspace.db) == attempt


def test_a_failed_backup_is_recorded_without_raising(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "openings.sqlite")

    def broken(*_):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(backups, "run_backup", broken)
    attempt = backups.run_if_due(workspace.db)
    assert attempt["outcome"] == "failed"
    assert attempt["error"] == "synthetic disk failure"
    assert backups.last_attempt(workspace.db)["error"] == "synthetic disk failure"
    assert backups.status(workspace.db)["ok"] is False


class OneCycle:
    """A stop event that ends the scheduler loop after its first idle wait."""

    def __init__(self):
        self.stopped = False

    def is_set(self):
        return self.stopped

    def wait(self, seconds):
        self.stopped = True
        return True


class IdleDiscovery:
    def schedule_due(self, stopping):
        return None


def test_the_worker_backs_up_on_its_cycle_and_survives_a_failure(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "openings.sqlite")
    worker = Worker(workspace, IdleDiscovery())
    worker.prune_seconds = 10**9
    worker._schedule_loop(OneCycle())
    assert len(backups.scheduled(tmp_path / "backups")) == 1
    assert worker.heartbeat_age() is not None
    # Not due again: the next cycle leaves the one backup.
    worker._schedule_loop(OneCycle())
    assert len(backups.scheduled(tmp_path / "backups")) == 1

    def broken(*_):
        raise sqlite3.OperationalError("synthetic failure")

    for item in (tmp_path / "backups").iterdir():
        item.unlink()
    monkeypatch.setattr(backups, "run_backup", broken)
    worker._schedule_loop(OneCycle())
    assert backups.last_attempt(workspace.db)["outcome"] == "failed"


# Owner access and /health


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "openings.sqlite", start_worker=False)
    app.state.auth.setup(PASSWORD)
    workspace = app.state.workspace
    backups.run_backup(workspace.db, backups.backup_dir(workspace.db), 3)
    shutil.copyfile(workspace.db.path, tmp_path / "openings.pre-schema13-20260101T080000Z.sqlite")
    return app


def test_the_owner_lists_downloads_and_deletes_kept_copies(app, tmp_path):
    with TestClient(app, base_url="http://localhost:8080") as client:
        session = client.post("/api/v1/auth/login", json={"password": PASSWORD}).json()
        listed = client.get("/api/v1/backups").json()
        kinds = {item["kind"]: item for item in listed["items"]}
        assert set(kinds) == {"scheduled", "pre_upgrade"}
        assert listed["schedule"]["keep"] == 3 and listed["schedule"]["ok"] is True
        daily, copy = kinds["scheduled"], kinds["pre_upgrade"]
        assert daily["size_bytes"] > 0 and daily["created_at"].endswith("Z")
        assert copy["created_at"] == "2026-01-01T08:00:00Z"

        response = client.get("/api/v1/backups/" + daily["name"])
        assert response.status_code == 200
        assert response.content[:16] == b"SQLite format 3\x00"
        assert daily["name"] in response.headers["content-disposition"]

        csrf = {"X-CSRF-Token": session["csrf_token"]}
        refused = client.delete("/api/v1/backups/" + daily["name"], headers=csrf)
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "backup_scheduled"
        deleted = client.delete("/api/v1/backups/" + copy["name"], headers=csrf)
        assert deleted.json() == {"deleted": True, "name": copy["name"]}
        assert not (tmp_path / copy["name"]).exists()
        assert [item["kind"] for item in client.get("/api/v1/backups").json()["items"]] == [
            "scheduled"
        ]


def test_the_renamed_original_of_the_0_24_upgrade_is_a_kept_copy(app, tmp_path):
    db = app.state.workspace.db
    shutil.copyfile(db.path, tmp_path / "openings.pre-0.24.sqlite")
    listed = {item["name"]: item["kind"] for item in backups.listing(db)}
    assert listed["openings.pre-0.24.sqlite"] == "pre_upgrade"
    assert listed["openings.pre-schema13-20260101T080000Z.sqlite"] == "pre_upgrade"
    # The archive beside it is not a database copy.
    (tmp_path / "openings.pre-0.24-archive.json").write_text("{}")
    assert "openings.pre-0.24-archive.json" not in {item["name"] for item in backups.listing(db)}


def test_names_outside_the_listing_are_not_found(app, tmp_path):
    token = app.state.auth.create_token("Synthetic owner", "owner")["token"]
    headers = {"Authorization": "Bearer " + token}
    (tmp_path / "unrelated.sqlite").write_bytes(b"synthetic")
    with TestClient(app, base_url="http://localhost:8080") as client:
        for name in (
            "openings.sqlite",
            "unrelated.sqlite",
            "..%2Fopenings.sqlite",
            "openings-20990101T000000Z.sqlite",
        ):
            for method in ("GET", "DELETE"):
                response = client.request(method, "/api/v1/backups/" + name, headers=headers)
                # An encoded separator never reaches the handler as a name.
                expected = (404, 405) if ".." in name else (404,)
                assert response.status_code in expected, (method, name)
        assert (tmp_path / "openings.sqlite").is_file()
    # The service itself matches exact names of the listing only.
    for name in ("../openings.sqlite", "backups/../openings.sqlite", "/etc/passwd", ""):
        with pytest.raises(DomainError) as missing:
            backups.find(app.state.workspace.db, name)
        assert missing.value.status == 404


def test_an_owner_token_succeeds_and_an_agent_token_is_refused(app):
    auth = app.state.auth
    owner = {"Authorization": "Bearer " + auth.create_token("Owner", "owner")["token"]}
    agent = {"Authorization": "Bearer " + auth.create_token("Agent", "agent")["token"]}
    with TestClient(app, base_url="http://localhost:8080") as client:
        items = client.get("/api/v1/backups", headers=owner).json()["items"]
        copy = next(item["name"] for item in items if item["kind"] == "pre_upgrade")
        for method, path in (
            ("GET", "/api/v1/backups"),
            ("GET", "/api/v1/backups/" + items[0]["name"]),
            ("DELETE", "/api/v1/backups/" + copy),
        ):
            response = client.request(method, path, headers=agent)
            assert response.status_code == 403, path
            assert response.json()["error"]["code"] == "forbidden"
        assert client.get("/api/v1/backups/" + items[0]["name"], headers=owner).status_code == 200
        assert client.delete("/api/v1/backups/" + copy, headers=owner).status_code == 200


def test_no_mcp_tool_reaches_kept_copies(app):
    names = {tool.name for tool in asyncio.run(app.state.mcp.list_tools())}
    assert not {name for name in names if name.startswith("backups")}
    descriptions = " ".join(
        (tool.description or "") for tool in asyncio.run(app.state.mcp.list_tools())
    )
    assert "/api/v1/backups" not in descriptions


def test_health_reports_the_backup_and_the_worker(tmp_path):
    app = create_app(tmp_path / "openings.sqlite")
    workspace = app.state.workspace
    with TestClient(app) as client:
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert set(body["backup"]) == {"last_at", "age_hours", "ok"}
        assert body["worker"]["heartbeat_age_seconds"] is not None
        # The scheduler's first cycle writes the first backup.
        deadline = datetime.now(UTC) + timedelta(seconds=10)
        while not client.get("/health").json()["backup"]["ok"]:
            assert datetime.now(UTC) < deadline
            threading.Event().wait(0.05)
        # A scheduler that stops cycling fails the healthcheck.
        workspace.worker.beat -= workspace.worker.stall_seconds + 1
        stalled = client.get("/health")
        assert stalled.status_code == 503
        assert stalled.json()["status"] == "worker_stalled"


def test_health_without_a_worker(tmp_path):
    app = create_app(tmp_path / "openings.sqlite", start_worker=False)
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["backup"] == {"last_at": None, "age_hours": None, "ok": False}
    assert body["worker"] == {"heartbeat_age_seconds": None}
    assert not os.path.exists(tmp_path / "backups")
