"""The fixed cost of the agent interface: tools/list, descriptions, instructions, the start read.

tools/list is what every agent session pays before its first call. It fails above
40,000 characters and warns above 36,000; each tool description is at most 250
characters; the server instructions at most 1,500; workspace_context on a realistic
synthetic workspace at most 16,000.
"""

import json
import re
import warnings

from context_fixtures import realistic
from openings.mcp_server import INSTRUCTIONS

TOOLS_LIST_LIMIT = 40_000
TOOLS_LIST_TARGET = 36_000
DESCRIPTION_LIMIT = 250
INSTRUCTIONS_LIMIT = 1_500
CONTEXT_LIMIT = 16_000


def tools_list(mcp):
    response = mcp.client.post(
        "/mcp/",
        headers={"Accept": "application/json, text/event-stream", **mcp.token["headers"]},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 200
    return response


def test_tools_list_and_instructions_stay_within_their_budget(mcp, owner_token):
    response = tools_list(mcp)
    size = len(response.text)
    tools = response.json()["result"]["tools"]
    assert 44 <= len(tools) <= 45, len(tools)
    assert size <= TOOLS_LIST_LIMIT, f"tools/list is {size} characters"
    if size > TOOLS_LIST_TARGET:
        warnings.warn(f"tools/list is {size} characters (target {TOOLS_LIST_TARGET})", stacklevel=1)
    for tool in tools:
        assert len(tool["description"]) <= DESCRIPTION_LIMIT, tool["name"]
    assert len(INSTRUCTIONS) <= INSTRUCTIONS_LIMIT
    assert "workspace_context" in INSTRUCTIONS and "skills_get" in INSTRUCTIONS
    assert "Never submit an application" in INSTRUCTIONS
    # Every default a description states is the schema's.
    stated = 0
    for tool in tools:
        properties = tool["inputSchema"]["properties"]
        for name, value in re.findall(r"\b(\w+) defaults? (?:to )?([\w.:-]+)", tool["description"]):
            if name in properties:
                stated += 1
                assert str(properties[name].get("default")) == value, (tool["name"], name)
        pending = list(properties.items())
        while pending:
            name, schema = pending.pop()
            pending += list(schema.get("properties", {}).items())
            pending += list(schema.get("items", {}).get("properties", {}).items())
            for value in _defaults(schema.get("description", "")):
                stated += 1
                default = schema.get("default", schema.get("items", {}).get("default"))
                assert default is not None and value in json.dumps(default), (tool["name"], name)
    assert stated
    # An owner token sees the same tools: owner-only operations are never tools.
    mcp.token = owner_token
    assert tools_list(mcp).json()["result"]["tools"] == tools


def _defaults(text):
    """Defaults a description states: "x defaults to y", "default y", "y (default)"."""
    found = re.findall(r"\bdefaults? (?:to )?([\w.:-]+)", text)
    found += re.findall(r"([\w.:-]+) \(default\)", text)
    return found


def test_workspace_context_of_a_realistic_workspace_fits(app, mcp):
    realistic(app)
    response = mcp.client.post(
        "/mcp/",
        headers={"Accept": "application/json, text/event-stream", **mcp.token["headers"]},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "workspace_context", "arguments": {}},
        },
    )
    text = response.json()["result"]["content"][0]["text"]
    assert len(json.loads(text)["career"]) == 18
    assert len(text) <= CONTEXT_LIMIT, len(text)
