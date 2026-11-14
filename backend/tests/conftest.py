"""Shared fixtures of the backend tests.

A fresh database is built once per test session (once per xdist worker) at the
current schema and copied per test, so a test pays for a file copy instead of
the schema script. The fixtures build on each other:

    database_path   a private copy of the fresh database (no owner yet)
    workspace       a Workspace on database_path
    app             the product application on a copy whose owner password is PASSWORD
    client          a TestClient of app, signed in as the owner (session + CSRF header)
                    with a cookie signed once per session: every copy of the owned
                    database shares its secret, and sign-in has its own tests
    owner_token     an owner API token of app: {"id", "name", "token", "headers"}
    agent_token     an agent API token of app, same shape
    mcp             an MCP client of app that calls tools with agent_token
    collection      a workspace and its Discovery service; URL checks pass every address
    local_server    a real HTTP server on 127.0.0.1 that records (host, path) of each GET
    alternating_threads  streamed responses read each chunk on the other of two threads

Test modules keep their own data builders (`*_fixtures.py`); the setup of a
workspace, an application and its sessions lives here.
"""

import asyncio
import json
import shutil
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import starlette.responses
from fastapi.testclient import TestClient

from discovery_fixtures import patch_discovery
from openings.app import create_app
from openings.auth import COOKIE, Auth
from openings.discovery import DiscoveryService
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


@pytest.fixture(scope="session")
def owner_session(owned_database):
    """A session cookie and CSRF token valid on every copy of the owned database."""
    cookie, session = Auth(Workspace(owned_database)).login(PASSWORD)
    _checkpointed(owned_database)
    return cookie, session["csrf"]


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
def client(app, owner_session):
    """The owner's browser: a session cookie and its CSRF header on every request."""
    cookie, csrf = owner_session
    with TestClient(app, base_url=BASE_URL, cookies={COOKIE: cookie}) as client:
        client.headers["X-CSRF-Token"] = csrf
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


@pytest.fixture
def collection(workspace, monkeypatch):
    """A workspace with its Discovery service; ``public_url`` accepts every address."""
    service = DiscoveryService(workspace)
    workspace.discovery = service
    patch_discovery(monkeypatch, "public_url", lambda url: url)
    return workspace, service


@pytest.fixture
def local_server():
    """An HTTP server on 127.0.0.1: ``/start`` redirects to ``server.redirect``, a path in
    ``server.bodies`` answers its bytes, any other path ``internal``."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.headers["Host"].split(":")[0], self.path))
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", self.server.redirect)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = self.server.bodies.get(self.path, b"internal")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError, ConnectionResetError:
                pass  # the client stopped reading a body over its limit

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.seen, server.bodies, server.redirect = seen, {}, None
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def alternating_threads(monkeypatch):
    """Read each chunk of a streamed response on the other of two worker threads, so no
    SQLite object may cross threads; the list holds one entry per chunk read."""
    executors = [ThreadPoolExecutor(max_workers=1) for _ in range(2)]
    reads = []

    def next_chunk(iterator):
        try:
            return True, next(iterator)
        except StopIteration:
            return False, None

    async def alternate(content):
        iterator = iter(content)
        while True:
            executor = executors[len(reads) % 2]
            reads.append(executor)
            available, chunk = await asyncio.get_running_loop().run_in_executor(
                executor, next_chunk, iterator
            )
            if not available:
                break
            yield chunk

    monkeypatch.setattr(starlette.responses, "iterate_in_threadpool", alternate)
    yield reads
    for executor in executors:
        executor.shutdown()
