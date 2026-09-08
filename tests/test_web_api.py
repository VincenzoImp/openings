import io
import zipfile

import pytest


def _add(client, **overrides):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote"}
    payload.update(overrides)
    response = client.post("/api/jobs", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()["job_ids"][0]


def test_health_and_dashboard(client):
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["embeddings"] == "disabled"
    assert "Openings" in client.get("/").text
    assert client.get("/api/dashboard/auth").json() == {"token_required": False}


def test_job_lifecycle_through_rest(client):
    job_id = _add(client, description="Python and PostgreSQL", labels=["seed"])
    assert (
        client.post(
            "/api/jobs", json={"title": "Backend Engineer", "company": "Acme", "location": "Remote"}
        ).status_code
        == 200
    )
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "shortlisted"
    assert detail["explain"]["score"] == 35
    assert detail["labels"] == ["seed"] and detail["postings"] == []

    assert (
        client.post(
            "/api/jobs/status", json={"job_ids": [job_id], "status": "applied", "note": "sent"}
        ).json()["affected_count"]
        == 1
    )
    assert (
        client.post("/api/jobs/labels", json={"job_ids": [job_id], "labels": ["b"]}).json()[
            "affected_count"
        ]
        == 1
    )
    assert (
        client.post(
            "/api/jobs/labels/remove", json={"job_ids": [job_id], "labels": ["seed"]}
        ).json()["affected_count"]
        == 1
    )

    patched = client.patch(f"/api/jobs/{job_id}", json={"job_level": "senior", "bogus": 1})
    assert patched.status_code == 200 and patched.json()["job_level"] == "senior"
    assert client.patch(f"/api/jobs/{job_id}", json={}).status_code == 422

    note = client.post(
        f"/api/jobs/{job_id}/notes", json={"kind": "qa", "title": "Why?", "body": "Because."}
    )
    assert note.status_code == 201
    edited = client.put(f"/api/jobs/{job_id}/notes/{note.json()['id']}", json={"body": "Better."})
    assert edited.json()["body"] == "Better."

    upload = client.post(
        f"/api/jobs/{job_id}/attachments",
        files={"file": ("cv.pdf", b"%PDF", "application/pdf")},
        data={"kind": "cv", "note": "v1"},
    )
    assert upload.status_code == 201
    attachment_id = upload.json()["id"]
    download = client.get(f"/api/jobs/{job_id}/attachments/{attachment_id}")
    assert download.status_code == 200 and download.content == b"%PDF"
    assert "attachment" in download.headers["content-disposition"]
    inline = client.get(
        f"/api/jobs/{job_id}/attachments/{attachment_id}", params={"inline": "true"}
    )
    assert inline.headers["content-disposition"].startswith("inline")
    renamed = client.patch(
        f"/api/jobs/{job_id}/attachments/{attachment_id}", json={"kind": "other", "note": "v2"}
    )
    assert renamed.json()["kind"] == "other"
    listed_attachments = client.get("/api/attachments", params={"kind": "other"}).json()
    assert listed_attachments["total"] == 1 and listed_attachments["items"][0]["company"] == "Acme"

    listed = client.get("/api/jobs", params={"statuses": "applied", "labels": "b"}).json()
    assert listed["total"] == 1 and listed["items"][0]["labels"] == ["b"]
    assert listed["items"][0]["attachments_count"] == 1

    bundle = client.get(f"/api/jobs/{job_id}/bundle.zip")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert "attachments/cv.pdf" in archive.namelist()

    events = [event["summary"] for event in client.get(f"/api/jobs/{job_id}").json()["events"]]
    assert "Status shortlisted -> applied: sent" in events

    assert client.delete(f"/api/jobs/{job_id}/attachments/{attachment_id}").status_code == 200
    assert client.delete(f"/api/jobs/{job_id}/notes/{note.json()['id']}").status_code == 200
    assert client.delete(f"/api/jobs/{job_id}/notes/999").status_code == 404


def test_invalid_status_and_sort_are_rejected(client):
    job_id = _add(client)
    assert (
        client.post(
            "/api/jobs/status", json={"job_ids": [job_id], "status": "bookmarked"}
        ).status_code
        == 422
    )
    assert client.get("/api/jobs", params={"sort": "random"}).status_code == 422
    assert client.get("/api/jobs", params={"statuses": "bookmarked"}).status_code == 422
    assert client.get("/api/jobs", params={"direction": "sideways"}).status_code == 422


def test_blacklist_flow_keeps_history(client):
    job_id = _add(client)
    assert (
        client.post("/api/blacklist", json={"job_ids": [job_id], "note": "closed"}).json()[
            "affected_count"
        ]
        == 1
    )
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "blacklisted"
    assert client.get("/api/jobs").json()["total"] == 0
    conflict = client.post(
        "/api/jobs", json={"title": "Backend Engineer", "company": "Acme", "location": "Remote"}
    )
    assert conflict.status_code == 409
    listed = client.get("/api/blacklist", params={"text": "backend"}).json()
    assert listed["total"] == 1
    assert (
        client.post("/api/blacklist/remove", json={"job_ids": [job_id]}).json()["affected_count"]
        == 1
    )
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "shortlisted"


def test_merge_endpoint(client):
    primary = _add(client, job_url="https://linkedin.com/jobs/view/1")
    other = _add(
        client, title="Backend Engineer (mirror)", job_url="https://ch.indeed.com/viewjob?jk=2"
    )
    merged = client.post("/api/jobs/merge", json={"primary_id": primary, "other_ids": [other]})
    assert merged.json()["affected_count"] == 1
    assert client.get(f"/api/jobs/{other}").status_code == 404
    assert len(client.get(f"/api/jobs/{primary}").json()["postings"]) == 2
    assert (
        client.post("/api/jobs/merge", json={"primary_id": "x", "other_ids": [primary]}).status_code
        == 404
    )


def test_sources_runs_stats_distribution_facets_settings(client):
    _add(client)
    sources = {item["name"]: item for item in client.get("/api/sources").json()}
    assert sources["manual"]["active_jobs"] == 1
    assert client.get("/api/runs").json() == []
    assert client.get("/api/runs/status").json()["running"] is False
    assert client.post("/api/runs").status_code == 202
    assert client.get("/api/runs/status").json()["requested"] is True
    assert client.get("/api/stats").json()["by_status"]["shortlisted"] == 1
    assert client.get("/api/distribution", params={"bin_size": 10}).json()
    facets = client.get("/api/jobs/facets", params={"limit": 5}).json()
    assert facets["sources"] == [{"value": "manual", "count": 1}]
    assert client.get("/api/companies/Acme/statuses").json() == {"shortlisted": 1}
    settings = client.get("/api/settings").json()
    assert settings["scoring"]["save_threshold"] == 0
    assert "settings.yaml" in client.get("/api/settings/reference").text
    labels = client.get("/api/labels").json()
    assert labels == []


def test_export_endpoints(client):
    job_id = _add(client)
    response = client.post("/api/export/jobs", json={"job_ids": [job_id], "format": "json"})
    assert response.status_code == 200
    assert response.headers["x-openings-export-total"] == "1"
    csv_response = client.get("/api/export/jobs", params={"statuses": "shortlisted"})
    assert csv_response.headers["content-type"].startswith("text/csv")
    everything = client.get("/api/export/jobs", params={"limit": 0, "format": "json"})
    assert everything.json()[0]["job_id"] == job_id
    filtered = client.post(
        "/api/export/jobs",
        json={"format": "json", "filters": {"statuses": ["shortlisted"], "limit": 0}},
    )
    assert filtered.json()[0]["job_id"] == job_id
    assert client.post("/api/export/jobs", json={"filters": {"bogus": 1}}).status_code == 422
    assert client.post("/api/export/jobs", json={"filters": {"limit": "abc"}}).status_code == 422


def test_cleanup_endpoints_with_dry_run(client):
    _add(client, status="new")
    assert client.get("/api/cleanup/preview").json()["total_deleted"] == 0
    dry = client.post(
        "/api/cleanup/delete-below-score", json={"score": 100, "dry_run": True}
    ).json()
    assert dry["affected_count"] == 1 and dry["message"] == "dry run"
    assert client.get("/api/jobs").json()["total"] == 1
    assert (
        client.post("/api/cleanup/delete-below-score", json={"score": 100}).json()["affected_count"]
        == 1
    )
    assert client.post("/api/cleanup/delete-stale", json={"days": 1}).json()["affected_count"] == 0
    assert client.post("/api/cleanup/run").json()["total_deleted"] == 0


def test_semantic_search_reports_missing_index(client):
    response = client.get("/api/jobs/search/semantic", params={"q": "python"})
    assert response.status_code == 503
    assert client.get("/api/jobs/search/semantic").status_code == 422


def test_labels_rename_and_delete(client):
    job_id = _add(client, labels=["old"])
    assert (
        client.post("/api/labels/rename", json={"old": "old", "new": "new"}).json()[
            "affected_count"
        ]
        == 1
    )
    assert client.get(f"/api/jobs/{job_id}").json()["labels"] == ["new"]
    assert client.post("/api/labels/delete", json={"label": "new"}).json()["affected_count"] == 1


def test_token_gate_protects_api_and_mcp(runtime, monkeypatch):
    monkeypatch.setenv("OPENINGS_API_TOKEN", "secret")
    from fastapi.testclient import TestClient

    from openings.web.app import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/dashboard/auth").json() == {"token_required": True}
        assert client.get("/health").status_code == 200
        assert client.get("/api/stats").status_code == 401
        assert client.get("/api/stats", headers={"X-Openings-Token": "secret"}).status_code == 200
        assert (
            client.get("/api/stats", headers={"Authorization": "Bearer secret"}).status_code == 200
        )
        assert client.get("/api/stats", headers={"Authorization": "Bearer nope"}).status_code == 401
        mcp_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"},
            },
        }
        assert client.post("/mcp/", json=init, headers=mcp_headers).status_code == 401
        assert (
            client.post(
                "/mcp/", json=init, headers={**mcp_headers, "Authorization": "Bearer secret"}
            ).status_code
            == 200
        )


@pytest.mark.parametrize(
    "path",
    [
        "/api/jobs/" + "0" * 64,
        "/api/jobs/x/attachments/1",
        "/api/jobs/x/bundle.zip",
        "/api/jobs/x/similar",
    ],
)
def test_unknown_job_is_404(client, path):
    assert client.get(path).status_code == 404
