"""Tests for the unified web REST API."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from job_search_tool.database import JobDatabase
from job_search_tool.models import Job


PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture()
def db_path():
    """Temporary DB path shared between the API client and direct DB access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture()
def _seed_db(db_path: Path) -> None:
    db = JobDatabase(db_path)
    jobs = [
        Job(
            title="Backend Engineer",
            company="Acme Corp",
            location="Remote",
            relevance_score=40,
            job_url="https://example.com/backend",
            job_type="fulltime",
            is_remote=True,
            date_posted=date(2026, 5, 1),
            min_amount=90000,
            max_amount=130000,
        ),
        Job(
            title="Frontend Developer",
            company="Widget Inc",
            location="New York",
            relevance_score=20,
            job_url="https://example.com/frontend",
            job_type="contract",
            is_remote=False,
            date_posted=date(2026, 5, 3),
            min_amount=70000,
            max_amount=90000,
        ),
        Job(
            title="Data Scientist",
            company="DataCo",
            location="San Francisco",
            relevance_score=30,
            job_url="https://example.com/data",
            job_type="fulltime",
            is_remote=False,
            date_posted=date(2026, 5, 5),
            min_amount=100000,
            max_amount=160000,
        ),
    ]
    db.save_job(jobs[0], site="linkedin")
    db.save_job(jobs[1], site="indeed")
    db.save_job(jobs[2], site="indeed")
    db.close()


@pytest.fixture()
def client(db_path: Path, _seed_db: None):
    """Create a TestClient backed by the seeded DB singleton."""
    with _client_for_db(db_path) as test_client:
        yield test_client


@contextmanager
def _client_for_db(db_path: Path):
    """Create a TestClient backed by an existing test DB path."""
    from job_search_tool import job_service
    from job_search_tool.web.app import create_app

    db = JobDatabase(db_path)
    db.close()
    job_service._db = db
    job_service._vs = None
    job_service._vs_attempted = True

    with TestClient(create_app(), raise_server_exceptions=True) as test_client:
        yield test_client

    db.close()
    job_service.reset_singletons()


@pytest.fixture()
def mock_vector_store():
    """Create a mock vector store returning canned semantic results."""
    from job_search_tool.vector_store import SemanticSearchResult

    vs = MagicMock()
    vs.search.return_value = [
        SemanticSearchResult(
            job_id="abc123",
            distance=0.15,
            similarity=0.85,
            metadata={
                "title": "ML Engineer",
                "company": "AI Corp",
                "location": "Remote",
                "relevance_score": 35,
                "site": "linkedin",
                "job_url": "https://example.com/ml",
            },
        )
    ]
    return vs


def test_web_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "jobs_count": 3}


def test_web_openapi_version_matches_project_metadata(client: TestClient) -> None:
    from job_search_tool.project_meta import get_project_version

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["version"] == get_project_version()


def test_api_token_rejects_missing_header(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOB_SEARCH_API_TOKEN", "secret-token")

    response = client.get("/api/jobs")

    assert response.status_code == 401


def test_api_token_accepts_bearer_header(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOB_SEARCH_API_TOKEN", "secret-token")

    response = client.get(
        "/api/jobs",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 200


def test_api_token_accepts_dashboard_header(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOB_SEARCH_API_TOKEN", "secret-token")

    response = client.get(
        "/api/jobs",
        headers={"X-Job-Search-Token": "secret-token"},
    )

    assert response.status_code == 200


def test_dashboard_auth_status_reports_token_requirement(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOB_SEARCH_API_TOKEN", "secret-token")

    response = client.get("/api/dashboard/auth")

    assert response.status_code == 200
    assert response.json() == {"token_required": True}
    assert "secret-token" not in response.text


def test_cors_default_does_not_allow_arbitrary_origin(client: TestClient) -> None:
    response = client.get(
        "/api/jobs",
        headers={"Origin": "http://evil.example"},
    )

    assert response.headers.get("access-control-allow-origin") is None


def test_cors_allows_configured_origin(
    db_path: Path,
    _seed_db: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOB_SEARCH_WEB_ALLOWED_ORIGINS", "http://dashboard.example")

    with _client_for_db(db_path) as test_client:
        response = test_client.get(
            "/api/jobs",
            headers={"Origin": "http://dashboard.example"},
        )

    assert response.headers["access-control-allow-origin"] == "http://dashboard.example"


def test_list_jobs_returns_paginated_result(client: TestClient) -> None:
    response = client.get("/api/jobs", params={"limit": 2, "offset": 1})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Data Scientist"


def test_list_jobs_filters(client: TestClient) -> None:
    response = client.get(
        "/api/jobs",
        params={"min_score": 25, "max_score": 35, "site": "indeed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Data Scientist"


def test_list_jobs_console_filters_and_sort(client: TestClient) -> None:
    response = client.get(
        "/api/jobs",
        params=[
            ("sites", "indeed"),
            ("sites", "linkedin"),
            ("job_types", "fulltime"),
            ("location", "san"),
            ("min_salary", "120000"),
            ("date_posted_from", "2026-05-01"),
            ("sort", "title"),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Data Scientist"


def test_get_job_facets(client: TestClient) -> None:
    response = client.get("/api/jobs/facets")

    assert response.status_code == 200
    data = response.json()
    assert data["sites"] == [
        {"value": "indeed", "count": 2},
        {"value": "linkedin", "count": 1},
    ]
    assert data["job_types"] == [
        {"value": "fulltime", "count": 2},
        {"value": "contract", "count": 1},
    ]


def test_get_job_found(client: TestClient) -> None:
    list_response = client.get("/api/jobs")
    job_id = list_response.json()["items"][0]["job_id"]

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id


def test_get_job_not_found(client: TestClient) -> None:
    response = client.get("/api/jobs/not-found")

    assert response.status_code == 404


def test_stats(client: TestClient) -> None:
    response = client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 3
    assert "avg_relevance_score" in data


def test_distribution(client: TestClient) -> None:
    response = client.get("/api/distribution", params={"bin_size": 10})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert all(len(entry) == 2 for entry in data)


def test_semantic_search_no_vector_store(client: TestClient) -> None:
    response = client.get("/api/jobs/search/semantic", params={"q": "python engineer"})

    assert response.status_code == 503


def test_semantic_search_with_vector_store(
    client: TestClient,
    mock_vector_store,
) -> None:
    from job_search_tool import job_service
    from job_search_tool.vector_store import SemanticSearchResult

    active_job_id = client.get("/api/jobs").json()["items"][0]["job_id"]
    mock_vector_store.search.return_value = [
        SemanticSearchResult(
            job_id=active_job_id,
            distance=0.15,
            similarity=0.85,
            metadata={
                "title": "ML Engineer",
                "company": "AI Corp",
                "location": "Remote",
                "relevance_score": 35,
                "site": "linkedin",
                "job_url": "https://example.com/ml",
            },
        )
    ]
    job_service._vs = mock_vector_store

    response = client.get(
        "/api/jobs/search/semantic",
        params={
            "q": "machine learning",
            "n_results": 12,
            "min_score": 30,
            "site": "linkedin",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_id"] == active_job_id
    assert data[0]["similarity"] == 0.85
    assert data[0]["location"] == "Remote"
    assert data[0]["site"] == "linkedin"
    assert data[0]["job_url"] == "https://example.com/ml"
    mock_vector_store.search.assert_called_once_with(
        query="machine learning",
        n_results=12,
        min_score=30,
        site="linkedin",
    )


def test_put_bookmark_is_explicit_and_idempotent(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    first = client.put(f"/api/jobs/{job_id}/bookmark", json={"bookmarked": True})
    second = client.put(f"/api/jobs/{job_id}/bookmark", json={"bookmarked": True})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["bookmarked"] is True
    assert second.json()["bookmarked"] is True


def test_bulk_bookmark_command(client: TestClient) -> None:
    job_ids = [
        item["job_id"]
        for item in client.get("/api/jobs", params={"limit": 2}).json()["items"]
    ]

    response = client.post(
        "/api/jobs/bookmark",
        json={"job_ids": [*job_ids, job_ids[0]], "bookmarked": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["affected_count"] == 2
    assert data["job_ids"] == job_ids
    assert data["bookmarked"] is True


def test_put_applied_is_explicit_and_idempotent(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    first = client.put(f"/api/jobs/{job_id}/applied", json={"applied": True})
    second = client.put(f"/api/jobs/{job_id}/applied", json={"applied": True})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["applied"] is True
    assert second.json()["applied"] is True


def test_bulk_applied_command(client: TestClient) -> None:
    job_ids = [
        item["job_id"]
        for item in client.get("/api/jobs", params={"limit": 2}).json()["items"]
    ]

    response = client.post(
        "/api/jobs/applied",
        json={"job_ids": job_ids, "applied": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["affected_count"] == 2
    assert data["job_ids"] == job_ids
    assert data["applied"] is True


def test_blacklist_jobs(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    response = client.post("/api/jobs/blacklist", json={"job_ids": [job_id, job_id]})

    assert response.status_code == 200
    assert response.json()["affected_count"] == 1
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_delete_jobs_is_not_blacklist(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    response = client.post("/api/jobs/delete", json={"job_ids": [job_id]})

    assert response.status_code == 200
    assert response.json()["affected_count"] == 1
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get("/api/blacklist").json()["total"] == 0


def test_blacklist_list_remove_and_purge(client: TestClient) -> None:
    jobs = client.get("/api/jobs").json()["items"]
    first_id = jobs[0]["job_id"]
    second_id = jobs[1]["job_id"]

    create = client.post("/api/blacklist", json={"job_ids": [first_id]})
    listed = client.get("/api/blacklist", params={"text": jobs[0]["company"]})
    removed = client.post("/api/blacklist/remove", json={"job_ids": [first_id]})
    client.post("/api/blacklist", json={"job_ids": [second_id]})
    purged = client.post("/api/blacklist/purge", json={})

    assert create.status_code == 200
    assert create.json()["affected_count"] == 1
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["job_id"] == first_id
    assert removed.status_code == 200
    assert removed.json()["affected_count"] == 1
    assert purged.status_code == 200
    assert purged.json()["affected_count"] == 1
    assert client.get("/api/blacklist").json()["total"] == 0


def test_export_selected_jobs_as_json(client: TestClient) -> None:
    job_ids = [
        item["job_id"]
        for item in client.get("/api/jobs", params={"limit": 2}).json()["items"]
    ]

    response = client.post(
        "/api/export/jobs",
        json={"job_ids": job_ids, "format": "json"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert len(data) == 2
    assert {item["job_id"] for item in data} == set(job_ids)


def test_export_filtered_jobs_as_csv(client: TestClient) -> None:
    response = client.get(
        "/api/export/jobs",
        params={"format": "csv", "site": "indeed", "sort": "title"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Data Scientist" in response.text
    assert "Frontend Developer" in response.text
    assert "Backend Engineer" not in response.text


def test_manual_cleanup_routes(client: TestClient) -> None:
    stale = client.post("/api/cleanup/delete-stale", json={"days": 0})
    below_score = client.post("/api/cleanup/delete-below-score", json={"score": 35})
    purge = client.post("/api/cleanup/purge-blacklist", json={})

    assert stale.status_code == 200
    assert below_score.status_code == 200
    assert purge.status_code == 200
    assert "affected_count" in stale.json()
    assert "affected_count" in below_score.json()
    assert "affected_count" in purge.json()


def test_cleanup_preview(client: TestClient) -> None:
    response = client.get("/api/cleanup/preview")

    assert response.status_code == 200
    data = response.json()
    assert set(data) >= {
        "deleted_below_score",
        "deleted_stale",
        "purged_blacklist",
        "total_deleted",
    }


def test_cleanup_run(client: TestClient) -> None:
    response = client.post("/api/cleanup/run")

    assert response.status_code == 200
    data = response.json()
    assert set(data) >= {
        "deleted_below_score",
        "deleted_stale",
        "purged_blacklist",
        "total_deleted",
    }


def test_standalone_api_module_is_removed() -> None:
    assert not (PROJECT_ROOT / "src/job_search_tool/api_server.py").exists()
