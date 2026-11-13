"""Local notes for a skill: versioned, attributed, appended when the skill is served.

The shipped skill text never changes; REST, MCP tools and MCP prompts serve the same
text with the same "Local notes for this workspace" section.
"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openings.actors import acting_as, token_actor
from openings.app import create_app
from openings.db import SCHEMA_VERSION, Database, upgrade
from openings.operations import restore_database
from openings.skill_notes import HEADING, MAX_LENGTH
from openings.workspace import Workspace
from schema_fixtures import table_names
from signal_fixtures import make_schema_eleven

ROOT = Path(__file__).resolve().parents[2] / "skills"
SKILL = "review-inbox"
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
NOTE = "Leave every job at Northstar Labs for the owner.\nQuote on-call sentences in reasons."


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENINGS_SKILLS", str(ROOT))
    app = create_app(tmp_path / "notes.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    return app


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://localhost:8080") as client:
        yield client


@pytest.fixture
def owner(app):
    return {"Authorization": "Bearer " + app.state.auth.create_token("Owner scripts")["token"]}


@pytest.fixture
def agent(app):
    token = app.state.auth.create_token("Synthetic agent", "agent")
    return {"Authorization": "Bearer " + token["token"], "id": token["id"]}


def rpc(client, headers, method, params):
    response = client.post(
        "/mcp/",
        headers={**MCP_HEADERS, "Authorization": headers["Authorization"]},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def tool(client, headers, name, arguments):
    result = rpc(client, headers, "tools/call", {"name": name, "arguments": arguments})
    if result.get("isError"):
        return None, json.loads(result["content"][0]["text"])["error"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"]), None


def auth(headers):
    return {"Authorization": headers["Authorization"]}


def save(client, headers, text, version, name=SKILL):
    return client.put(
        f"/api/v1/skills/{name}/notes",
        headers=auth(headers),
        json={"expected_version": version, "text": text},
    )


def shipped(name=SKILL, path="SKILL.md"):
    return (ROOT / name / path).read_text(encoding="utf-8")


def test_a_note_is_served_identically_over_rest_and_mcp(client, owner, agent):
    digest = hashlib.sha256((ROOT / SKILL / "SKILL.md").read_bytes()).hexdigest()
    saved = save(client, owner, NOTE, 0)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1 and saved.json()["text"] == NOTE

    rest = client.get(f"/api/v1/skills/{SKILL}", headers=auth(agent)).json()
    via_file = client.get(f"/api/v1/skills/{SKILL}/files/SKILL.md", headers=auth(agent)).json()
    mcp, error = tool(client, agent, "skills_get", {"name": SKILL})
    assert error is None
    assert rest["content"] == via_file["content"] == mcp["content"]
    assert rest["local_notes"] == mcp["local_notes"]
    assert rest["local_notes"]["version"] == 1 and "text" not in rest["local_notes"]

    content = rest["content"]
    text = shipped()
    assert content.startswith(text.rstrip())
    section = content[len(text.rstrip()) :]
    assert section.startswith(f"\n\n---\n\n{HEADING}\n\nWritten in this workspace (version 1, ")
    assert "by Owner scripts)" in section and section.endswith(NOTE + "\n")

    prompt = rpc(client, agent, "prompts/get", {"name": SKILL})
    assert prompt["messages"][0]["content"]["text"].endswith(content)

    # The shipped text never changes and stays readable on its own.
    assert hashlib.sha256((ROOT / SKILL / "SKILL.md").read_bytes()).hexdigest() == digest
    plain = client.get(f"/api/v1/skills/{SKILL}?local_notes=false", headers=auth(agent)).json()
    assert plain["content"] == text
    plain_mcp, _ = tool(
        client, agent, "skills_get", {"name": SKILL, "value": {"local_notes": False}}
    )
    assert plain_mcp["content"] == text

    # Reference files are served as shipped, without notes.
    path = "references/run-report.md"
    reference = client.get(
        f"/api/v1/skills/openings-workspace/files/{path}", headers=auth(agent)
    ).json()
    assert reference["content"] == shipped("openings-workspace", path)
    assert reference["local_notes"] is None
    # Another skill has no notes.
    other = client.get("/api/v1/skills/setup-openings", headers=auth(agent)).json()
    assert other["content"] == shipped("setup-openings") and other["local_notes"] is None


def test_versions_conflicts_and_unchanged_text(client, owner):
    assert save(client, owner, "First.", 0).json()["version"] == 1
    stale = save(client, owner, "Second.", 0)
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_version"] == 1
    assert save(client, owner, "Second.\r\n\n  ", 1).json()["version"] == 2
    again = save(client, owner, "Second.", 2).json()
    assert again["version"] == 2 and again["versions_total"] == 2
    notes = client.get(f"/api/v1/skills/{SKILL}/notes", headers=auth(owner)).json()
    assert notes["text"] == "Second." and notes["max_length"] == MAX_LENGTH
    assert [item["version"] for item in notes["versions"]] == [2, 1]
    assert [item["text"] for item in notes["versions"]] == ["Second.", "First."]
    assert notes["updated_by"]["name"] == "Owner scripts"

    # Empty text clears the notes as a new version; the skill is then served as shipped.
    cleared = save(client, owner, "   \n", 2).json()
    assert cleared["version"] == 3 and cleared["text"] == ""
    served = client.get(f"/api/v1/skills/{SKILL}", headers=auth(owner)).json()
    assert served["content"] == shipped() and HEADING not in served["content"]
    listed = {
        item["name"]: item
        for item in client.get("/api/v1/skills", headers=auth(owner)).json()["items"]
    }
    assert listed[SKILL]["local_notes"]["version"] == 3
    assert listed[SKILL]["local_notes"]["length"] == 0


def test_limits_and_unknown_skills(client, owner):
    assert save(client, owner, "x" * (MAX_LENGTH + 1), 0).status_code == 422
    assert save(client, owner, "x" * MAX_LENGTH, 0).status_code == 200
    assert save(client, owner, "Note.", 0, name="no-such-skill").status_code == 404
    assert client.get("/api/v1/skills/no-such-skill/notes", headers=auth(owner)).status_code == 404
    _, error = tool(
        client,
        owner,
        "skill_notes_update",
        {"name": "..", "value": {"expected_version": 0, "text": "x"}},
    )
    assert error["code"] == "not_found"


def test_an_agent_token_may_write_notes_and_is_attributed(app, client, agent):
    value, error = tool(
        client,
        agent,
        "skill_notes_update",
        {"name": SKILL, "value": {"expected_version": 0, "text": "Read the policy first."}},
    )
    assert error is None and value["version"] == 1
    assert value["updated_by"]["kind"] == "token"
    assert value["updated_by"]["token_kind"] == "agent"
    read, _ = tool(client, agent, "skill_notes_get", {"name": SKILL})
    rest = client.get(f"/api/v1/skills/{SKILL}/notes", headers=auth(agent)).json()
    assert read == rest
    served = client.get(f"/api/v1/skills/{SKILL}", headers=auth(agent)).json()["content"]
    assert "by Synthetic agent)" in served

    events = app.state.workspace.db.all("SELECT * FROM events WHERE kind='skill_notes_updated'")
    assert len(events) == 1
    event = events[0]
    assert (event["subject_type"], event["subject_id"]) == ("skill", SKILL)
    assert json.loads(event["payload"]) == {"skill": SKILL, "version": 1}
    assert (event["actor_kind"], event["actor_token_kind"]) == ("token", "agent")
    listed = client.get("/api/v1/events?subject_type=skill", headers=auth(agent)).json()["items"]
    assert listed[0]["subject"]["label"] == SKILL


def test_the_list_describes_reference_files_and_notes(client, owner):
    save(client, owner, NOTE, 0)
    items = {
        item["name"]: item
        for item in client.get("/api/v1/skills", headers=auth(owner)).json()["items"]
    }
    workspace = items["openings-workspace"]
    details = {item["path"]: item for item in workspace["file_details"]}
    assert set(details) == set(workspace["files"])
    report = details["references/run-report.md"]
    assert report["bytes"] == (ROOT / "openings-workspace/references/run-report.md").stat().st_size
    assert report["title"].startswith("Run report")
    assert details["SKILL.md"]["title"]
    assert items[SKILL]["local_notes"]["version"] == 1
    assert items[SKILL]["local_notes"]["length"] == len(NOTE)
    assert workspace["local_notes"] is None


def schema_eleven(path):
    Database(path)
    make_schema_eleven(path)


def test_a_schema_eleven_workspace_gains_the_table(tmp_path):
    path = tmp_path / "schema11.sqlite"
    schema_eleven(path)
    with closing(sqlite3.connect(path)) as conn:
        assert "skill_notes" not in table_names(conn)
    Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with closing(sqlite3.connect(path)) as conn, closing(sqlite3.connect(fresh.path)) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 14
        assert table_names(conn) == table_names(reference)
        sql = "SELECT sql FROM sqlite_master WHERE name='skill_notes'"
        assert conn.execute(sql).fetchone() == reference.execute(sql).fetchone()

    # The upgrade step itself creates the table, before schema.sql is applied.
    stepped = tmp_path / "stepped.sqlite"
    schema_eleven(stepped)
    with closing(sqlite3.connect(stepped)) as conn:
        upgrade(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert "skill_notes" in table_names(conn)

    source = tmp_path / "backup11.sqlite"
    schema_eleven(source)
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, source)
    assert target.db.one("PRAGMA user_version")["user_version"] == SCHEMA_VERSION
    assert target.db.all("SELECT * FROM skill_notes") == []


def test_the_run_list_carries_the_method_section(app):
    token = app.state.auth.create_token("Synthetic agent", "agent")
    with acting_as(token_actor(token["id"], token["name"], "agent")):
        run = app.state.activity.start_run({"workflow": SKILL})
        app.state.activity.finish_run(
            run["id"],
            {
                "expected_version": run["version"],
                "summary": "Reviewed the jobs.",
                "method": "The workflow lacks a step for agency postings.",
            },
        )
    other = app.state.auth.create_token("Second agent", "agent")
    with acting_as(token_actor(other["id"], other["name"], "agent")):
        app.state.activity.start_run({"workflow": "manage-sources"})
    items = {item["workflow"]: item for item in app.state.activity.list_runs()["items"]}
    assert items[SKILL]["method"] == "The workflow lacks a step for agency postings."
    assert items["manage-sources"]["method"] == ""
