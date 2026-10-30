"""Consistent JSON exports survive streaming thread changes and failed downloads."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest
from starlette.requests import ClientDisconnect

import openings.app as app_module
from openings.app import RecordsResponse, create_app
from openings.models import JobInput


@pytest.fixture
def snapshots(monkeypatch):
    files = []
    create = app_module.tempfile.TemporaryFile

    def tracked_file(*args, **kwargs):
        snapshot = create(*args, **kwargs)
        files.append(snapshot)
        return snapshot

    monkeypatch.setattr(app_module.tempfile, "TemporaryFile", tracked_file)
    yield files
    for snapshot in files:
        snapshot.close()


def test_export_stream_survives_worker_thread_changes(tmp_path, monkeypatch, snapshots):
    import starlette.responses

    app = create_app(tmp_path / "export.sqlite", start_worker=False)
    workspace = app.state.workspace
    workspace.ingest_job(
        JobInput(title="Synthetic role", company="Example", posting="Build Python APIs.")
    )
    workspace.set_settings("scoring", {"enabled": False, "api_key": "synthetic-secret"})
    workspace.set_settings("instructions", {"general": "Reviewed synthetic evidence."})
    executors = [ThreadPoolExecutor(max_workers=1) for _ in range(2)]
    calls = 0

    def next_chunk(iterator):
        try:
            return True, next(iterator)
        except StopIteration:
            return False, None

    async def alternate_threads(content):
        nonlocal calls
        iterator = iter(content)
        while True:
            executor = executors[calls % 2]
            calls += 1
            available, chunk = await asyncio.get_running_loop().run_in_executor(
                executor, next_chunk, iterator
            )
            if not available:
                break
            yield chunk

    monkeypatch.setattr(starlette.responses, "iterate_in_threadpool", alternate_threads)
    try:
        with TestClient(app) as client:
            client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
            response = client.get("/api/v1/export")
        assert response.status_code == 200
        archive = response.json()
        assert archive["format"] == "openings-records-v1"
        assert archive["files_include_bytes"] is False
        assert archive["jobs"][0]["title"] == "Synthetic role"
        assert archive["settings"]["instructions"]["general"] == "Reviewed synthetic evidence."
        assert "api_key" not in archive["settings"]["scoring"]
        assert "auth" not in archive["settings"]
        assert int(response.headers["content-length"]) == len(response.content)
        assert snapshots and all(snapshot.closed for snapshot in snapshots)
        assert calls >= 2
    finally:
        for executor in executors:
            executor.shutdown()


def test_export_keeps_one_snapshot_during_concurrent_writes(tmp_path, monkeypatch):
    app = create_app(tmp_path / "snapshot.sqlite", start_worker=False)
    workspace = app.state.workspace
    workspace.ingest_job(
        JobInput(title="First role", company="Example", posting="Build reliable services.")
    )
    workspace.set_settings("instructions", {"general": "Before export"})
    dumps = app_module.json.dumps
    changed = False

    def write_during_export(value, *args, **kwargs):
        nonlocal changed
        if isinstance(value, dict) and value.get("title") == "First role" and not changed:
            changed = True
            workspace.ingest_job(
                JobInput(title="Later role", company="Example", posting="Another posting.")
            )
            workspace.set_settings("instructions", {"general": "After export began"})
        return dumps(value, *args, **kwargs)

    with TestClient(app) as client:
        client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        monkeypatch.setattr(app_module.json, "dumps", write_during_export)
        response = client.get("/api/v1/export")
    archive = response.json()
    assert changed
    assert [job["title"] for job in archive["jobs"]] == ["First role"]
    assert archive["settings"]["instructions"]["general"] == "Before export"
    assert workspace.db.one("SELECT count(*) n FROM jobs")["n"] == 2


def test_export_preparation_failure_closes_snapshot_before_response(tmp_path, snapshots):
    app = create_app(tmp_path / "invalid-record.sqlite", start_worker=False)
    app.state.workspace.db.execute(
        "INSERT INTO sources(id,name,kind,config,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (
            "invalid",
            "Synthetic invalid source",
            "rss",
            "invalid JSON",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        response = client.get("/api/v1/export")
    assert response.status_code == 500
    assert b"openings-records-v1" not in response.content
    assert snapshots and all(snapshot.closed for snapshot in snapshots)


@pytest.mark.asyncio
@pytest.mark.parametrize("spec_version", ["2.0", "2.4"])
async def test_export_disconnect_closes_snapshot(spec_version, snapshots):
    response = RecordsResponse(iter(['{"synthetic":"', "x" * 150_000, '"}']))
    started = asyncio.Event()

    async def send(message):
        if message["type"] == "http.response.body":
            started.set()
            if spec_version == "2.4":
                raise OSError("Synthetic disconnected client")
            await asyncio.Event().wait()

    async def receive():
        await started.wait()
        return {"type": "http.disconnect"}

    scope = {"type": "http", "asgi": {"spec_version": spec_version}}
    if spec_version == "2.4":
        with pytest.raises(ClientDisconnect):
            await response(scope, receive, send)
    else:
        await response(scope, receive, send)
    assert snapshots and all(snapshot.closed for snapshot in snapshots)
