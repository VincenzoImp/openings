"""Tests for the REST API server."""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from database import JobDatabase
from models import Job


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path():
    """Temporary DB path shared between the API client and direct access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture()
def _seed_db(db_path):
    """Seed the database with test data (runs once, closes connection after)."""
    db = JobDatabase(db_path)
    jobs = [
        Job(
            title="Backend Engineer",
            company="Acme Corp",
            location="Remote",
            relevance_score=40,
            job_url="https://example.com/1",
            job_type="fulltime",
            is_remote=True,
        ),
        Job(
            title="Frontend Developer",
            company="Widget Inc",
            location="New York, NY",
            relevance_score=20,
            job_url="https://example.com/2",
            job_type="fulltime",
            is_remote=False,
        ),
        Job(
            title="Data Scientist",
            company="DataCo",
            location="San Francisco, CA",
            relevance_score=30,
            job_url="https://example.com/3",
        ),
    ]
    for job in jobs:
        db.save_job(job, site="indeed")
    db.close()


@pytest.fixture()
def client(db_path, _seed_db):
    """Create a FastAPI test client backed by the seeded DB."""
    import api_server
    import job_service

    db = JobDatabase(db_path)
    db.close()

    # Patch the shared service singletons
    job_service._db = db
    job_service._vs = None
    job_service._vs_attempted = True

    api_server.app.router.lifespan_context = _noop_lifespan
    with TestClient(api_server.app, raise_server_exceptions=True) as c:
        yield c
    db.close()
    job_service.reset_singletons()


@pytest.fixture()
def mock_vector_store():
    """Create a mock vector store returning canned results."""
    from vector_store import SemanticSearchResult

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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["jobs_count"] == 3


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------


def test_list_jobs_default(client):
    resp = client.get("/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["relevance_score"] >= data[1]["relevance_score"]


def test_list_jobs_limit(client):
    resp = client.get("/jobs", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_jobs_offset(client):
    resp = client.get("/jobs", params={"offset": 2, "limit": 10})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_jobs_min_score(client):
    resp = client.get("/jobs", params={"min_score": 30})
    assert resp.status_code == 200
    data = resp.json()
    assert all(j["relevance_score"] >= 30 for j in data)


def test_list_jobs_bookmarked_filter(client):
    resp = client.get("/jobs")
    job_id = resp.json()[0]["job_id"]
    client.post(f"/jobs/{job_id}/bookmark")

    resp = client.get("/jobs", params={"bookmarked": True})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["bookmarked"] is True


def test_list_jobs_sort_date(client):
    resp = client.get("/jobs", params={"sort": "date"})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ---------------------------------------------------------------------------
# Get single job
# ---------------------------------------------------------------------------


def test_get_job_found(client):
    resp = client.get("/jobs")
    job_id = resp.json()[0]["job_id"]
    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id


def test_get_job_not_found(client):
    resp = client.get("/jobs/nonexistent_id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Stats and distribution
# ---------------------------------------------------------------------------


def test_stats(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_jobs" in data
    assert data["total_jobs"] == 3


def test_distribution(client):
    resp = client.get("/distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for entry in data:
        assert len(entry) == 2


def test_distribution_custom_bin(client):
    resp = client.get("/distribution", params={"bin_size": 10})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bookmark / Apply
# ---------------------------------------------------------------------------


def test_bookmark_toggle(client):
    resp = client.get("/jobs")
    job_id = resp.json()[0]["job_id"]

    resp = client.post(f"/jobs/{job_id}/bookmark")
    assert resp.status_code == 200
    assert resp.json()["bookmarked"] is True

    resp = client.post(f"/jobs/{job_id}/bookmark")
    assert resp.status_code == 200
    assert resp.json()["bookmarked"] is False


def test_bookmark_not_found(client):
    resp = client.post("/jobs/nonexistent/bookmark")
    assert resp.status_code == 404


def test_apply_toggle(client):
    resp = client.get("/jobs")
    job_id = resp.json()[0]["job_id"]

    resp = client.post(f"/jobs/{job_id}/apply")
    assert resp.status_code == 200
    assert resp.json()["applied"] is True

    resp = client.post(f"/jobs/{job_id}/apply")
    assert resp.status_code == 200
    assert resp.json()["applied"] is False


def test_apply_not_found(client):
    resp = client.post("/jobs/nonexistent/apply")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_job(client):
    resp = client.get("/jobs")
    job_id = resp.json()[0]["job_id"]

    resp = client.delete(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 404


def test_delete_below_score(client):
    resp = client.delete("/jobs/below-score/25")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_count"] >= 1


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


def test_semantic_search_no_vector_store(client):
    resp = client.get("/jobs/search/semantic", params={"q": "python engineer"})
    assert resp.status_code == 503


def test_semantic_search_with_vector_store(client, mock_vector_store):
    import job_service

    job_service._vs = mock_vector_store
    resp = client.get("/jobs/search/semantic", params={"q": "machine learning"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["job_id"] == "abc123"
    assert "similarity" in data[0]
    job_service._vs = None
