"""One timeline per job and per application: scope, filters, pins and authors."""

import json
import sqlite3

import pytest

from openings.actors import OWNER, SYSTEM, acting_as, batch, token_actor
from openings.errors import DomainError
from openings.workspace import Workspace
from timeline_fixtures import guided_application

AGENT = token_actor("agent-token", "Synthetic agent", "agent")


def job(workspace, title="Synthetic engineer"):
    return workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})


def seeded(workspace):
    """A job with two applications (one closed), job and application notes and a reply."""
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
    with acting_as(AGENT), batch():
        on_current = workspace.add_note(
            first_job["id"], {"body": "Agent observation.", "application_id": current["id"]}
        )
        applied = workspace.update_application(
            current["id"], {"expected_version": current["version"], "status": "applied"}
        )
        applied = workspace.update_application(
            current["id"], {"expected_version": applied["version"], "reply": {"kind": "interview"}}
        )
    return {
        "job": first_job,
        "older": older,
        "current": applied,
        "on_job": on_job,
        "on_older": on_older,
        "on_current": on_current,
    }


def test_application_and_job_timelines_hold_their_entries(tmp_path):
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
    assert agent_note["actor"] == "agent:Synthetic agent" and agent_note["batch_id"] is None
    assert "run" not in agent_note
    # The agent's changes of one call share one batch.
    batches = {item["batch_id"] for item in items if item["actor"] == "agent:Synthetic agent"}
    batches.discard(None)
    assert len(batches) == 1 and batches.pop().startswith("b_")
    # Writing a note is represented by the note, not by an event too.
    kinds = [item["event"]["kind"] for item in items if item["type"] == "event"]
    assert "note_added" not in kinds and "job_added" in kinds
    assert "application_created" in kinds
    # Recording the interview invitation: kind reply.
    replies = [item for item in items if item["kind"] == "reply"]
    assert [item["event"]["kind"] for item in replies] == ["reply_added"]
    assert result["counts"] == {
        "note": 3,
        "event": len(items) - 3 - 1,
        "reply": 1,
    }
    # Events stay text-free: no note text in any payload.
    for item in items:
        if item["type"] == "event":
            assert "Lead with" not in json.dumps(item["event"]["payload"])
            assert item["note"] is None
        else:
            assert item["event"] is None

    # A job's timeline holds every application's entries.
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
    events = read(kinds=["event", "reply"])
    assert events["total"] == full["total"] - 3
    by_agent = read(who=["agent"])
    assert by_agent["items"] and {item["actor"] for item in by_agent["items"]} == {
        "agent:Synthetic agent"
    }
    owner = read(who=["owner"])
    assert {item["actor"] for item in owner["items"]} == {"owner"}
    system = read(who=["system"])
    assert {item["actor"] for item in system["items"]} == {"system"}
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


def test_notes_record_their_author_and_one_pinned_note_per_scope(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    target = job(workspace)
    with acting_as(AGENT):
        agent = workspace.add_note(target["id"], {"body": "By the agent."})
    with acting_as(SYSTEM):
        system = workspace.add_note(target["id"], {"body": "By the system."})
    assert [note["author"] for note in (agent, system)] == ["agent:Synthetic agent", "system"]
    assert (agent["scope"], agent["pinned"]) == ("job", False)
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
    assert stale.value.details == {"current_version": 2, "id": first["id"]}
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


def test_the_pinned_note_holds_an_applications_guidance(tmp_path):
    workspace = Workspace(tmp_path / "timeline.sqlite")
    target = job(workspace)
    text = "Ünïcode ✓\r\nTrailing space  \n\n"
    application = guided_application(workspace, target["id"], text)
    pinned = application["pinned_note"]
    assert (pinned["body"], pinned["scope"], pinned["pinned"]) == (text, "application", True)
    # Searching applications finds the pinned note's text.
    workspace.update_note(pinned["id"], {"expected_version": 1, "body": "Revised guidance"})
    assert workspace.list_applications(q="Revised guid")["total"] == 1
    workspace.pin_note(pinned["id"], {"expected_version": 2, "pinned": False})
    assert workspace.get_application(application["id"])["pinned_note"] is None
    assert workspace.list_applications(q="Revised guid")["total"] == 0


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
