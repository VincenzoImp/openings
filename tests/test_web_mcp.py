"""Tests for the unified web MCP server."""

from __future__ import annotations

from datetime import date
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

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
                description="React and TypeScript.",
                job_url="https://example.com/frontend",
                job_type="contract",
                is_remote=False,
                date_posted=date(2026, 5, 3),
                min_amount=70000,
                max_amount=90000,
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
        "list_blacklisted_jobs",
        "search_similar",
        "get_statistics",
        "get_score_distribution",
        "get_facets",
        "set_bookmarked",
        "set_applied",
        "blacklist_jobs",
        "unblacklist_jobs",
        "delete_jobs",
        "delete_jobs_below_score",
        "delete_stale_jobs",
        "purge_blacklist",
        "preview_cleanup",
        "run_cleanup",
        "export_jobs",
        "get_settings_documentation",
    }


def test_list_jobs_returns_filtered_summaries() -> None:
    from job_search_tool.web.mcp import list_jobs

    data = json.loads(list_jobs(min_score=30, site="linkedin"))

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Backend Engineer"
    assert set(data["items"][0]) == {
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


def test_list_jobs_supports_console_filters() -> None:
    from job_search_tool.web.mcp import list_jobs

    data = json.loads(
        list_jobs(
            sites=["indeed"],
            location="new",
            job_types=["contract"],
            min_salary=80000,
            date_posted_from="2026-05-01",
            sort="title",
        )
    )

    assert data["total"] == 1
    assert data["items"][0]["title"] == "Frontend Developer"


def test_search_similar_supports_console_filters() -> None:
    from job_search_tool import job_service
    from job_search_tool.vector_store import SemanticSearchResult
    from job_search_tool.web.mcp import search_similar

    active_job_id = job_service.get_db().get_all_jobs()[0].job_id
    job_service._vs = MagicMock()
    job_service._vs.search.return_value = [
        SemanticSearchResult(
            job_id=active_job_id,
            distance=0.12,
            similarity=0.88,
            metadata={
                "title": "ML Engineer",
                "company": "AI Corp",
                "location": "Remote",
                "relevance_score": 44,
                "site": "linkedin",
                "job_url": "https://example.com/ml",
            },
        )
    ]

    data = json.loads(
        search_similar(
            "machine learning",
            n_results=5,
            min_score=30,
            site="linkedin",
        )
    )

    assert data == [
        {
            "job_id": active_job_id,
            "title": "ML Engineer",
            "company": "AI Corp",
            "location": "Remote",
            "similarity": 0.88,
            "relevance_score": 44,
            "site": "linkedin",
            "job_url": "https://example.com/ml",
        }
    ]
    job_service._vs.search.assert_called_once_with(
        query="machine learning",
        n_results=5,
        min_score=30,
        site="linkedin",
    )


def test_set_bookmarked_is_explicit_and_idempotent(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import set_bookmarked

    job_id = temp_db.get_all_jobs()[0].job_id

    first = json.loads(set_bookmarked([job_id], True))
    second = json.loads(set_bookmarked([job_id], True))

    assert first["success"] is True
    assert second["success"] is True
    assert first["job_ids"] == [job_id]
    assert first["bookmarked"] is True
    assert second["bookmarked"] is True


def test_set_applied_is_explicit_and_idempotent(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import set_applied

    job_id = temp_db.get_all_jobs()[0].job_id

    first = json.loads(set_applied([job_id], True))
    second = json.loads(set_applied([job_id], True))

    assert first["success"] is True
    assert second["success"] is True
    assert first["job_ids"] == [job_id]
    assert first["applied"] is True
    assert second["applied"] is True


def test_blacklist_jobs_returns_count(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import blacklist_jobs, get_job

    job_id = temp_db.get_all_jobs()[0].job_id

    result = json.loads(blacklist_jobs([job_id, job_id]))

    assert result["success"] is True
    assert result["affected_count"] == 1
    assert "error" in json.loads(get_job(job_id))


def test_blacklist_list_unblacklist_and_delete_tools(temp_db: JobDatabase) -> None:
    from job_search_tool.web.mcp import (
        blacklist_jobs,
        delete_jobs,
        get_job,
        list_blacklisted_jobs,
        unblacklist_jobs,
    )

    jobs = temp_db.get_all_jobs()
    blacklist_id = jobs[0].job_id
    delete_id = jobs[1].job_id

    blacklisted = json.loads(blacklist_jobs([blacklist_id]))
    listed = json.loads(list_blacklisted_jobs(text=jobs[0].company))
    unblacklisted = json.loads(unblacklist_jobs([blacklist_id]))
    deleted = json.loads(delete_jobs([delete_id]))

    assert blacklisted["affected_count"] == 1
    assert listed["total"] == 1
    assert listed["items"][0]["job_id"] == blacklist_id
    assert unblacklisted["affected_count"] == 1
    assert deleted["affected_count"] == 1
    assert "error" in json.loads(get_job(delete_id))
    assert json.loads(list_blacklisted_jobs())["total"] == 0


def test_facets_export_and_manual_cleanup_tools() -> None:
    from job_search_tool.web.mcp import (
        delete_jobs_below_score,
        export_jobs,
        get_facets,
        purge_blacklist,
    )

    facets = json.loads(get_facets())
    exported = json.loads(export_jobs(format="json", site="indeed"))
    below_score = json.loads(delete_jobs_below_score(25))
    purge = json.loads(purge_blacklist())

    assert facets["sites"] == [
        {"value": "indeed", "count": 1},
        {"value": "linkedin", "count": 1},
    ]
    assert len(exported) == 1
    assert exported[0]["title"] == "Frontend Developer"
    assert below_score["affected_count"] == 1
    assert "affected_count" in purge


def test_export_jobs_supports_console_filters() -> None:
    from job_search_tool.web.mcp import export_jobs

    exported = json.loads(
        export_jobs(
            format="json",
            sites=["indeed"],
            job_types=["contract"],
            min_salary=80000,
            date_posted_from="2026-05-01",
            sort="title",
        )
    )

    assert len(exported) == 1
    assert exported[0]["title"] == "Frontend Developer"


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
