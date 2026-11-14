"""One-way parity from the declarations: every API route is one operation or a listed
transport route, and every operation that is not owner-only is one MCP tool."""

import re

from openings.interfaces import OPERATIONS, TRANSPORT_ONLY


def key(method, path):
    return method.upper(), re.sub(r"\{[^}]+\}", "{}", path.replace(":path", "")).rstrip("/")


async def test_routes_and_tools_follow_the_operations(app):
    served = {key(m, path) for path, methods in app.openapi()["paths"].items() for m in methods}
    operations = [key(method, "/api/v1" + path) for op in OPERATIONS for method, path in op.routes]
    transport = [
        key(method, path if path in ("/health", "/mcp/") else "/api/v1" + path)
        for method, path, _ in TRANSPORT_ONLY
    ]
    api = {route for route in served if route[1].startswith(("/api/v1", "/health"))}
    assert len(operations + transport) == len(set(operations + transport)), "Declared twice"
    assert api == set(operations) | set(transport) - {key("POST", "/mcp/")}
    assert all(reason.strip() and "\n" not in reason for *_, reason in TRANSPORT_ONLY)

    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    open_to_agents = {op.name for op in OPERATIONS if op.access != "owner"}
    assert tools == open_to_agents, "Every non-owner operation is one tool, and only those"
    assert len({op.name for op in OPERATIONS}) == len(OPERATIONS)
    assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", op.name) for op in OPERATIONS)


def test_a_read_and_a_write_answer_alike_over_rest_and_mcp(owner_token, mcp):
    """The same function serves both: a write and a read return the same record."""
    client = mcp.client
    client.headers.update(owner_token["headers"])
    job = client.post("/api/v1/jobs", json={"title": "Engineer", "posting": "Synthetic."}).json()
    over_mcp, error = mcp.call(
        "notes_create", {"job_id": job["id"], "body": "First.", "pinned": True}
    )
    over_rest = client.post(f"/api/v1/jobs/{job['id']}/notes", json={"body": "Second."}).json()
    assert error is None and set(over_mcp) == set(over_rest)
    read, _ = mcp.call("notes_get", {"note_id": over_rest["id"]})
    assert read == client.get(f"/api/v1/notes/{over_rest['id']}").json()
    listed, _ = mcp.call("jobs_list", {"q": "Engineer", "include_counts": True})
    assert listed == client.get("/api/v1/jobs?q=Engineer&include_counts=true").json()
