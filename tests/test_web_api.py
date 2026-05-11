"""Tests for the unified web REST API."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
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
        ),
        Job(
            title="Frontend Developer",
            company="Widget Inc",
            location="New York",
            relevance_score=20,
            job_url="https://example.com/frontend",
            job_type="contract",
            is_remote=False,
        ),
        Job(
            title="Data Scientist",
            company="DataCo",
            location="San Francisco",
            relevance_score=30,
            job_url="https://example.com/data",
            job_type="fulltime",
            is_remote=False,
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

    job_service._vs = mock_vector_store

    response = client.get("/api/jobs/search/semantic", params={"q": "machine learning"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_id"] == "abc123"
    assert data[0]["similarity"] == 0.85


def test_put_bookmark_is_explicit_and_idempotent(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    first = client.put(f"/api/jobs/{job_id}/bookmark", json={"bookmarked": True})
    second = client.put(f"/api/jobs/{job_id}/bookmark", json={"bookmarked": True})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["bookmarked"] is True
    assert second.json()["bookmarked"] is True


def test_put_applied_is_explicit_and_idempotent(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    first = client.put(f"/api/jobs/{job_id}/applied", json={"applied": True})
    second = client.put(f"/api/jobs/{job_id}/applied", json={"applied": True})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["applied"] is True
    assert second.json()["applied"] is True


def test_blacklist_jobs(client: TestClient) -> None:
    job_id = client.get("/api/jobs").json()["items"][0]["job_id"]

    response = client.post("/api/jobs/blacklist", json={"job_ids": [job_id, job_id]})

    assert response.status_code == 200
    assert response.json()["affected_count"] == 1
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


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
