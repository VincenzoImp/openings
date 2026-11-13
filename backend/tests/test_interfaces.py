"""Release contract: declarations, the running app and owner-only access agree."""

import json
import re

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from mcp.types import ToolAnnotations

from openings.app import create_app
from openings.interfaces import catalog
from openings.interfaces.registry import (
    Operation,
    Param,
    Route,
    Tool,
    bind_mcp,
    bind_rest,
    capability_entries,
)
from openings.mcp_server import OpeningsMCP


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
    declared = {operation.canonical_name for operation in operations if operation.tool}
    assert tools == declared
    templates = {item.uri_template for item in await app.state.mcp.list_resource_templates()}
    prompts = await app.state.mcp.list_prompts()
    assert templates == {surface.name for surface in surfaces if surface.kind == "resource"}
    assert prompts and any(surface.kind == "prompt" for surface in surfaces)
    names = [operation.canonical_name for operation in operations]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", name) for name in names)
    assert len({operation.id for operation in operations}) == len(operations)


# One representative call per owner-only operation: REST request arguments and MCP
# tool arguments. An operation declared access=owner without an entry fails the test.
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
    """Every operation declared access=owner returns forbidden to an agent token."""
    app = create_app(tmp_path / "access.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    agent = app.state.auth.create_token("Synthetic agent", "agent")["token"]
    owner = app.state.auth.create_token("Synthetic owner token")["token"]
    marked = {
        operation.id: {
            "rest": [
                {"method": route.method, "path": "/api/v1" + route.path} for route in operation.rest
            ],
            "mcp": [operation.canonical_name] if operation.tool else [],
        }
        for operation in catalog()[0]
        if operation.access == "owner"
    }
    assert set(marked) == set(OWNER_ONLY_CALLS)
    with TestClient(app, base_url="http://localhost:8080") as client:
        capabilities = client.get(
            "/api/v1/capabilities", headers={"Authorization": "Bearer " + agent}
        ).json()
        assert capabilities["token_kind"] == "agent"
        assert {item["name"] for item in capabilities["operations"] if "access" in item} == {
            operation.canonical_name for operation in catalog()[0] if operation.access == "owner"
        }
        owner_view = client.get(
            "/api/v1/capabilities", headers={"Authorization": "Bearer " + owner}
        )
        assert owner_view.json()["token_kind"] == "owner"
        assert len(owner_view.content) < 10_000

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


class Greeter:
    def greet(self, name, loud):
        return {"greeting": ("HELLO " if loud else "Hello ") + name}


@pytest.mark.asyncio
async def test_one_declaration_gives_a_route_a_tool_and_a_capability():
    """A synthetic operation, declared once, binds to REST and MCP under one name."""
    operation = Operation(
        "greetings.read",
        "greetings",
        "get",
        "Synthetic",
        "Greet someone",
        params=(Param("name", str), Param("loud", bool, False)),
        call=lambda s, name, loud: s.greet(name, loud),
        rest=(Route("GET", "/greetings/{name}", "greeting_get"),),
        tool=Tool(ToolAnnotations(readOnlyHint=True), "Greet someone."),
    )
    assert operation.canonical_name == "greetings_get"
    router, mcp = APIRouter(prefix="/api/v1"), OpeningsMCP("Synthetic")
    bind_rest(router, (operation,), Greeter())
    bind_mcp(mcp, (operation,), Greeter())
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/api/v1/greetings/Ada?loud=true").json() == {"greeting": "HELLO Ada"}
    assert app.openapi()["paths"]["/api/v1/greetings/{name}"]["get"]["summary"] == "Greeting Get"
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert set(tools) == {"greetings_get"}
    assert tools["greetings_get"].description == "Greet someone."
    result = await mcp.call_tool("greetings_get", {"name": "Ada"})
    assert "Hello Ada" in result.content[0].text
    assert capability_entries((operation,)) == [
        {"name": "greetings_get", "method": "GET", "path": "/greetings/{name}"}
    ]
