"""One-way parity from the declarations: every API route is one operation or a listed
transport route; every operation is an MCP tool, owner-only, or REST-only naming the MCP
tool that does its work."""

import re

from openings.interfaces import OPERATIONS, TRANSPORT_ONLY
from openings.interfaces.operation import without_empty


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
    assert tools == {op.name for op in OPERATIONS if op.on_mcp}
    for op in OPERATIONS:
        if op.covered_by:
            # A REST-only route's work is an MCP tool's; owner-only work is never one.
            assert op.access != "owner" and set(op.covered_by) <= tools, op.name
    assert len({op.name for op in OPERATIONS}) == len(OPERATIONS)
    assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", op.name) for op in OPERATIONS)


def test_a_read_and_a_write_answer_alike_over_rest_and_mcp(owner_token, mcp):
    """The same services serve both; MCP leaves out empty fields."""
    client = mcp.client
    client.headers.update(owner_token["headers"])
    job = client.post("/api/v1/jobs", json={"title": "Engineer", "posting": "Synthetic."}).json()
    over_mcp, error = mcp.call(
        "notes_create", {"job_id": job["id"], "body": "First.", "pinned": True}
    )
    over_rest = client.post(f"/api/v1/jobs/{job['id']}/notes", json={"body": "Second."}).json()
    assert error is None and set(over_mcp) - {"pinned_at"} == set(without_empty(over_rest))
    read, _ = mcp.call("jobs_get", {"ids": [job["id"]]})
    notes = client.get("/api/v1/jobs/batch", params={"ids": job["id"]}).json()["items"][0]["notes"]
    assert read["items"][0]["notes"] == without_empty(notes)
    listed, _ = mcp.call("jobs_list", {"q": "Engineer", "include_counts": True})
    rest = client.get("/api/v1/jobs?q=Engineer&include_counts=true").json()
    assert listed == without_empty(rest)
