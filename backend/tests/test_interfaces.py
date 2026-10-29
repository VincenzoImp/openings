"""Release contract: every advertised operation resolves on REST and MCP."""

import re

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app


def route_path(path):
    return re.sub(r"\{[^}]+\}", "{}", path).rstrip("/")


@pytest.mark.asyncio
async def test_operation_inventory_covers_runtime_interfaces(tmp_path):
    app = create_app(tmp_path / "operations.sqlite", start_worker=False)
    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        assert session.status_code == 200
        inventory = client.get("/api/v1/capabilities").json()
    tools = {tool.name: tool for tool in await app.state.mcp.list_tools()}
    routes = {
        (method.upper(), route_path(path))
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }
    advertised = set()
    for operation in inventory["operations"]:
        assert operation["dashboard"], operation["id"]
        for route in operation["rest"]:
            identity = (route["method"], route_path(route["path"]))
            assert identity in routes, (operation["id"], identity)
            advertised.add(identity)
        for name in operation["mcp"]:
            assert name in tools, (operation["id"], name)
    for exception in inventory["exceptions"]:
        assert exception["reason"]
        advertised.update((item["method"], route_path(item["path"])) for item in exception["rest"])
    assert not {route for route in routes - advertised if route[1].startswith("/api/v1")}
    assert set(tools) == {
        name for operation in inventory["operations"] for name in operation["mcp"]
    }
    assert all(tool.annotations is not None for tool in tools.values())
