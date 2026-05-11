"""Tests for serving built dashboard assets from the web server."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from job_search_tool.database import JobDatabase


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    from job_search_tool import job_service
    from job_search_tool.web.app import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        static_dir = Path(tmpdir) / "frontend"
        assets_dir = static_dir / "assets"
        assets_dir.mkdir(parents=True)
        (static_dir / "index.html").write_text(
            '<!doctype html><div id="root">Built Dashboard</div>',
            encoding="utf-8",
        )
        (assets_dir / "app.js").write_text(
            "console.log('dashboard');", encoding="utf-8"
        )

        db = JobDatabase(Path(tmpdir) / "jobs.db")
        db.close()

        monkeypatch.setenv("JOB_SEARCH_FRONTEND_DIST", str(static_dir))
        monkeypatch.setenv("JOB_SEARCH_WEB_ALLOWED_HOSTS", "testserver")
        job_service._db = db
        job_service._vs = None
        job_service._vs_attempted = True

        with TestClient(create_app(), raise_server_exceptions=True) as test_client:
            yield test_client

        db.close()
        job_service.reset_singletons()


def test_root_serves_built_dashboard(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Built Dashboard" in response.text


def test_assets_are_served(client: TestClient) -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "dashboard" in response.text


def test_static_serving_does_not_swallow_api(client: TestClient) -> None:
    response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_static_serving_does_not_swallow_mcp(client: TestClient) -> None:
    response = client.get("/mcp/")

    assert response.status_code != 404
