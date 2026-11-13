"""One timeline per job and per application: scope, filters, pins, authors and REST/MCP parity."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from openings.activity import ActivityService
from openings.actors import OWNER, SYSTEM, acting_as, token_actor
from openings.app import create_app
from openings.career import CareerService, TemplateCreate
from openings.documents import ContextCreate, DocumentService
from openings.errors import DomainError
from openings.workspace import Workspace
from timeline_fixtures import guided_application

AGENT = token_actor("agent-token", "Synthetic agent", "agent")
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def job(workspace, title="Synthetic engineer"):
    return workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})


def seeded(workspace):
    """A job with two applications (one closed), job and application notes and a response."""
    first_job = job(workspace)
    with acting_as(OWNER):
        older = workspace.create_application({"job_id": first_job["id"]})
        older = workspace.update_application(
            older["id"],
            {"expected_version": older["version"], "status": "closed", "outcome": "not_pursued"},
        )
        current = guided_application(workspace, first_job["id"], "Lead with the platform work.")
        on_job = workspace.add_note(first_job["id"], {"body": "Recruiter is Synthetic Person."})
        on_older = workspace.add_note(
            first_job["id"], {"body": "Not this time.", "application_id": older["id"]}
        )
    with acting_as(AGENT):
        ActivityService(workspace).start_run({"workflow": "track-applications"})
        on_current = workspace.add_note(
            first_job["id"], {"body": "Agent observation.", "application_id": current["id"]}
        )
        applied = workspace.update_application(
            current["id"], {"expected_version": current["version"], "status": "interview"}
        )
    return {
        "job": first_job,
        "older": older,
        "current": applied,
        "on_job": on_job,
        "on_older": on_older,
        "on_current": on_current,
    }


def test_an_application_timeline_holds_its_entries_and_its_jobs_only(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    ids = seeded(workspace)
    current = ids["current"]
    result = workspace.timeline(application_id=current["id"])
    assert result["scope"] == {
        "type": "application",
        "id": current["id"],
        "job_id": ids["job"]["id"],
    }
    items = result["items"]
    assert result["total"] == len(items)
    # The pinned note first, then newest first.
    assert items[0]["type"] == "note" and items[0]["note"]["pinned"]
    assert items[0]["note"]["body"] == "Lead with the platform work."
    rest = [item["created_at"] for item in items[1:]]
    assert rest == sorted(rest, reverse=True)
    applications = {item["application_id"] for item in items}
    assert applications == {current["id"], None}
    assert ids["on_older"]["id"] not in {item["id"] for item in items}
    by_id = {item["id"]: item for item in items}
    assert by_id[ids["on_job"]["id"]]["scope"] == {"type": "job", "id": ids["job"]["id"]}
    agent_note = by_id[ids["on_current"]["id"]]
    assert agent_note["scope"] == {"type": "application", "id": current["id"]}
    assert agent_note["actor"]["token_kind"] == "agent"
    assert agent_note["run"]["workflow"] == "track-applications"
    # Writing a note is represented by the note, not by an event too.
    kinds = [item["event"]["kind"] for item in items if item["type"] == "event"]
    assert "note_added" not in kinds and "job_added" in kinds
    assert "application_created" in kinds
    # Moving to Interview recorded an employer response: kind response.
    responses = [item for item in items if item["kind"] == "response"]
    assert [item["event"]["kind"] for item in responses] == ["response_added"]
    assert result["counts"] == {
        "note": 3,
        "event": len(items) - 3 - 1,
        "response": 1,
    }
    # Events stay text-free: no note text in any payload.
    for item in items:
        if item["type"] == "event":
            assert "Lead with" not in json.dumps(item["event"]["payload"])
            assert item["note"] is None
        else:
            assert item["event"] is None


def test_a_job_timeline_holds_every_application(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    ids = seeded(workspace)
    result = workspace.timeline(job_id=ids["job"]["id"])
    entries = {item["id"] for item in result["items"]}
    assert {ids["on_job"]["id"], ids["on_older"]["id"], ids["on_current"]["id"]} <= entries
    scopes = {item["application_id"] for item in result["items"]}
    assert scopes == {None, ids["older"]["id"], ids["current"]["id"]}
    assert workspace.list_notes(ids["job"]["id"])["items"][0]["pinned"]


def test_filters_counts_and_paging(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    ids = seeded(workspace)
    application_id = ids["current"]["id"]

    def read(**value):
        return workspace.timeline(application_id=application_id, value=value)

    full = read(limit=200)
    notes = read(kinds=["note"])
    assert {item["type"] for item in notes["items"]} == {"note"}
    assert notes["total"] == notes["counts"]["note"] == 3
    # Counts follow every filter but the kind.
    assert notes["counts"] == full["counts"]
    events = read(kinds=["event", "response"])
    assert events["total"] == full["total"] - 3
    by_agent = read(who=["agent"])
    assert by_agent["items"] and {item["actor"]["token_kind"] for item in by_agent["items"]} == {
        "agent"
    }
    owner = read(who=["owner"])
    assert {item["actor"]["kind"] for item in owner["items"]} == {"owner"}
    system = read(who=["system"])
    assert {item["actor"]["kind"] for item in system["items"]} == {"system"}
    assert by_agent["total"] + owner["total"] + system["total"] == full["total"]
    job_only = read(scope="job")
    assert {item["scope"]["type"] for item in job_only["items"]} == {"job"}
    application_only = read(scope="application")
    assert job_only["total"] + application_only["total"] == full["total"]
    assert read(since="2999-01-01")["total"] == 0
    assert read(until="2000-01-01")["total"] == 0
    newest = full["items"][1]["created_at"][:10]
    assert read(since=newest, until=newest)["total"] >= 1
    pages = [read(limit=2, offset=offset)["items"] for offset in range(0, full["total"], 2)]
    assert [item["id"] for page in pages for item in page] == [item["id"] for item in full["items"]]
    with pytest.raises(DomainError) as both:
        workspace.timeline(job_id=ids["job"]["id"], application_id=application_id)
    assert both.value.code == "timeline_scope"
    with pytest.raises(DomainError) as unknown:
        workspace.timeline(application_id="unknown")
    assert unknown.value.status == 404
    with pytest.raises(DomainError):
        workspace.timeline(job_id="unknown")


def test_notes_record_their_author_and_run(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    target = job(workspace)
    with acting_as(OWNER):
        owner = workspace.add_note(target["id"], {"body": "By the owner."})
    with acting_as(AGENT):
        before_run = workspace.add_note(target["id"], {"body": "Before a run."})
        run = ActivityService(workspace).start_run({"workflow": "review-inbox"})
        in_run = workspace.add_note(target["id"], {"body": "In a run."})
    with acting_as(SYSTEM):
        system = workspace.add_note(target["id"], {"body": "By the system."})
    assert (owner["author"]["kind"], owner["run"]) == ("owner", None)
    assert before_run["author"]["name"] == "Synthetic agent" and before_run["run"] is None
    assert in_run["run"] == {"id": run["id"], "workflow": "review-inbox"}
    assert system["author"]["kind"] == "system"
    assert (owner["scope"], owner["pinned"]) == ("job", False)
    # The run report counts the note it wrote.
    assert ActivityService(workspace).get_run(run["id"])["change_counts"] == {"note_added": 1}


def test_one_pinned_note_per_scope_and_pinning_is_recorded(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    target = job(workspace)
    application = workspace.create_application({"job_id": target["id"]})
    first = workspace.add_note(target["id"], {"body": "First.", "pinned": True})
    second = workspace.add_note(target["id"], {"body": "Second."})
    on_application = workspace.add_note(
        target["id"], {"body": "On it.", "application_id": application["id"], "pinned": True}
    )
    # Each scope has its own pin.
    assert workspace.get_note(first["id"])["pinned"] and on_application["pinned"]
    pinned = workspace.pin_note(second["id"], {"expected_version": 1})
    assert pinned["pinned"] and pinned["version"] == 2
    replaced = workspace.get_note(first["id"])
    assert (replaced["pinned"], replaced["version"]) == (False, 2)
    with pytest.raises(DomainError) as stale:
        workspace.pin_note(first["id"], {"expected_version": 1})
    assert stale.value.details == {"current_version": 2}
    # Unpinning keeps the note; doing it twice is no change.
    unpinned = workspace.pin_note(second["id"], {"expected_version": 2, "pinned": False})
    assert (unpinned["pinned"], unpinned["version"]) == (False, 3)
    assert (
        workspace.pin_note(second["id"], {"expected_version": 3, "pinned": False})["version"] == 3
    )
    events = workspace.db.all(
        "SELECT kind,payload,subject_id FROM events WHERE subject_type='note' ORDER BY rowid"
    )
    assert [(row["kind"], json.loads(row["payload"])) for row in events[-3:]] == [
        ("note_unpinned", {"version": 2, "replaced_by": second["id"]}),
        ("note_pinned", {"version": 2}),
        ("note_unpinned", {"version": 3}),
    ]
    # SQLite refuses a second pinned note in one scope.
    with workspace.db.transaction() as conn:
        conn.execute("UPDATE notes SET pinned_at='2026-01-01' WHERE id=?", (first["id"],))
    with pytest.raises(sqlite3.IntegrityError), workspace.db.transaction() as conn:
        conn.execute("UPDATE notes SET pinned_at='2026-01-01' WHERE id=?", (second["id"],))


def test_the_application_note_field_is_gone_and_the_pinned_note_holds_guidance(tmp_path):
    """0.23 removed the application ``note`` field; the pinned note is the one place."""
    workspace = Workspace(tmp_path / "timeline.sqlite")
    target = job(workspace)
    with pytest.raises(ValidationError):
        workspace.create_application({"job_id": target["id"], "note": "Removed field"})
    text = "Ünïcode ✓\r\nTrailing space  \n\n"
    application = guided_application(workspace, target["id"], text)
    assert "note" not in application
    pinned = application["pinned_note"]
    assert (pinned["body"], pinned["scope"], pinned["pinned"]) == (text, "application", True)
    with pytest.raises(ValidationError):
        workspace.update_application(
            application["id"], {"expected_version": application["version"], "note": "x"}
        )
    assert workspace.get_note(pinned["id"])["version"] == 1
    # Searching applications finds the pinned note's text.
    workspace.update_note(pinned["id"], {"expected_version": 1, "body": "Revised guidance"})
    assert workspace.list_applications(q="Revised guid")["total"] == 1
    workspace.pin_note(pinned["id"], {"expected_version": 2, "pinned": False})
    assert workspace.get_application(application["id"])["pinned_note"] is None
    assert workspace.list_applications(q="Revised guid")["total"] == 0


def test_new_contexts_freeze_the_pinned_note(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    documents = DocumentService(workspace)
    CareerService(workspace).create_template(TemplateCreate(name="Synthetic CV", tex="TeX"))
    target = job(workspace)
    application = workspace.create_application({"job_id": target["id"]})
    workspace.add_note(
        target["id"],
        {"body": "Pinned guidance ✓", "application_id": application["id"], "pinned": True},
    )
    workspace.add_note(target["id"], {"body": "Not pinned", "application_id": application["id"]})
    context = documents.prepare_context(
        ContextCreate(application_id=application["id"], note="For this pass")
    )
    payload = context["payload"]
    assert payload["application"]["note"] == "Pinned guidance ✓"
    assert payload["instructions"]["application_note"] == "Pinned guidance ✓\n\nFor this pass"
    # A later edit leaves the frozen copy as it was.
    pinned = workspace.get_application(application["id"])["pinned_note"]
    workspace.update_note(pinned["id"], {"expected_version": 1, "body": "Changed"})
    assert documents.get_context(context["id"])["payload"] == payload


def test_merge_keeps_one_pinned_job_note(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    source = job(workspace, "Synthetic engineer copy")
    target = job(workspace)
    kept = workspace.add_note(target["id"], {"body": "Kept.", "pinned": True})
    moved = workspace.add_note(source["id"], {"body": "Moved.", "pinned": True})
    workspace.merge_jobs(source["id"], target["id"], 1, 1)
    notes = {item["id"]: item for item in workspace.list_notes(target["id"])["items"]}
    assert notes[kept["id"]]["pinned"] and not notes[moved["id"]]["pinned"]
    unpinned = workspace.timeline(job_id=target["id"], value={"kinds": ["event"]})["items"]
    assert any(item["event"]["kind"] == "note_unpinned" for item in unpinned)


def tool(client, headers, name, arguments):
    response = client.post(
        "/mcp",
        headers={**MCP_HEADERS, **headers},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    result = response.json()["result"]
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_rest_and_mcp_return_identical_timelines(tmp_path):
    app = create_app(tmp_path / "parity.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    workspace = app.state.workspace
    ids = seeded(workspace)
    headers = {"Authorization": "Bearer " + app.state.auth.create_token("Synthetic")["token"]}
    job_id, application_id = ids["job"]["id"], ids["current"]["id"]
    cases = [
        ({}, ""),
        ({"kinds": ["note", "response"]}, "?kinds=note&kinds=response"),
        (
            {"who": ["agent", "owner"], "scope": "application"},
            "?who=agent&who=owner&scope=application",
        ),
        ({"limit": 2, "offset": 1}, "?limit=2&offset=1"),
        ({"since": "2000-01-01", "until": "2999-12-31"}, "?since=2000-01-01&until=2999-12-31"),
    ]
    with TestClient(app, base_url="http://localhost:8080") as client:
        for value, query in cases:
            for path, arguments in (
                (f"/api/v1/jobs/{job_id}/timeline", {"job_id": job_id}),
                (
                    f"/api/v1/applications/{application_id}/timeline",
                    {"application_id": application_id},
                ),
            ):
                rest = client.get(path + query, headers=headers)
                assert rest.status_code == 200, rest.text
                mcp = tool(client, headers, "timeline_get", {**arguments, "value": value})
                assert mcp == rest.json(), (path, value)
                assert mcp["items"], (path, value)
        # Pinning over REST and MCP alike.
        note = ids["on_job"]
        pinned = client.post(
            f"/api/v1/notes/{note['id']}/pin", json={"expected_version": 1}, headers=headers
        ).json()
        assert pinned["pinned"] and pinned["version"] == 2
        unpinned = tool(
            client,
            headers,
            "notes_pin",
            {"note_id": note["id"], "value": {"expected_version": 2, "pinned": False}},
        )
        assert (unpinned["pinned"], unpinned["version"]) == (False, 3)
        refused = client.get(f"/api/v1/jobs/{job_id}/timeline?kinds=text", headers=headers)
        assert refused.status_code == 422
