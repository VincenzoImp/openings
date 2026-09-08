"""Serving the built dashboard next to the API and MCP endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(env, tmp_path, monkeypatch: pytest.MonkeyPatch):
    from openings.web.app import create_app

    static_dir = tmp_path / "frontend"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        '<!doctype html><div id="root">Built Dashboard</div>', encoding="utf-8"
    )
    (assets_dir / "app.js").write_text("console.log('dashboard');", encoding="utf-8")
    monkeypatch.setenv("OPENINGS_FRONTEND_DIST", str(static_dir))

    with TestClient(create_app(), raise_server_exceptions=True) as test_client:
        yield test_client


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
