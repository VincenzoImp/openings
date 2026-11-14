"""Consistent JSON exports survive streaming thread changes and failed downloads."""

import asyncio
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from openings.interfaces.system import grant
from openings.models import JobInput
from openings.snapshots import RecordsResponse


@pytest.fixture
def snapshots(monkeypatch):
    files = []
    create = tempfile.TemporaryFile

    def tracked_file(*args, **kwargs):
        snapshot = create(*args, **kwargs)
        files.append(snapshot)
        return snapshot

    monkeypatch.setattr(tempfile, "TemporaryFile", tracked_file)
    yield files
    for snapshot in files:
        snapshot.close()


def test_export_stream_survives_worker_thread_changes(app, client, monkeypatch, snapshots):
    import starlette.responses

    workspace = app.state.workspace
    workspace.ingest_job(
        JobInput(title="Synthetic role", company="Example", posting="Build Python APIs.")
    )
    workspace.set_settings("workspace", {"no_reply_days": 21})
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
        response = client.get("/api/v1/export")
        assert response.status_code == 200
        archive = response.json()
        assert archive["format"] == "openings-records-v1"
        assert archive["files_include_bytes"] is False
        assert archive["jobs"][0]["title"] == "Synthetic role"
        assert archive["settings"]["workspace"]["no_reply_days"] == 21
        assert "auth" not in archive["settings"]
        assert int(response.headers["content-length"]) == len(response.content)
        assert snapshots and all(snapshot.closed for snapshot in snapshots)
        assert calls >= 2
    finally:
        for executor in executors:
            executor.shutdown()


def test_export_keeps_one_snapshot_during_concurrent_writes(app, client, monkeypatch):
    workspace = app.state.workspace
    workspace.ingest_job(
        JobInput(title="First role", company="Example", posting="Build reliable services.")
    )
    workspace.set_settings("workspace", {"no_reply_days": 21})
    dumps = json.dumps
    changed = False

    def write_during_export(value, *args, **kwargs):
        nonlocal changed
        if isinstance(value, dict) and value.get("title") == "First role" and not changed:
            changed = True
            workspace.ingest_job(
                JobInput(title="Later role", company="Example", posting="Another posting.")
            )
            workspace.set_settings("workspace", {"no_reply_days": 60})
        return dumps(value, *args, **kwargs)

    monkeypatch.setattr(json, "dumps", write_during_export)
    response = client.get("/api/v1/export")
    archive = response.json()
    assert changed
    assert [job["title"] for job in archive["jobs"]] == ["First role"]
    assert archive["settings"]["workspace"]["no_reply_days"] == 21
    assert workspace.db.one("SELECT count(*) n FROM jobs")["n"] == 2


def test_export_preparation_failure_closes_snapshot_before_response(app, owner_token, snapshots):
    # The schema refuses text that is not JSON; a damaged file can still hold it.
    with app.state.workspace.db.transaction() as conn:
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute(
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
        response = client.get("/api/v1/export", headers=owner_token["headers"])
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


@pytest.mark.asyncio
async def test_export_preserves_nullable_career_dates_and_scoped_mcp_download(app, client):
    from openings.career import EntryCreate, HighlightCreate, TemplateCreate

    career, workspace, documents = app.state.career, app.state.workspace, app.state.documents
    undated = career.create_entry(
        EntryCreate(title="Undated project", kind="project", skills=["Python"])
    )
    career.create_entry(
        EntryCreate(
            title="Dated project", kind="project", dates={"kind": "single", "start": "2025"}
        )
    )
    claim = career.create_highlight(
        HighlightCreate(career_id=undated["id"], text="Synthetic claim", approved=True)
    )
    career.create_template(TemplateCreate(name="Synthetic CV", tex="Example", is_default=True))
    job = workspace.ingest_job({"title": "Synthetic role", "posting": "Build reliable services."})
    application = workspace.create_application({"job_id": job["id"]})
    documents.create_document(
        {
            "application_id": application["id"],
            "career_ids": [undated["id"]],
            "pdf": {"name": "cv.pdf", "size": 1},
        }
    )
    archive = client.get("/api/v1/export").json()
    # The owner's export grant (workspace_export, owner only).
    ticket = grant(app.state.workspace, "export")
    client.cookies.clear()
    assert client.get("/api/v1/export").status_code == 401
    scoped = client.get(ticket["url"], headers=ticket["headers"])
    assert scoped.status_code == 200
    assert scoped.json() == archive
    assert client.get("/api/v1/career/profile", headers=ticket["headers"]).status_code == 401
    entries = {row["title"]: row for row in archive["knowledge"]}
    assert entries["Undated project"]["dates"] is None
    assert entries["Dated project"]["dates"]["start"] == "2025"
    assert archive["claims"][0]["id"] == claim["id"]
    assert "contexts" not in archive
    assert archive["documents"][0]["knowledge_ids"] == [undated["id"]]
    assert "auth" not in archive["settings"]
