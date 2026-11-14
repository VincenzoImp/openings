"""MCP tools run off the event loop and return REST-shaped structured errors."""

import json
import threading

from fastapi.testclient import TestClient

from openings.app import create_app


def call(client, headers, name, arguments, ident=1):
    response = client.post(
        "/mcp/",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": ident,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert response.status_code == 200
    return response.json()["result"]


def error_body(result):
    assert result["isError"] is True
    return json.loads(result["content"][0]["text"])["error"]


def test_mcp_errors_keep_code_status_details_and_current_version(tmp_path):
    app = create_app(tmp_path / "mcp-contract.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic MCP client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    job = app.state.workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    with TestClient(app, base_url="http://localhost:8080") as client:
        missing = error_body(call(client, headers, "jobs_get", {"job_id": "unknown"}))
        assert missing == {
            "code": "not_found",
            "status": 404,
            "message": "Job was not found.",
            "details": None,
        }

        stale = error_body(
            call(
                client,
                headers,
                "jobs_update",
                {"job_id": job["id"], "expected_version": 99, "title": "Changed"},
                2,
            )
        )
        assert stale["code"] == "conflict" and stale["status"] == 409
        assert stale["details"] == {"current_version": job["version"], "id": job["id"]}

        invalid = error_body(call(client, headers, "jobs_get", {}, 3))
        assert invalid["code"] == "validation" and invalid["status"] == 422
        assert invalid["details"][0]["field"] == ["job_id"]


def test_sync_tools_run_in_worker_threads(tmp_path):
    app = create_app(tmp_path / "mcp-thread.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic MCP client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    workspace = app.state.workspace
    original = workspace.get_job
    seen = []

    def record(*args, **kwargs):
        seen.append(threading.current_thread().name)
        return original(*args, **kwargs)

    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    workspace.get_job = record
    with TestClient(app, base_url="http://localhost:8080") as client:
        assert call(client, headers, "jobs_get", {"job_id": job["id"]}).get("isError") is False
    assert seen and all(name.startswith("AnyIO worker thread") for name in seen), seen
