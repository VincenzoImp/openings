"""The advertised MCP URL accepts JSON-RPC directly with transport safeguards."""

import json

from fastapi.testclient import TestClient

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
