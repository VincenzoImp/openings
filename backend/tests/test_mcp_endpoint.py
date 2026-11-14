"""The advertised MCP URL accepts JSON-RPC directly with transport safeguards."""

import json

from fastapi.testclient import TestClient

from openings import __version__
from openings.app import create_app


def test_advertised_mcp_endpoint_and_trailing_slash_support_json_rpc(tmp_path):
    app = create_app(tmp_path / "mcp-endpoint.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic MCP client")["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
    }
    observed = []
    mount = next(route for route in app.routes if getattr(route, "path", None) == "/mcp")
    transport = mount.app

    async def observe_scope(scope, receive, send):
        observed.append((scope["path"], scope["raw_path"], scope["query_string"]))
        await transport(scope, receive, send)

    mount.app = observe_scope
    with TestClient(app, base_url="http://localhost:8080", follow_redirects=False) as client:
        endpoint = client.get("/api/v1/workspace", headers=headers).json()["mcp_endpoint"]
        for path in (endpoint, endpoint + "/"):
            response = client.post(
                path + "?client=synthetic%20agent",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "synthetic-client", "version": "1"},
                    },
                },
            )
            assert response.status_code == 200
            assert not response.history
            assert response.json()["result"]["serverInfo"]["name"] == "Openings"
            tools = client.post(
                path,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            assert tools.status_code == 200
            assert "workspace_info" in {tool["name"] for tool in tools.json()["result"]["tools"]}
            read = client.post(
                path,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "workspace_info", "arguments": {}},
                },
            )
            assert read.status_code == 200
            result = read.json()["result"]
            assert not result.get("isError")
            value = result.get("structuredContent") or json.loads(result["content"][0]["text"])
            assert value["name"] == "Openings"
            assert read.headers["cache-control"] == "no-store"
    assert [entry for entry in observed if entry[2]] == [
        ("/mcp/", b"/mcp/", b"client=synthetic%20agent"),
        ("/mcp/", b"/mcp/", b"client=synthetic%20agent"),
    ]


def test_both_mcp_paths_preserve_auth_origin_host_and_maintenance_checks(tmp_path, monkeypatch):
    origin = "https://jobs.example.test"
    monkeypatch.setenv("OPENINGS_PUBLIC_URL", origin)
    app = create_app(tmp_path / "mcp-boundary.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic MCP client")["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
        "Origin": origin,
    }
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    with TestClient(app, base_url=origin, follow_redirects=False) as client:
        client.post("/api/v1/auth/login", json={"password": "synthetic-password"})
        for endpoint in ("/mcp", "/mcp/"):
            assert client.post(endpoint, json=message).status_code == 401
            assert (
                client.post(
                    endpoint, json=message, headers={"Authorization": "Bearer invalid"}
                ).status_code
                == 401
            )
            assert client.post(endpoint, json=message, headers=headers).status_code == 200
            assert (
                client.post(
                    endpoint, json=message, headers={**headers, "Origin": "https://other.example"}
                ).status_code
                == 403
            )
            assert (
                client.post(
                    endpoint, json=message, headers={**headers, "Host": "other.example"}
                ).status_code
                == 421
            )
            assert (
                client.post(
                    endpoint,
                    json=message,
                    headers={**headers, "Content-Length": str(40 * 1024**2 + 1)},
                ).status_code
                == 413
            )
            app.state.workspace.maintenance = True
            assert client.post(endpoint, json=message, headers=headers).status_code == 503
            app.state.workspace.maintenance = False


CAPABILITIES = {
    "prompts": {"listChanged": False},
    "resources": {"subscribe": False, "listChanged": False},
    "tools": {"listChanged": False},
}


def test_handshake_and_per_request_protocols_report_the_same_static_server(tmp_path):
    app = create_app(tmp_path / "mcp-protocols.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic MCP client")["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
    }
    identity = {"name": "Openings", "version": __version__}
    client_info = {"name": "synthetic-client", "version": "1"}

    with TestClient(app, base_url="http://localhost:8080") as client:
        for requested, negotiated in (
            ("2024-11-05", "2024-11-05"),
            ("2025-03-26", "2025-03-26"),
            ("2025-06-18", "2025-06-18"),
            ("2025-11-25", "2025-11-25"),
            ("1999-01-01", "2025-11-25"),
        ):
            result = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": requested,
                        "capabilities": {},
                        "clientInfo": client_info,
                    },
                },
            ).json()["result"]
            assert result == {
                "protocolVersion": negotiated,
                "capabilities": CAPABILITIES,
                "serverInfo": identity,
            }

        def per_request(method, params=None):
            meta = {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": client_info,
            }
            return client.post(
                "/mcp",
                headers={**headers, "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": {**(params or {}), "_meta": meta},
                },
            )

        discovered = per_request("server/discover").json()["result"]
        assert discovered["capabilities"] == CAPABILITIES
        assert discovered["_meta"]["io.modelcontextprotocol/serverInfo"] == identity
        tools = per_request("tools/list").json()["result"]["tools"]
        assert "workspace_info" in {tool["name"] for tool in tools}
        # No tool, prompt or resource changes at runtime, so no stream is ever held open.
        listen = per_request("subscriptions/listen", {"notifications": {"toolsListChanged": True}})
        assert listen.status_code == 404
        assert listen.headers["content-type"] == "application/json"
        assert listen.json()["error"]["code"] == -32601


def test_context_and_staleness_tools_answer_with_their_replacement(mcp, agent_token):
    # Frozen contexts and staleness are gone (0.24); REST answers 410 Gone.
    for name, replacement in (
        ("contexts_create", "applications_get"),
        ("contexts_get", "preferences_get"),
        ("contexts_list", "documents_create"),
        ("staleness_get", "documents_list"),
        ("staleness_list", "documents_list"),
    ):
        _, removed = mcp.call(name, {})
        assert removed["code"] == "tool_removed" and replacement in removed["message"]
        assert removed["details"] == {"tool": name}
    for path in ("/contexts", "/contexts/any", "/staleness", "/applications/any/staleness"):
        response = mcp.client.get("/api/v1" + path, headers=agent_token["headers"])
        assert response.status_code == 410
