"""Scheduled local backups, pre-upgrade copies and the owner's access to them (#205)."""

import hashlib
import json
import shutil
import sqlite3
import stat
import threading
from contextlib import closing
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from doubles import Lane
from openings import backups, compaction, operations
from openings.app import create_app
from openings.common import now
from openings.db import SCHEMA_VERSION, Database
from openings.discovery import DiscoveryService
from openings.errors import DomainError
from openings.operations import restore_database
from openings.worker import Worker
from openings.workspace import Workspace


def older(path, version=13):
    """A workspace file marked with an earlier schema than the migration starts from."""
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


# Starting a workspace


def test_a_fresh_workspace_takes_no_copy_and_an_unsupported_schema_is_refused(tmp_path):
    Database(tmp_path / "fresh.sqlite")
    assert not list(tmp_path.glob("*.pre-*"))

    path = older(tmp_path / "openings.sqlite")
    before = path.read_bytes()
    files = sorted(item.name for item in tmp_path.iterdir())
    with pytest.raises(DomainError) as refused:
        Database(path)
    assert refused.value.code == "schema_version"
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == files


# Scheduled backups


def test_a_backup_is_verified_private_and_rotated(tmp_path, monkeypatch):
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
    # The directory is created private, here or where the setting names.
    assert backups.backup_dir(workspace.db) == tmp_path / "backups"
    monkeypatch.setenv("OPENINGS_BACKUP_DIR", str(tmp_path / "elsewhere" / "copies"))
    directory = backups.backup_dir(workspace.db)
    assert directory == tmp_path / "elsewhere" / "copies"
    backups.run_backup(workspace.db, directory, 3)
    assert mode(directory) == 0o700
    assert len(backups.scheduled(directory)) == 1


def test_skipped_failed_and_disabled_backups_are_recorded(tmp_path, monkeypatch, caplog):
    workspace = Workspace(tmp_path / "openings.sqlite")
    with monkeypatch.context() as patch:
        no_room(patch)
        assert backups.run_backup(workspace.db, tmp_path / "backups", 3) is None
        assert "Scheduled backup skipped" in caplog.text
        assert backups.scheduled(tmp_path / "backups") == []
        attempt = backups.run_if_due(workspace.db)
    assert attempt["outcome"] == "skipped" and attempt["name"] is None
    assert backups.last_attempt(workspace.db)["outcome"] == "skipped"
    assert backups.status(workspace.db)["ok"] is False

    def broken(*_):
        raise OSError("synthetic disk failure")

    # After a skipped or failed attempt the next one waits an hour, not one cycle.
    later = datetime.now(UTC) + timedelta(hours=backups.RETRY_HOURS, minutes=1)
    with monkeypatch.context() as patch:
        patch.setattr(backups, "run_backup", broken)
        assert backups.run_if_due(workspace.db) is None
        attempt = backups.run_if_due(workspace.db, later)
        assert backups.run_if_due(workspace.db, later + timedelta(minutes=30)) is None
    assert attempt["outcome"] == "failed"
    assert attempt["error"] == "synthetic disk failure"
    assert backups.last_attempt(workspace.db)["error"] == "synthetic disk failure"
    assert backups.status(workspace.db)["ok"] is False

    # Keeping zero disables scheduled backups.
    monkeypatch.setenv("OPENINGS_BACKUP_KEEP", "0")
    assert backups.due(workspace.db) is False
    assert backups.run_if_due(workspace.db) is None
    assert backups.scheduled(tmp_path / "backups") == []
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


class IdleDiscovery:
    def schedule_due(self, stopping):
        return None


def test_the_worker_backs_up_on_its_cycle_and_survives_a_failure(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "openings.sqlite")
    worker = Worker(workspace, IdleDiscovery())
    worker.prune_seconds = 10**9
    worker._schedule_loop(Lane())
    assert len(backups.scheduled(tmp_path / "backups")) == 1
    assert worker.heartbeat_age() is not None
    # Not due again: the next cycle leaves the one backup.
    worker._schedule_loop(Lane())
    assert len(backups.scheduled(tmp_path / "backups")) == 1

    def broken(*_):
        raise sqlite3.OperationalError("synthetic failure")

    for item in (tmp_path / "backups").iterdir():
        item.unlink()
    monkeypatch.setattr(backups, "run_backup", broken)
    worker._schedule_loop(Lane())
    assert backups.last_attempt(workspace.db)["outcome"] == "failed"


# Owner access and /health


@pytest.fixture
def kept(app):
    """The owner's app with one scheduled backup and one pre-upgrade copy beside it."""
    db = app.state.workspace.db
    backups.run_backup(db, backups.backup_dir(db), 3)
    copy = db.path.with_name(db.path.stem + ".pre-schema13-20260101T080000Z.sqlite")
    shutil.copyfile(db.path, copy)
    return db


def test_the_owner_lists_downloads_and_deletes_kept_copies(kept, client):
    # 0.24's renamed original is a kept copy; the archive beside it is not.
    renamed = kept.path.with_name(kept.path.stem + ".pre-0.24.sqlite")
    shutil.copyfile(kept.path, renamed)
    kept.path.with_name(kept.path.stem + ".pre-0.24-archive.json").write_text("{}")
    listed = client.get("/api/v1/backups").json()
    assert {item["name"]: item["kind"] for item in listed["items"]}[renamed.name] == "pre_upgrade"
    assert len(listed["items"]) == 3
    renamed.unlink()
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

    refused = client.delete("/api/v1/backups/" + daily["name"])
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "backup_scheduled"
    deleted = client.delete("/api/v1/backups/" + copy["name"])
    assert deleted.json() == {"deleted": True, "name": copy["name"]}
    assert not kept.path.with_name(copy["name"]).exists()
    assert [item["kind"] for item in client.get("/api/v1/backups").json()["items"]] == ["scheduled"]


def test_names_outside_the_listing_are_not_found(kept, app, owner_token):
    """Exact names of the listing only; an owner token reaches them (agents: test_parity)."""
    headers = owner_token["headers"]
    kept.path.with_name("unrelated.sqlite").write_bytes(b"synthetic")
    with TestClient(app, base_url="http://localhost:8080") as client:
        for name in (
            kept.path.name,
            "unrelated.sqlite",
            "..%2F" + kept.path.name,
            "openings-20990101T000000Z.sqlite",
        ):
            for method in ("GET", "DELETE"):
                response = client.request(method, "/api/v1/backups/" + name, headers=headers)
                # An encoded separator never reaches the handler as a name.
                expected = (404, 405) if ".." in name else (404,)
                assert response.status_code in expected, (method, name)
        assert kept.path.is_file()
        items = client.get("/api/v1/backups", headers=headers).json()["items"]
        copy = next(item["name"] for item in items if item["kind"] == "pre_upgrade")
        assert client.get("/api/v1/backups/" + items[0]["name"], headers=headers).is_success
        assert client.delete("/api/v1/backups/" + copy, headers=headers).is_success
    # The service itself matches exact names of the listing only.
    for name in ("../" + kept.path.name, "backups/../" + kept.path.name, "/etc/passwd", ""):
        with pytest.raises(DomainError) as missing:
            backups.find(kept, name)
        assert missing.value.status == 404


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


def test_health_without_a_worker(app, client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["backup"] == {"last_at": None, "age_hours": None, "ok": False}
    assert body["worker"] == {"heartbeat_age_seconds": None}
    assert not (app.state.workspace.db.path.parent / "backups").exists()


# Restore


def test_a_backup_keeps_exact_files_and_a_restore_keeps_provider_requests(workspace, tmp_path):
    original = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    value = b"synthetic file bytes"
    sha = hashlib.sha256(value).hexdigest()
    with workspace.db.transaction() as c:
        c.execute("INSERT INTO blobs VALUES(?,?,?)", (sha, value, len(value)))
        c.execute(
            "INSERT INTO files(id,sha256,name,size,job_id,created_at) VALUES(?,?,?,?,?,?)",
            ("f1", sha, "source.tex", len(value), original["id"], now()),
        )
    discovery = DiscoveryService(workspace)
    provider = discovery.providers.get("linkedin")
    workspace.db.backup(tmp_path / "before-requests.sqlite")
    with sqlite3.connect(tmp_path / "before-requests.sqlite") as copy:
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copy.execute("SELECT content FROM blobs").fetchone()[0] == value
    deadline = (datetime.now(UTC) + timedelta(minutes=20)).isoformat(timespec="microseconds")
    workspace.db.execute(
        "UPDATE providers SET runtime=? WHERE id='linkedin'",
        (
            json.dumps(
                {
                    "events": [datetime.now(UTC).timestamp()],
                    "cooldown_until": deadline,
                    "total_requests": 1,
                }
            ),
        ),
    )
    # The installation's tokens stay as they are, with their last context read.
    token = ("t1", "Agent", "synthetic-hash", now(), "agent", "2026-01-02T03:04:05Z")
    workspace.db.execute(
        "INSERT INTO api_tokens(id,name,token_hash,created_at,kind,context_read_at) "
        "VALUES(?,?,?,?,?,?)",
        token,
    )
    restore_database(workspace, tmp_path / "before-requests.sqlite")
    assert workspace.db.one("SELECT * FROM api_tokens")["context_read_at"] == token[-1]
    restored = discovery.providers.get("linkedin")
    assert restored["runtime"]["cooldown_until"] == deadline
    assert restored["runtime"]["requests_day"] == 1
    assert restored["policy"] == provider["policy"]


def test_a_refused_or_failed_restore_leaves_the_workspace_as_it_was(
    workspace, tmp_path, monkeypatch
):
    kept = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build APIs."})
    # A backup of an unsupported schema is refused without reading further.
    for version in (1, 4):
        archive = tmp_path / f"unsupported-{version}.sqlite"
        with closing(sqlite3.connect(archive)) as connection:
            connection.execute(f"PRAGMA user_version={version}")
            connection.execute("CREATE TABLE marker(value TEXT)")
            connection.commit()
        original = archive.read_bytes()
        with pytest.raises(DomainError) as refused:
            restore_database(workspace, archive)
        assert refused.value.code == "backup_version"
        assert archive.read_bytes() == original
    # A restore that fails after the copy began is rolled back and the worker restarts.
    DiscoveryService(workspace)  # its providers' runtime is carried over the copy
    backup = tmp_path / "backup.sqlite"
    workspace.db.backup(backup)
    later = workspace.ingest_job({"title": "Later engineer", "posting": "Run services."})
    calls = []
    workspace.worker = SimpleNamespace(
        stop=lambda: calls.append("stop"), start=lambda: calls.append("start")
    )

    def broken(*_):
        raise RuntimeError("Synthetic failure while restoring.")

    monkeypatch.setattr(operations, "preserve_provider_runtime", broken)
    with pytest.raises(RuntimeError):
        restore_database(workspace, backup)
    assert calls == ["stop", "start"]
    assert {job["id"] for job in workspace.list_jobs()["items"]} == {kept["id"], later["id"]}
    assert workspace.db.one("PRAGMA quick_check")["quick_check"] == "ok"
    assert not list(workspace.db.path.parent.glob("*rollback*"))
