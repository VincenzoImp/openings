"""Shared fixtures of the backend tests.

A fresh database is built once per test session (once per xdist worker) at the
current schema and copied per test, so a test pays for a file copy instead of
the schema script. The fixtures build on each other:

    database_path   a private copy of the fresh database (no owner yet)
    workspace       a Workspace on database_path
    app             the product application on a copy whose owner password is PASSWORD
    client          a TestClient of app, signed in as the owner (session + CSRF header)
    owner_token     an owner API token of app: {"id", "name", "token", "headers"}
    agent_token     an agent API token of app, same shape
    mcp             an MCP client of app that calls tools with agent_token

Test modules keep their own data builders (`*_fixtures.py`); the setup of a
workspace, an application and its sessions lives here.
"""

import json
import shutil
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.auth import Auth
from openings.workspace import Workspace

PASSWORD = "synthetic-password"
BASE_URL = "http://localhost:8080"
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _checkpointed(path):
    """Fold the WAL into the file, so a plain copy of it is complete."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return path


@pytest.fixture(scope="session")
def fresh_database(tmp_path_factory):
    """One database at the current schema, built by the product code, never opened again."""
    path = tmp_path_factory.mktemp("template") / "fresh.sqlite"
    Workspace(path)
    return _checkpointed(path)


@pytest.fixture(scope="session")
def owned_database(tmp_path_factory, fresh_database):
    """The fresh database with the owner's password set (PASSWORD)."""
    path = tmp_path_factory.mktemp("template") / "owned.sqlite"
    shutil.copyfile(fresh_database, path)
    Auth(Workspace(path)).setup(PASSWORD)
    return _checkpointed(path)


@pytest.fixture
def database_path(tmp_path, fresh_database):
    path = tmp_path / "workspace.sqlite"
    shutil.copyfile(fresh_database, path)
    return path


@pytest.fixture
def workspace(database_path):
    return Workspace(database_path)


@pytest.fixture
def app(tmp_path, owned_database):
    path = tmp_path / "app.sqlite"
    shutil.copyfile(owned_database, path)
    return create_app(path, start_worker=False)


@pytest.fixture
def client(app):
    """The owner's browser: a session cookie and its CSRF header on every request."""
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.post("/api/v1/auth/login", json={"password": PASSWORD})
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = client.get("/api/v1/auth/session").json()["csrf_token"]
        yield client


def _token(app, name, kind):
    token = app.state.auth.create_token(name, kind)
    return {**token, "headers": {"Authorization": "Bearer " + token["token"]}}


@pytest.fixture
def owner_token(app):
    return _token(app, "Synthetic owner scripts", "owner")


@pytest.fixture
def agent_token(app):
    return _token(app, "Synthetic agent", "agent")


class McpClient:
    """JSON-RPC over the HTTP MCP endpoint with one bearer token."""

    def __init__(self, client, token):
        self.client, self.token = client, token

    def rpc(self, method, params=None):
        response = self.client.post(
            "/mcp/",
            headers={**MCP_HEADERS, **self.token["headers"]},
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
        assert response.status_code == 200, response.text
        return response.json()["result"]

    def call(self, name, arguments=None):
        """Call a tool; return (value, None) or (None, the structured error)."""
        result = self.rpc("tools/call", {"name": name, "arguments": arguments or {}})
        text = result["content"][0]["text"] if result.get("content") else "null"
        if result.get("isError"):
            return None, json.loads(text)["error"]
        return result.get("structuredContent") or json.loads(text), None


@pytest.fixture
def mcp(app, agent_token):
    # A client without the owner's cookie: the agent token is the only credential.
    with TestClient(app, base_url=BASE_URL) as client:
        yield McpClient(client, agent_token)
