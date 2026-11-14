"""Compact list and mutation defaults, settings conflict details and revocable browser
sessions. MCP serves the same records without empty fields (test_parity.py)."""

from fastapi.testclient import TestClient

from conftest import BASE_URL, PASSWORD, McpClient
from openings.db import encode

STAMP = "2026-01-01T00:00:00.000000+00:00"


def stable(value):
    """Drop durations of an unfinished run, which grow between two reads."""
    if isinstance(value, dict):
        return {
            key: stable(item)
            for key, item in value.items()
            if key not in ("total_seconds", "waiting_seconds")
        }
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def populated(app):
    ws = app.state.workspace
    jobs = [
        ws.ingest_job(
            {
                "url": f"https://jobs.example.com/{index}",
                "title": f"Synthetic engineer {index}",
                "company": f"Example {index % 2}",
                "location": "Remote",
                "posting": "Build reliable services. " * 200,
                "metadata": {"source": "greenhouse", "job_type": "fulltime"},
            }
        )
        for index in range(3)
    ]
    application = ws.create_application({"job_id": jobs[0]["id"]})
    with ws.db.transaction() as connection:
        connection.execute(
            "INSERT INTO documents(id,application_id,kind,title,content,version,created_at) VALUES('doc-1',?,'answers','Form',?,1,?)",
            (application["id"], encode({"sections": ["Synthetic content"] * 50}), STAMP),
        )
        connection.execute(
            "INSERT INTO sources(id,name,kind,config,enabled,schedule,created_at,updated_at) VALUES('source-1','Example board','greenhouse',?,0,?,?,?)",
            (
                encode({"board": "example"}),
                encode({"kind": "interval", "minutes": 1440}),
                STAMP,
                STAMP,
            ),
        )
        connection.execute(
            "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,created_at) VALUES('run-1','source-1','Example board',1,?,?)",
            (encode({"name": "Example board", "config": {"board": "example"}}), STAMP),
        )
        connection.execute(
            "INSERT INTO tasks(id,kind,source_id,run_id,state,payload,result,next_run_at,error,created_at,updated_at) VALUES('task-1','collect','source-1','run-1','queued',?,?,?,'provider paused',?,?)",
            (
                encode({"provider": "greenhouse", "checkpoint": {"page": 2}}),
                encode({"received": 4, "diagnostics": [{"provider": "greenhouse"}] * 3}),
                STAMP,
                STAMP,
                STAMP,
            ),
        )
    return jobs, application


def test_lists_and_mutations_default_to_compact_records_with_full_opt_in(app, client, agent_token):
    jobs, application = populated(app)
    mcp = McpClient(client, agent_token)
    rest = client.get("/api/v1/jobs").json()
    assert "facets" not in rest and rest["total"] == 3
    faceted = client.get("/api/v1/jobs?include_facets=true").json()
    assert faceted["facets"]["companies"] == ["Example 0", "Example 1"]
    assert faceted["items"] == rest["items"]

    documents = client.get("/api/v1/documents").json()
    assert documents["items"][0]["file_count"] == 0
    assert "content" not in documents["items"][0]
    full = client.get("/api/v1/documents?summary=false").json()
    assert full["items"][0]["content"]["sections"] and full["items"][0]["files"] == []

    sources = client.get("/api/v1/sources").json()
    source = sources["items"][0]
    assert source["last_diagnostic_count"] == 3 and "last_diagnostics" not in source
    assert "source_snapshot" not in source["last_run"]
    assert source["last_run"]["tasks"] == [
        {
            "id": "task-1",
            "kind": "collect",
            "provider": "greenhouse",
            "state": "queued",
            "attempts": 0,
            "error": "provider paused",
            "next_run_at": STAMP,
            "updated_at": STAMP,
        }
    ]
    full = client.get("/api/v1/sources?summary=false").json()["items"][0]
    assert len(full["last_diagnostics"]) == 3
    assert full["last_run"]["tasks"][0]["result"]["received"] == 4
    detail = client.get("/api/v1/sources/source-1").json()
    assert detail.pop("recent_runs") and stable(full) == stable(detail)

    runs = client.get("/api/v1/collection/runs").json()
    assert runs["items"][0]["tasks"] == source["last_run"]["tasks"]
    assert runs["items"][0]["counts"]["received"] == 4
    full = client.get("/api/v1/collection/runs?summary=false").json()
    assert stable(full["items"][0]) == stable(client.get("/api/v1/collection/runs/run-1").json())
    assert "checkpoint" not in full["items"][0]["tasks"][0]["payload"]

    # Mutations answer with the compact job, not the posting.
    job = jobs[1]
    triaged = client.post(
        f"/api/v1/jobs/{job['id']}/triage",
        json={"triage": "shortlisted", "expected_version": job["version"]},
    ).json()
    assert triaged["triage"] == "shortlisted" and triaged["version"] == job["version"] + 1
    assert "posting" not in triaged and "postings" not in triaged
    assert triaged["posting_preview"].startswith("Build reliable services.")
    assert triaged == client.get("/api/v1/jobs?triage=shortlisted").json()["items"][0]
    job = jobs[2]
    updated, error = mcp.call(
        "jobs_update", {"job_id": job["id"], "title": "Renamed", "expected_version": 1}
    )
    assert error is None and updated["title"] == "Renamed" and updated["version"] == 2
    assert "posting" not in updated
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["posting"]

    changed = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"priority": 3, "expected_version": application["version"]},
    ).json()
    assert changed["priority"] == 3 and changed["job"]["id"] == jobs[0]["id"]
    assert "posting" not in changed["job"] and changed["job"]["posting_preview"]
    assert changed["preparation"] is not None
    read = client.get(f"/api/v1/applications/{application['id']}").json()
    assert read["job"]["posting"] and read["version"] == changed["version"]


def test_settings_conflicts_report_current_version(app, client):
    jobs, _application = populated(app)
    profile = client.get("/api/v1/career/profile").json()
    settings = client.get("/api/v1/preferences").json()["settings"]
    collection = client.get("/api/v1/collection").json()
    for path, body, current, record in [
        ("/api/v1/career/profile", {"name": "Synthetic"}, profile["version"], "profile"),
        ("/api/v1/settings", {"no_reply_days": 40}, settings["version"], "settings"),
        ("/api/v1/collection", {"enabled": False}, collection["version"], "collection"),
    ]:
        response = client.patch(path, json={**body, "expected_version": current + 5})
        assert response.status_code == 409, (path, response.text)
        error = response.json()["error"]
        assert error["code"] == "conflict"
        assert error["details"] == {"current_version": current, "id": record}, path

    stale = client.post(
        "/api/v1/jobs/bulk",
        json={"action": "shortlisted", "items": [{"id": jobs[1]["id"], "expected_version": 9}]},
    ).json()
    assert stale["items"][0]["error"]["details"] == {
        "current_version": jobs[1]["version"],
        "id": jobs[1]["id"],
    }


def test_logout_revokes_browser_sessions_but_keeps_api_tokens(app, agent_token):
    headers = agent_token["headers"]
    with TestClient(app, base_url=BASE_URL) as client:
        login = client.post("/api/v1/auth/login", json={"password": PASSWORD})
        assert login.status_code == 200
        stolen = client.cookies.get("openings_session")
        csrf = login.json()["csrf_token"]
        assert client.get("/api/v1/jobs").status_code == 200

        # A second browser signed in at the same time is revoked as well.
        client.cookies.clear()
        client.post("/api/v1/auth/login", json={"password": PASSWORD})
        other_cookie = client.cookies.get("openings_session")
        client.cookies.clear()
        client.cookies.set("openings_session", stolen)

        result = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        assert result.status_code == 200 and result.json()["sessions_revoked"] is True

        for cookie in (stolen, other_cookie):
            client.cookies.set("openings_session", cookie)
            assert client.get("/api/v1/jobs").status_code == 401
            assert client.get("/api/v1/auth/session").json()["authenticated"] is False
        client.cookies.clear()

        assert client.get("/api/v1/jobs", headers=headers).status_code == 200

        again = client.post("/api/v1/auth/login", json={"password": PASSWORD})
        assert again.status_code == 200
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True
        assert client.get("/api/v1/jobs").status_code == 200

        # Logout without a valid session or token cannot revoke the owner's session.
        current = client.cookies.get("openings_session")
        client.cookies.clear()
        assert client.post("/api/v1/auth/logout").status_code == 401
        client.cookies.set("openings_session", current)
        assert client.get("/api/v1/jobs").status_code == 200
