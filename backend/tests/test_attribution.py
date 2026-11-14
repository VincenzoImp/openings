"""Minimal attribution (#209): one actor label per change and one batch per call."""

import pytest

from openings.actors import OWNER, SYSTEM, acting_as, batch, current_batch, token_actor
from openings.events import EventLog
from openings.mcp_server import REMOVED_TOOLS


def add_jobs(workspace, count, prefix="Synthetic role"):
    with acting_as(SYSTEM):
        return [
            workspace.ingest_job(
                {"title": f"{prefix} {index}", "company": "Example", "posting": "Build APIs."}
            )
            for index in range(count)
        ]


def bulk(jobs, action, **extra):
    return {
        "action": action,
        "items": [{"id": job["id"], "expected_version": job["version"]} for job in jobs],
        **extra,
    }


class Owner:
    """Requests with an owner token on a client the MCP fixture already started."""

    def __init__(self, client, token):
        self.client, self.headers = client, token["headers"]

    def get(self, path, **options):
        return self.client.get(path, headers=self.headers, **options)

    def post(self, path, **options):
        return self.client.post(path, headers=self.headers, **options)


def events_of(app, **filters):
    return EventLog(app.state.workspace).list_events({"limit": 200, **filters})["items"]


def test_each_writer_has_its_label(app):
    workspace = app.state.workspace
    job = add_jobs(workspace, 1)[0]
    for actor, label in (
        (OWNER, "owner"),
        (token_actor("t1", "Scripts", "owner"), "owner"),
        (token_actor("t2", "Laptop agent", "agent"), "agent:Laptop agent"),
        (SYSTEM, "system"),
    ):
        with acting_as(actor):
            note = workspace.add_note(job["id"], {"body": f"By {label}."})
        assert note["author"] == label
    labels = [
        item["actor"]
        for item in events_of(app, job_id=job["id"], include_system=True)
        if item["kind"] == "note_added"
    ]
    assert sorted(labels) == ["agent:Laptop agent", "owner", "owner", "system"]
    # Outside a request (worker, startup) a change has no batch.
    assert current_batch() is None
    with batch():
        first = current_batch()
        assert first.startswith("b_") and len(first) == 28 and current_batch() == first
    with batch():
        assert current_batch() != first


def test_system_changes_are_left_out_of_the_change_log_by_default(app):
    add_jobs(app.state.workspace, 2)
    assert events_of(app, kind="job_added") == []
    assert len(events_of(app, kind="job_added", include_system=True)) == 2
    assert len(events_of(app, kind="job_added", actor="system")) == 2


def test_one_rest_request_is_one_batch(app, client, agent_token):
    jobs = add_jobs(app.state.workspace, 3)
    response = client.post(
        "/api/v1/jobs/bulk",
        json=bulk(jobs, "dismissed", reason="Not a fit."),
        headers=agent_token["headers"],
    )
    assert response.status_code == 200, response.text
    triaged = events_of(app, kind="triage_changed")
    assert len(triaged) == 3
    assert {item["actor"] for item in triaged} == {"agent:Synthetic agent"}
    (batch_id,) = {item["batch_id"] for item in triaged}
    assert batch_id.startswith("b_")
    # Another request is another batch.
    note = client.post(
        f"/api/v1/jobs/{jobs[0]['id']}/notes",
        json={"body": "Later."},
        headers=agent_token["headers"],
    )
    assert note.status_code in (200, 201), note.text
    later = events_of(app, kind="note_added")[0]
    assert later["batch_id"] not in (None, batch_id)
    assert [item["id"] for item in events_of(app, batch_id=batch_id)] == [
        item["id"] for item in triaged
    ]


def test_an_agent_triage_of_fifty_jobs_is_one_batch_the_owner_restores(app, mcp, owner_token):
    # One HTTP client for both tokens: the owner reads and restores with an owner token.
    client = Owner(mcp.client, owner_token)
    workspace = app.state.workspace
    jobs = add_jobs(workspace, 50)
    with acting_as(OWNER):
        mine = workspace.set_triage(
            add_jobs(workspace, 1, "Owner role")[0]["id"], "dismissed", 1, "Mine."
        )
    _, error = mcp.call("jobs_bulk", {"value": bulk(jobs, "dismissed", reason="Too junior.")})
    assert error is None, error
    triaged = events_of(app, kind="triage_changed", actor="agent:Synthetic agent")
    assert len(triaged) == 50
    (batch_id,) = {item["batch_id"] for item in triaged}
    # The Dismissed tab: by agent, by this token, by this batch and since a time.
    listed = client.get("/api/v1/jobs", params={"dismissed_by": "agent", "limit": 200}).json()
    assert listed["total"] == 50
    assert {item["dismissal"]["by"] for item in listed["items"]} == {"agent:Synthetic agent"}
    assert {item["dismissal"]["category"] for item in listed["items"]} == {"agent"}
    assert {item["dismissal"]["reason"] for item in listed["items"]} == {"Too junior."}
    by_name = client.get(
        "/api/v1/jobs", params={"dismissed_by": "agent:Synthetic agent", "limit": 200}
    ).json()
    assert by_name["total"] == 50
    assert client.get("/api/v1/jobs", params={"dismissed_by": "owner"}).json()["total"] == 1
    assert client.get("/api/v1/jobs", params={"batch_id": batch_id}).json()["total"] == 50
    since = min(item["dismissal"]["at"] for item in listed["items"])
    assert client.get("/api/v1/jobs", params={"since": since}).json()["total"] == 50
    counts = client.get("/api/v1/jobs", params={"include_counts": True}).json()["counts"]
    assert counts["dismissed_by"] == {"agent": 50, "owner": 1, "system": 0}
    refused = client.get("/api/v1/jobs", params={"dismissed_by": "someone"})
    assert refused.status_code == 422
    # One action restores the batch to New.
    items = by_name["items"]
    restored = client.post("/api/v1/jobs/bulk", json=bulk(items, "new"))
    assert restored.status_code == 200, restored.text
    assert client.get("/api/v1/jobs", params={"dismissed_by": "agent"}).json()["total"] == 0
    assert workspace.get_job(mine["id"])["triage"] == "dismissed"
    restoring = events_of(app, kind="triage_changed", actor="owner")
    assert len({item["batch_id"] for item in restoring}) == 2  # the owner's dismissal, the restore


def test_one_mcp_tool_call_is_one_batch(app, mcp):
    jobs = add_jobs(app.state.workspace, 2)
    for job in jobs:
        _, error = mcp.call(
            "notes_create", {"job_id": job["id"], "value": {"body": "Synthetic note."}}
        )
        assert error is None, error
    notes = events_of(app, kind="note_added")
    assert len(notes) == 2 and len({item["batch_id"] for item in notes}) == 2
    # A read makes no batch and records nothing.
    before = len(events_of(app, include_system=True))
    mcp.call("jobs_list", {})
    assert len(events_of(app, include_system=True)) == before


@pytest.mark.parametrize(
    ("tool", "replacement"),
    [
        ("runs_start", "Report what you did in the chat"),
        ("questions_ask", "ask the owner in the chat"),
        ("requests_list", "notes_create"),
        ("skill_notes_update", "working_with_me"),
    ],
)
def test_removed_agent_tools_name_their_replacement(mcp, tool, replacement):
    _, error = mcp.call(tool, {})
    assert error["code"] == "tool_removed" and error["details"] == {"tool": tool}
    assert replacement.lower() in error["message"].lower()


def test_no_removed_tool_or_route_remains(app, mcp, owner_token):
    client = Owner(mcp.client, owner_token)
    listed = {tool["name"] for tool in mcp.rpc("tools/list")["tools"]}
    removed = {
        name
        for name in REMOVED_TOOLS
        if name.split("_")[0] in ("runs", "questions", "requests", "skill")
    }
    assert len(removed) == 19 and not removed & listed
    for path in ("/api/v1/runs", "/api/v1/questions", "/api/v1/requests", "/api/v1/skills/x/notes"):
        assert client.get(path).status_code == 404
    info = client.get("/api/v1/workspace").json()
    assert info["actor"] == "owner" and "open_requests" not in info
