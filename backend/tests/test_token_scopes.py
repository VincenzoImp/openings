"""Scoped API tokens: an agent token has no owner authority; owner tokens keep full access."""

import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from openings.actors import OWNER, acting_as, current_actor, token_actor
from openings.app import create_app
from openings.errors import DomainError

PASSWORD = "synthetic-password"
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
FORBIDDEN = {"token_kind": "agent", "required": "owner"}


# Unlike the shared `client`, no owner session: every request names its token.
@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://localhost:8080") as client:
        yield client


def bearer(token):
    return {"Authorization": "Bearer " + token["token"]}


def tool(client, token, name, arguments=None):
    """Call an MCP tool over the HTTP endpoint; returns (value, error)."""
    response = client.post(
        "/mcp",
        headers={**MCP_HEADERS, **bearer(token)},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    if result.get("isError"):
        return None, json.loads(result["content"][0]["text"])["error"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"]), None


def question(app, agent):
    with acting_as(token_actor(agent["id"], agent["name"], "agent")):
        return app.state.activity.ask_question({"question": "Which notice period applies?"})


def refused_over_rest(response):
    assert response.status_code == 403, response.text
    error = response.json()["error"]
    assert (error["code"], error["details"]) == ("forbidden", FORBIDDEN)
    assert "agent token cannot" in error["message"]
    return error


def refused_over_mcp(result):
    value, error = result
    assert value is None
    assert (error["code"], error["status"], error["details"]) == ("forbidden", 403, FORBIDDEN)
    return error


def test_an_agent_token_is_refused_owner_operations_on_rest_and_mcp(app, client):
    auth = app.state.auth
    agent = auth.create_token("Synthetic agent", "agent")
    other = auth.create_token("Second synthetic agent", "agent")
    asked = question(app, agent)
    headers = bearer(agent)
    answer = {"expected_version": asked["version"], "answer": "Three months."}
    pairs = [
        (
            client.post(
                "/api/v1/auth/password", json={"password": "changed-password"}, headers=headers
            ),
            tool(
                client, agent, "owner_password_update", {"value": {"password": "changed-password"}}
            ),
        ),
        (client.get("/api/v1/tokens", headers=headers), tool(client, agent, "tokens_list")),
        (
            client.post(
                "/api/v1/tokens", json={"name": "Escalation", "kind": "owner"}, headers=headers
            ),
            tool(
                client, agent, "tokens_create", {"value": {"name": "Escalation", "kind": "owner"}}
            ),
        ),
        (
            client.delete(f"/api/v1/tokens/{other['id']}", headers=headers),
            tool(client, agent, "tokens_revoke", {"token_id": other["id"]}),
        ),
        (
            client.post(
                "/api/v1/backup/restore",
                content=b"SQLite format 3\x00",
                headers={**headers, "Content-Type": "application/vnd.sqlite3"},
            ),
            tool(client, agent, "workspace_restore"),
        ),
        (
            client.post(f"/api/v1/questions/{asked['id']}/answer", json=answer, headers=headers),
            tool(client, agent, "questions_answer", {"question_id": asked["id"], "value": answer}),
        ),
    ]
    for over_rest, over_mcp in pairs:
        rest_error, mcp_error = refused_over_rest(over_rest), refused_over_mcp(over_mcp)
        assert rest_error["message"] == mcp_error["message"]
    # Nothing changed: the password, both tokens and the open question are as before.
    assert client.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 200
    assert {item["name"] for item in auth.list_tokens()["items"]} == {
        "Synthetic agent",
        "Second synthetic agent",
    }
    assert app.state.activity.get_question(asked["id"])["state"] == "open"
    assert not app.state.activity.list_events({"kind": "owner_password_changed"})["total"]


def test_an_agent_token_keeps_the_workflow_operations(app, client):
    agent = app.state.auth.create_token("Synthetic agent", "agent")
    headers = bearer(agent)
    info, error = tool(client, agent, "workspace_info")
    assert error is None
    assert info["actor"] == {
        "kind": "token",
        "id": agent["id"],
        "name": "Synthetic agent",
        "token_kind": "agent",
        "label": "Synthetic agent",
    }
    assert client.get("/api/v1/workspace", headers=headers).json()["actor"] == info["actor"]
    job = client.post(
        "/api/v1/jobs",
        json={"title": "Synthetic engineer", "company": "Example", "posting": "Build APIs."},
        headers=headers,
    ).json()
    run, error = tool(client, agent, "runs_start", {"value": {"workflow": "review-inbox"}})
    assert error is None and run["actor"]["token_kind"] == "agent"
    asked, error = tool(
        client,
        agent,
        "questions_ask",
        {
            "value": {
                "question": "Is Bern acceptable?",
                "subject_type": "job",
                "subject_id": job["id"],
            }
        },
    )
    assert error is None and asked["asked_by"]["token_kind"] == "agent"
    note = client.post(
        f"/api/v1/jobs/{job['id']}/notes", json={"body": "Synthetic note"}, headers=headers
    ).json()
    assert note["author"]["token_kind"] == "agent"
    # An agent may withdraw its own question; only the answer belongs to the owner.
    withdrawn, error = tool(
        client,
        agent,
        "questions_withdraw",
        {"question_id": asked["id"], "value": {"expected_version": asked["version"]}},
    )
    assert error is None and withdrawn["withdrawn_by"]["token_kind"] == "agent"
    history = client.get(f"/api/v1/events?run_id={run['id']}", headers=headers).json()["items"]
    assert {item["actor"]["token_kind"] for item in history} == {"agent"}
    # Export and permanent deletion stay available: they are workspace data operations.
    assert client.get("/api/v1/export", headers=headers).status_code == 200
    export, error = tool(client, agent, "workspace_export")
    assert error is None and export["headers"]["X-Operational-Token"]
    current = client.get(f"/api/v1/jobs/{job['id']}", headers=headers).json()
    forgotten, error = tool(
        client, agent, "jobs_delete", {"job_id": job["id"], "expected_version": current["version"]}
    )
    assert error is None and forgotten["deleted"] is True
    # The recorded kind outlives the token.
    app.state.auth.revoke_token(agent["id"])
    assert app.state.activity.get_run(run["id"])["actor"]["token_kind"] == "agent"


def test_an_agent_backup_carries_no_installation_credentials(app, client, tmp_path):
    workspace, auth = app.state.workspace, app.state.auth
    agent = auth.create_token("Synthetic agent", "agent")
    owner = auth.create_token("Synthetic owner token", "owner")
    job = workspace.ingest_job({"title": "Kept job", "company": "Example", "posting": "Build."})
    secrets = workspace.get_settings("auth")["data"]
    needles = [
        secrets["password_hash"].encode(),
        secrets["secret"].encode(),
        hashlib.sha256(agent["token"].encode()).hexdigest().encode(),
        hashlib.sha256(owner["token"].encode()).hexdigest().encode(),
    ]
    grant, error = tool(client, agent, "workspace_backup")
    assert error is None
    for response in (
        client.get("/api/v1/backup", headers=bearer(agent)),
        # The scoped download remembers that an agent token requested it.
        client.get(grant["url"], headers=grant["headers"]),
    ):
        assert response.status_code == 200
        assert not any(needle in response.content for needle in needles)
        copy = tmp_path / "agent-backup.sqlite"
        copy.write_bytes(response.content)
        with sqlite3.connect(copy) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("SELECT count(*) FROM api_tokens").fetchone()[0] == 0
            assert not conn.execute("SELECT 1 FROM settings WHERE key='auth'").fetchall()
            assert conn.execute("SELECT title FROM jobs").fetchall() == [("Kept job",)]
    # An owner backup stays a complete copy of the installation.
    complete = client.get("/api/v1/backup", headers=bearer(owner))
    assert all(needle in complete.content for needle in needles)
    # The agent's backup restores completely; the installation keeps its own access.
    workspace.forget_job(job["id"], workspace.get_job(job["id"])["version"])
    restored = client.post(
        "/api/v1/backup/restore",
        content=copy.read_bytes(),
        headers={**bearer(owner), "Content-Type": "application/vnd.sqlite3"},
    )
    assert restored.status_code == 200, restored.text
    assert workspace.get_job(job["id"])["title"] == "Kept job"
    assert client.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 200
    kinds = {item["name"]: item["kind"] for item in auth.list_tokens()["items"]}
    assert kinds == {"Synthetic agent": "agent", "Synthetic owner token": "owner"}
    assert client.get("/api/v1/jobs", headers=bearer(agent)).status_code == 200


def test_an_owner_token_keeps_full_access_and_chooses_the_kind(app, client):
    owner = app.state.auth.create_token("Synthetic owner token", "owner")
    assert owner["kind"] == "owner"
    headers = bearer(owner)
    # The kind defaults to the scoped agent on both interfaces, as in the dashboard.
    default = client.post("/api/v1/tokens", json={"name": "Agent on laptop"}, headers=headers)
    script, error = tool(
        client, owner, "tokens_create", {"value": {"name": "Script", "kind": "owner"}}
    )
    default = default.json()
    assert error is None and (default["kind"], script["kind"]) == ("agent", "owner")
    assert default["token"].startswith("op_")
    listed, error = tool(client, owner, "tokens_list")
    assert error is None
    assert client.get("/api/v1/tokens", headers=headers).json() == listed
    assert {item["name"]: item["kind"] for item in listed["items"]} == {
        "Synthetic owner token": "owner",
        "Script": "owner",
        "Agent on laptop": "agent",
    }
    assert "token_hash" not in listed["items"][0] and "token" not in listed["items"][0]
    created = app.state.activity.list_events({"kind": "token_created"})["items"][0]
    assert created["payload"] == {"name": "Script", "kind": "owner"}
    assert created["actor"]["token_kind"] == "owner"
    for body in ({"name": "Invalid", "kind": "admin"}, {"name": "Invalid", "kind": None}):
        invalid = client.post("/api/v1/tokens", json=body, headers=headers)
        _, error = tool(client, owner, "tokens_create", {"value": body})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == error["code"] == "validation"
    # The owner can run everything from an external session: answer, revoke, change the password.
    asked = question(app, default)
    answered, error = tool(
        client,
        owner,
        "questions_answer",
        {"question_id": asked["id"], "value": {"expected_version": 1, "answer": "Three months."}},
    )
    assert error is None and answered["answered_by"]["token_kind"] == "owner"
    assert client.delete(f"/api/v1/tokens/{default['id']}", headers=headers).status_code == 200
    changed, error = tool(
        client, owner, "owner_password_update", {"value": {"password": "changed-password"}}
    )
    assert error is None and changed["api_tokens_preserved"] is True
    assert (
        client.post("/api/v1/auth/login", json={"password": "changed-password"}).status_code == 200
    )
    backup = client.get("/api/v1/backup", headers=headers)
    restored = client.post(
        "/api/v1/backup/restore",
        content=backup.content,
        headers={**headers, "Content-Type": "application/vnd.sqlite3"},
    )
    assert restored.status_code == 200, restored.text
    upload, error = tool(client, owner, "workspace_restore")
    assert error is None and upload["url"] == "/api/v1/backup/restore"


def test_the_owner_session_and_the_system_are_never_refused(app):
    auth = app.state.auth
    agent = auth.create_token("Synthetic agent", "agent")
    with acting_as(OWNER):
        assert auth.list_tokens()["total"] == 1
        assert auth.create_token("Second", "agent")["kind"] == "agent"
    assert current_actor().kind == "system" and auth.list_tokens()["total"] == 2
    with acting_as(token_actor(agent["id"], agent["name"], "agent")):
        for call in (
            auth.list_tokens,
            lambda: auth.create_token("Third"),
            lambda: auth.revoke_token(agent["id"]),
            lambda: auth.change_password("another-password"),
        ):
            with pytest.raises(DomainError) as refused:
                call()
            assert (refused.value.status, refused.value.code) == (403, "forbidden")
    with pytest.raises(DomainError) as invalid:
        auth.create_token("Invalid", "admin")
    assert invalid.value.code == "token_kind"
