"""Release contract: every advertised operation resolves on REST and MCP."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.interfaces import catalog, inventory_text


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


def test_operation_inventory_is_generated_from_the_declarations():
    """operation-inventory.json is what scripts/inventory.py writes from the declarations."""
    path = Path(__file__).resolve().parents[2] / "backend/openings/operation-inventory.json"
    assert path.read_text() == inventory_text(), "Run `uv run python scripts/inventory.py`."


@pytest.mark.asyncio
async def test_every_declared_route_tool_and_surface_is_registered(tmp_path):
    """Declarations and the running app agree; each operation has a unique canonical name."""
    app = create_app(tmp_path / "declared.sqlite", start_worker=False)
    operations, exemptions, surfaces = catalog()
    paths = app.openapi()["paths"]
    for operation in operations:
        for route in operation.rest:
            schema = paths.get("/api/v1" + route.path.replace(":path", ""), {})
            assert route.method.lower() in schema, (operation.id, route.method, route.path)
            if not route.custom:
                assert schema[route.method.lower()]["operationId"].startswith(route.name + "_")
    for exemption in exemptions:
        for route in exemption.rest:
            if not route.absolute:
                assert route.method.lower() in paths["/api/v1" + route.path], exemption.id
    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    declared = {operation.tool.name for operation in operations if operation.tool}
    assert tools == declared
    templates = {item.uri_template for item in await app.state.mcp.list_resource_templates()}
    prompts = await app.state.mcp.list_prompts()
    assert templates == {surface.name for surface in surfaces if surface.kind == "resource"}
    assert prompts and any(surface.kind == "prompt" for surface in surfaces)
    names = [operation.canonical_name for operation in operations]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", name) for name in names)
    assert len({operation.id for operation in operations}) == len(operations)


def test_parity_matrix_is_current():
    """The committed matrix matches the inventory, contract and dashboard source."""
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/parity_matrix.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


# One representative call per owner-only operation: REST request arguments and MCP
# tool arguments. An operation marked access=owner without an entry fails the test.
OWNER_ONLY_CALLS = {
    "password.update": (
        {"json": {"password": "another-synthetic-password"}},
        {"value": {"password": "another-synthetic-password"}},
    ),
    "tokens.list": ({}, {}),
    "tokens.create": ({"json": {"name": "Escalation"}}, {"value": {"name": "Escalation"}}),
    "tokens.revoke": ({}, {"token_id": "missing"}),
    "backup.restore": ({"content": b"SQLite format 3\x00"}, {}),
    "questions.answer": (
        {"json": {"expected_version": 1, "answer": "Synthetic"}},
        {"question_id": "missing", "value": {"expected_version": 1, "answer": "Synthetic"}},
    ),
    "requests.create": (
        {"json": {"text": "Prepare this one too."}},
        {"value": {"text": "Prepare this one too."}},
    ),
    "requests.withdraw": (
        {"json": {"expected_version": 1}},
        {"request_id": "missing", "value": {"expected_version": 1}},
    ),
    "policy.confirm": (
        {"json": {"expected_version": 1}},
        {"item_id": "missing", "value": {"expected_version": 1}},
    ),
}


def test_owner_only_operations_refuse_an_agent_token_on_rest_and_mcp(tmp_path):
    """Every operation the inventory marks access=owner returns forbidden to an agent token."""
    app = create_app(tmp_path / "access.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    agent = app.state.auth.create_token("Synthetic agent", "agent")["token"]
    owner = app.state.auth.create_token("Synthetic owner token")["token"]
    with TestClient(app, base_url="http://localhost:8080") as client:
        inventory = client.get(
            "/api/v1/capabilities", headers={"Authorization": "Bearer " + agent}
        ).json()
        assert set(inventory["access"]) == {"owner", "default"}
        marked = {
            operation["id"]: operation
            for operation in inventory["operations"]
            if operation.get("access") == "owner"
        }
        assert all(
            operation.get("access", "owner") == "owner" for operation in inventory["operations"]
        )
        assert set(marked) == set(OWNER_ONLY_CALLS)

        def over_mcp(token, name, arguments):
            response = client.post(
                "/mcp",
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            result = response.json()["result"]
            if not result.get("isError"):
                return None
            return json.loads(result["content"][0]["text"])["error"]["code"]

        for identifier, operation in marked.items():
            request, arguments = OWNER_ONLY_CALLS[identifier]
            for route in operation["rest"]:
                path = re.sub(r"\{[^}]+\}", "missing", route["path"])
                response = client.request(
                    route["method"], path, headers={"Authorization": "Bearer " + agent}, **request
                )
                assert response.status_code == 403, (identifier, response.text)
                assert response.json()["error"]["code"] == "forbidden", identifier
            for name in operation["mcp"]:
                assert over_mcp(agent, name, arguments) == "forbidden", (identifier, name)
        # The same calls are not refused for want of authority with an owner token.
        # The password change runs last: it is the only one that succeeds with these inputs.
        for identifier in sorted(marked, key=lambda item: item == "password.update"):
            if identifier == "backup.restore":
                continue  # A real restore is covered by test_token_scopes.py.
            for name in marked[identifier]["mcp"]:
                assert over_mcp(owner, name, OWNER_ONLY_CALLS[identifier][1]) != "forbidden"
