"""One-way parity, computed from the declarations: every REST route belongs to one
operation, and every operation that is not owner-only is also an MCP tool."""

import re
from collections import Counter

import pytest

from openings.app import create_app
from openings.interfaces import catalog


def key(method, path):
    return method.upper(), re.sub(r"\{[^}]+\}", "{}", path.replace(":path", "")).rstrip("/")


@pytest.mark.asyncio
async def test_routes_and_tools_follow_the_declared_operations(tmp_path):
    app = create_app(tmp_path / "parity.sqlite", start_worker=False)
    operations, exemptions, _ = catalog()
    declared = Counter(
        key(route.method, ("" if route.absolute else "/api/v1") + route.path)
        for item in (*operations, *exemptions)
        for route in item.rest
    )
    served = {key(m, p) for p, methods in app.openapi()["paths"].items() for m in methods}
    api = {route for route in served if route[1].startswith("/api/v1")}
    assert not api - set(declared), "Routes without an operation or transport reason"
    assert {r for r, n in declared.items() if n > 1} == set(), "Routes declared twice"
    assert {r for r in declared if r[1].startswith("/api/v1")} <= served

    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    names = Counter(op.canonical_name for op in operations if op.tool)
    assert all(count == 1 for count in names.values())
    assert tools == set(names), "Every MCP tool is one operation and every tool is served"
    for operation in operations:
        assert operation.access in (None, "owner"), operation.id
        # An operation without a tool is owner-only REST (backups, for example).
        assert operation.tool or operation.access == "owner", f"{operation.id} lacks a tool"
        assert operation.tool or operation.canonical_name not in tools, operation.id
    for exemption in exemptions:
        reason = exemption.reason.strip()
        assert reason and "\n" not in reason, exemption.id
