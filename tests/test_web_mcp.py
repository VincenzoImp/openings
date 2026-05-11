"""Tests for the unified web MCP server."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from job_search_tool.database import JobDatabase
from job_search_tool.models import Job


PROJECT_ROOT = Path(__file__).parent.parent


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
                job_url="https://example.com/backend",
                is_remote=True,
            ),
            Job(
                title="Frontend Developer",
                company="Widget Inc",
                location="New York",
                relevance_score=20,
                description="React and TypeScript.",
                job_url="https://example.com/frontend",
                is_remote=False,
            ),
        ]
        db.save_job(jobs[0], site="linkedin")
        db.save_job(jobs[1], site="indeed")
        yield db
        db.close()


@pytest.fixture(autouse=True)
def patch_service_globals(temp_db: JobDatabase):
    """Patch the shared job_service singletons used by web MCP tools."""
    from job_search_tool import job_service

    job_service._db = temp_db
    job_service._vs = None
    job_service._vs_attempted = True
    yield
    job_service.reset_singletons()


@pytest.mark.asyncio()
async def test_create_mcp_server_exposes_tools() -> None:
    from job_search_tool.web.mcp import create_mcp_server

    server = create_mcp_server()
    tools = await server.list_tools()

    assert {tool.name for tool in tools} >= {
        "list_jobs",
        "get_job",
        "search_similar",
        "get_statistics",
        "get_score_distribution",
        "set_bookmarked",
        "set_applied",
        "blacklist_jobs",
        "preview_cleanup",
        "run_cleanup",
        "get_settings_documentation",
    }


def test_list_jobs_returns_filtered_summaries() -> None:
    from job_search_tool.web.mcp import list_jobs

    data = json.loads(list_jobs(min_score=30, site="linkedin"))

    assert len(data) == 1
    assert data[0]["title"] == "Backend Engineer"
    assert set(data[0]) == {
        "job_id",
        "title",
        "company",
        "location",
        "relevance_score",
        "site",
        "bookmarked",
        "applied",
        "first_seen",
        "job_url",
    }


def test_set_bookmarked_is_explicit_and_idempotent(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import set_bookmarked

    job_id = temp_db.get_all_jobs()[0].job_id

    first = json.loads(set_bookmarked(job_id, True))
    second = json.loads(set_bookmarked(job_id, True))

    assert first["success"] is True
    assert second["success"] is True
    assert first["bookmarked"] is True
    assert second["bookmarked"] is True


def test_set_applied_is_explicit_and_idempotent(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import set_applied

    job_id = temp_db.get_all_jobs()[0].job_id

    first = json.loads(set_applied(job_id, True))
    second = json.loads(set_applied(job_id, True))

    assert first["success"] is True
    assert second["success"] is True
    assert first["applied"] is True
    assert second["applied"] is True


def test_blacklist_jobs_returns_count(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import blacklist_jobs, get_job

    job_id = temp_db.get_all_jobs()[0].job_id

    result = json.loads(blacklist_jobs([job_id, job_id]))

    assert result["success"] is True
    assert result["affected_count"] == 1
    assert "error" in json.loads(get_job(job_id))


def test_cleanup_tools_return_counts() -> None:
    from job_search_tool.web.mcp import preview_cleanup, run_cleanup

    preview = json.loads(preview_cleanup())
    result = json.loads(run_cleanup())

    assert set(preview) >= {
        "deleted_below_score",
        "deleted_stale",
        "purged_blacklist",
        "total_deleted",
    }
    assert set(result) >= {
        "deleted_below_score",
        "deleted_stale",
        "purged_blacklist",
        "total_deleted",
    }


def test_mcp_path_is_mounted_in_web_app() -> None:
    from job_search_tool.web.app import create_app

    app = create_app()

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_mcp_endpoint_accepts_configured_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    from job_search_tool.web.app import create_app

    monkeypatch.setenv("JOB_SEARCH_WEB_ALLOWED_HOSTS", "testserver")

    with TestClient(create_app(), raise_server_exceptions=True) as client:
        response = client.get("/mcp/")

    assert response.status_code != 421


def test_standalone_mcp_module_is_removed() -> None:
    assert not (PROJECT_ROOT / "src/job_search_tool/mcp_server.py").exists()
