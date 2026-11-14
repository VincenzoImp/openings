"""MCP tools run off the event loop and return REST-shaped structured errors."""

import threading


def test_mcp_errors_keep_code_status_details_and_current_version(app, mcp):
    job = app.state.workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    _, missing = mcp.call("documents_get", {"document_id": "unknown"})
    assert missing == {
        "code": "not_found",
        "status": 404,
        "message": "Document revision was not found.",
        "details": None,
    }
    _, stale = mcp.call(
        "jobs_update", {"job_id": job["id"], "expected_version": 99, "title": "Changed"}
    )
    assert stale["code"] == "conflict" and stale["status"] == 409
    assert stale["details"] == {"current_version": job["version"], "id": job["id"]}
    _, invalid = mcp.call("jobs_get", {})
    assert invalid["code"] == "validation" and invalid["status"] == 422
    assert invalid["details"][0]["field"] == ["ids"]
    # Sync tools run in worker threads, off the event loop.
    workspace = app.state.workspace
    original = workspace.get_job
    seen = []

    def record(*args, **kwargs):
        seen.append(threading.current_thread().name)
        return original(*args, **kwargs)

    workspace.get_job = record
    value, error = mcp.call("jobs_get", {"ids": [job["id"]]})
    assert error is None and value["items"]
    assert seen and all(name.startswith("AnyIO worker thread") for name in seen), seen
