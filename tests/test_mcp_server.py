"""Tests for the MCP server tools.

Tests call the Python functions directly (not via MCP protocol) with mocked
DB and vector store dependencies.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from database import JobDatabase
from models import Job


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_db():
    """Create a temporary JobDatabase with test jobs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = JobDatabase(Path(tmpdir) / "test.db")
        jobs = [
            Job(
                title="Backend Engineer",
                company="Acme Corp",
                location="Remote",
                relevance_score=40,
                description="Build scalable Python services.",
                job_url="https://example.com/1",
            ),
            Job(
                title="Frontend Developer",
                company="Widget Inc",
                location="New York, NY",
                relevance_score=20,
                description="React and TypeScript.",
                job_url="https://example.com/2",
            ),
        ]
        for job in jobs:
            db.save_job(job, site="indeed")
        yield db
        db.close()


@pytest.fixture()
def mock_vs():
    """Create a mock vector store."""
    from vector_store import SemanticSearchResult

    vs = MagicMock()
    vs.search.return_value = [
        SemanticSearchResult(
            job_id="abc123",
            distance=0.1,
            similarity=0.9,
            metadata={
                "title": "ML Engineer",
                "company": "AI Corp",
                "relevance_score": 35,
            },
        )
    ]
    return vs


@pytest.fixture(autouse=True)
def patch_service_globals(temp_db, mock_vs):
    """Patch the shared job_service singletons used by mcp_server."""
    import job_service

    job_service._db = temp_db
    job_service._vs = mock_vs
    job_service._vs_attempted = True
    yield
    job_service.reset_singletons()


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------


def test_list_jobs_returns_valid_json():
    from mcp_server import list_jobs

    result = list_jobs()
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 2


def test_list_jobs_respects_limit():
    from mcp_server import list_jobs

    result = list_jobs(limit=1)
    data = json.loads(result)
    assert len(data) == 1


def test_list_jobs_min_score_filter():
    from mcp_server import list_jobs

    result = list_jobs(min_score=30)
    data = json.loads(result)
    assert all(j["relevance_score"] >= 30 for j in data)


def test_list_jobs_bookmarked_filter(temp_db):
    from mcp_server import list_jobs

    result = list_jobs(bookmarked_only=True)
    data = json.loads(result)
    assert len(data) == 0


def test_list_jobs_summary_fields():
    from mcp_server import list_jobs

    result = list_jobs()
    data = json.loads(result)
    job = data[0]
    # Should have summary fields but NOT description
    assert "job_id" in job
    assert "title" in job
    assert "company" in job
    assert "relevance_score" in job
    assert "description" not in job


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------


def test_get_job_returns_full_detail(temp_db):
    from mcp_server import get_job

    jobs = temp_db.get_all_jobs()
    result = get_job(jobs[0].job_id)
    data = json.loads(result)
    assert "description" in data
    assert data["job_id"] == jobs[0].job_id


def test_get_job_not_found():
    from mcp_server import get_job

    result = get_job("nonexistent_id")
    data = json.loads(result)
    assert "error" in data


# ---------------------------------------------------------------------------
# search_similar
# ---------------------------------------------------------------------------


def test_search_similar_returns_results():
    from mcp_server import search_similar

    result = search_similar("python backend")
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["job_id"] == "abc123"
    assert "similarity" in data[0]


def test_search_similar_no_vector_store():
    from mcp_server import search_similar

    with patch("mcp_server.get_vs", return_value=None):
        result = search_similar("test query")
        data = json.loads(result)
        assert "error" in data


# ---------------------------------------------------------------------------
# get_statistics
# ---------------------------------------------------------------------------


def test_get_statistics():
    from mcp_server import get_statistics

    result = get_statistics()
    data = json.loads(result)
    assert "total_jobs" in data
    assert data["total_jobs"] == 2


# ---------------------------------------------------------------------------
# get_score_distribution
# ---------------------------------------------------------------------------


def test_get_score_distribution():
    from mcp_server import get_score_distribution

    result = get_score_distribution(bin_size=10)
    data = json.loads(result)
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# bookmark_job / apply_job
# ---------------------------------------------------------------------------


def test_bookmark_job(temp_db):
    from mcp_server import bookmark_job

    jobs = temp_db.get_all_jobs()
    result = bookmark_job(jobs[0].job_id)
    data = json.loads(result)
    assert data["bookmarked"] is True

    # Toggle back
    result = bookmark_job(jobs[0].job_id)
    data = json.loads(result)
    assert data["bookmarked"] is False


def test_bookmark_job_not_found():
    from mcp_server import bookmark_job

    result = bookmark_job("nonexistent")
    data = json.loads(result)
    assert "error" in data


def test_apply_job(temp_db):
    from mcp_server import apply_job

    jobs = temp_db.get_all_jobs()
    result = apply_job(jobs[0].job_id)
    data = json.loads(result)
    assert data["applied"] is True


def test_apply_job_not_found():
    from mcp_server import apply_job

    result = apply_job("nonexistent")
    data = json.loads(result)
    assert "error" in data


# ---------------------------------------------------------------------------
# delete_job
# ---------------------------------------------------------------------------


def test_delete_job(temp_db):
    from mcp_server import delete_job

    jobs = temp_db.get_all_jobs()
    result = delete_job(jobs[0].job_id)
    data = json.loads(result)
    assert data["deleted"] is True

    # Verify blacklisted
    assert temp_db.is_job_blacklisted(jobs[0].job_id)


def test_delete_jobs_below_score():
    from mcp_server import delete_jobs_below_score

    result = delete_jobs_below_score(25)
    data = json.loads(result)
    assert "deleted_count" in data
    assert data["deleted_count"] >= 1


# ---------------------------------------------------------------------------
# get_settings_documentation
# ---------------------------------------------------------------------------


def test_get_settings_documentation():
    from mcp_server import get_settings_documentation

    text = get_settings_documentation()
    assert isinstance(text, str)
    assert len(text) > 500
    # Verify key sections are present
    for section in [
        "search",
        "queries",
        "scoring",
        "parallel",
        "retry",
        "throttling",
        "scheduler",
        "notifications",
        "database",
        "vector_search",
    ]:
        assert section in text.lower(), f"Section '{section}' missing from docs"
