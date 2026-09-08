import pytest


def _add(client, **overrides):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote"}
    payload.update(overrides)
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["job_ids"][0]


def test_health_and_dashboard(client):
    assert client.get("/health").json()["status"] == "ok"
    assert "Openings" in client.get("/").text
    assert client.get("/api/dashboard/auth").json() == {"token_required": False}


def test_job_lifecycle_through_rest(client):
    job_id = _add(client, description="Python and PostgreSQL", labels=["seed"])
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "shortlisted"
    assert detail["explain"]["score"] == 35
    assert detail["labels"] == ["seed"]

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

    note = client.post(
        f"/api/jobs/{job_id}/notes", json={"kind": "qa", "title": "Why?", "body": "Because."}
    )
    assert note.status_code == 201
    upload = client.post(
        f"/api/jobs/{job_id}/attachments",
        files={"file": ("cv.pdf", b"%PDF", "application/pdf")},
        data={"kind": "cv", "note": "v1"},
    )
    assert upload.status_code == 201
    attachment_id = upload.json()["id"]
    download = client.get(f"/api/jobs/{job_id}/attachments/{attachment_id}")
    assert download.status_code == 200 and download.content == b"%PDF"

    listed = client.get("/api/jobs", params={"status": "applied", "label": "b"}).json()
    assert listed["total"] == 1 and listed["items"][0]["labels"] == ["b"]

    events = [event["summary"] for event in client.get(f"/api/jobs/{job_id}").json()["events"]]
    assert "Status shortlisted -> applied: sent" in events
    assert any(summary.startswith("Attachment added (cv)") for summary in events)

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


def test_blacklist_flow(client):
    job_id = _add(client)
    assert client.post("/api/blacklist", json={"job_ids": [job_id]}).json()["affected_count"] == 1
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    conflict = client.post(
        "/api/jobs", json={"title": "Backend Engineer", "company": "Acme", "location": "Remote"}
    )
    assert conflict.status_code == 409
    assert client.get("/api/blacklist").json()["total"] == 1
    assert (
        client.post("/api/blacklist/remove", json={"job_ids": [job_id]}).json()["affected_count"]
        == 1
    )
    assert client.post("/api/blacklist/purge", json={}).json()["affected_count"] == 0


def test_sources_runs_stats_distribution_facets(client):
    _add(client)
    sources = {item["name"]: item for item in client.get("/api/sources").json()}
    assert sources["manual"]["active_jobs"] == 1
    assert client.get("/api/runs").json() == []
    assert client.get("/api/stats").json()["by_status"]["shortlisted"] == 1
    assert client.get("/api/distribution", params={"bin_size": 10}).json()
    assert client.get("/api/jobs/facets").json()["sources"] == [{"value": "manual", "count": 1}]


def test_export_endpoints(client):
    job_id = _add(client)
    response = client.post("/api/export/jobs", json={"job_ids": [job_id], "format": "json"})
    assert response.status_code == 200
    assert response.headers["x-openings-export-total"] == "1"
    csv_response = client.get("/api/export/jobs", params={"status": "shortlisted"})
    assert csv_response.headers["content-type"].startswith("text/csv")
    filtered = client.post(
        "/api/export/jobs",
        json={"format": "json", "filters": {"statuses": ["shortlisted"], "limit": 0}},
    )
    assert filtered.json()[0]["job_id"] == job_id
    assert client.post("/api/export/jobs", json={"filters": {"bogus": 1}}).status_code == 422


def test_cleanup_endpoints(client):
    _add(client, status="new")
    assert client.get("/api/cleanup/preview").json()["total_deleted"] == 0
    assert (
        client.post("/api/cleanup/delete-below-score", json={"score": 100}).json()["affected_count"]
        == 1
    )
    assert client.post("/api/cleanup/delete-stale", json={"days": 1}).json()["affected_count"] == 0
    assert client.post("/api/cleanup/run").json()["total_deleted"] == 0


def test_semantic_search_reports_missing_vector_store(client, monkeypatch):
    from openings.web import service

    monkeypatch.setattr(service, "_vector_store_attempted", True)
    monkeypatch.setattr(service, "_vector_store", None)
    response = client.get("/api/jobs/search/semantic", params={"q": "python"})
    assert response.status_code == 503
    assert "Vector store" in response.json()["detail"]


def test_token_gate(env, monkeypatch):
    monkeypatch.setenv("OPENINGS_API_TOKEN", "secret")
    from fastapi.testclient import TestClient

    from openings.web.app import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/dashboard/auth").json() == {"token_required": True}
        assert client.get("/api/stats").status_code == 401
        assert client.get("/api/stats", headers={"X-Openings-Token": "secret"}).status_code == 200
        assert (
            client.get("/api/stats", headers={"Authorization": "Bearer secret"}).status_code == 200
        )
        assert client.get("/api/stats", headers={"Authorization": "Bearer nope"}).status_code == 401


@pytest.mark.parametrize("path", ["/api/jobs/" + "0" * 64, "/api/jobs/x/attachments/1"])
def test_unknown_job_is_404(client, path):
    assert client.get(path).status_code == 404
