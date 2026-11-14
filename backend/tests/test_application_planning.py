"""Application priority, deadline, employer requirements and readiness and what is missing for Ready."""

import json

import pytest
from fastapi.testclient import TestClient

from document_fixtures import attach, attach_pdf
from openings.app import create_app
from openings.documents import DocumentCreate
from openings.errors import DomainError
from openings.interfaces.operation import without_empty
from openings.workspace import Workspace
from timeline_fixtures import guided_application


def seeded(path):
    workspace = Workspace(path)
    job = workspace.ingest_job(
        {"title": "Synthetic platform engineer", "company": "Example", "posting": "Run APIs."}
    )
    application = guided_application(
        workspace,
        job["id"],
        "Synthetic guidance",
        questions=[{"id": "why", "label": "Why this role?"}],
    )
    application = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "answers": {"why": "Synthetic answer."}},
    )
    return workspace, job, application


def test_planning_fields_validate_and_clear_explicitly(tmp_path):
    workspace = Workspace(tmp_path / "fields.sqlite")
    job = workspace.ingest_job({"title": "Synthetic role", "posting": "Build services."})
    application = workspace.create_application(
        {
            "job_id": job["id"],
            "priority": 1,
            "deadline": "2026-12-01",
            "requirements": [
                {"kind": "authorship", "text": "Write without AI tools.", "blocking": True},
                {"id": "refs", "kind": "reference", "text": "Two references."},
            ],
        }
    )
    assert application["priority"] == 1 and application["deadline"] == "2026-12-01"
    first, second = application["requirements"]
    assert first["id"] and second["id"] == "refs"
    assert first == {
        "id": first["id"],
        "kind": "authorship",
        "text": "Write without AI tools.",
        "blocking": True,
        "resolved": False,
        "note": "",
    }
    assert application["missing"] == ["cv", "letter", "requirement:" + first["id"]]
    assert (application["open_requirements"], application["blocking_requirements"]) == (2, 1)

    for invalid in (
        {"priority": 0},
        {"priority": 6},
        {"deadline": "2026-02-30"},
        {"deadline": "2026-12-01T10:00:00Z"},
        {"requirements": None},
        {"requirements": [{"kind": "other", "text": ""}]},
        {"requirements": [{"kind": "salary", "text": "Synthetic"}]},
    ):
        with pytest.raises(ValueError):
            workspace.update_application(
                application["id"], {"expected_version": application["version"], **invalid}
            )
    with pytest.raises(DomainError) as duplicate:
        workspace.update_application(
            application["id"],
            {
                "expected_version": application["version"],
                "requirements": [{"id": "x", "text": "A"}, {"id": "x", "text": "B"}],
            },
        )
    assert duplicate.value.code == "requirement_id"
    assert workspace.get_application(application["id"]) == application

    resolved = [{**first, "resolved": True, "note": "Owner writes the letter."}, second]
    application = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "requirements": resolved},
    )
    assert application["requirements"] == resolved
    assert application["missing"] == ["cv", "letter"]
    assert application["blocking_requirements"] == 0
    unchanged = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "requirements": resolved},
    )
    assert unchanged["version"] == application["version"]
    with pytest.raises(DomainError) as stale:
        workspace.update_application(
            application["id"], {"expected_version": application["version"] - 1, "priority": 3}
        )
    assert stale.value.status == 409
    cleared = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "priority": None, "deadline": None},
    )
    assert cleared["priority"] is None and cleared["deadline"] is None
    events = workspace.application_events(application["id"])["items"]
    assert {"priority", "deadline"} <= set(events[0]["payload"]["fields"])


def test_missing_documents_follow_current_revisions_and_sorts_by_plan(tmp_path):
    app = create_app(tmp_path / "readiness.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents

    def start(title, **fields):
        job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build."})
        return workspace.create_application({"job_id": job["id"], **fields})

    def missing(application):
        return workspace.get_application(application["id"])["missing"]

    def ids(**query):
        return [item["id"] for item in workspace.list_applications(**query)["items"]]

    late = start("Late", deadline="2027-03-01", priority=3)
    soon = start("Soon", deadline="2026-12-01", required_documents=["cv"])
    urgent = start("Urgent", deadline="2027-03-01", priority=1)
    loose = start("Loose")
    assert ids(sort="deadline") == [soon["id"], urgent["id"], late["id"], loose["id"]]
    assert ids(sort="priority") == [urgent["id"], late["id"], soon["id"], loose["id"]]

    cv = documents.create_document(DocumentCreate(application_id=soon["id"], kind="cv", title="CV"))
    documents.create_document(
        DocumentCreate(
            application_id=soon["id"], kind="answers", title="Form", content={"text": "B"}
        )
    )
    assert missing(soon) == ["cv"]
    with TestClient(app) as client:
        attach(documents, client.put, cv["id"], "A", pdf=False)
        assert missing(soon) == ["cv"]
        attach_pdf(documents, client.put, cv["id"], "A")
    # Form answers never affect Ready.
    assert missing(soon) == [] and ids(stage="ready") == [soon["id"]]
    # A new revision replaces the complete leaf; its parent's PDF does not count.
    documents.create_document(
        DocumentCreate(application_id=soon["id"], kind="cv", title="CV v2", previous_id=cv["id"])
    )
    assert missing(soon) == ["cv"]
    updated = workspace.update_application(
        late["id"],
        {
            "expected_version": late["version"],
            "requirements": [
                {"id": "permit", "kind": "eligibility", "text": "Work permit", "blocking": True}
            ],
        },
    )
    assert updated["missing"] == ["cv", "letter", "requirement:permit"]
    assert ids(stage="ready") == []
    assert set(ids(needs="documents")) == {soon["id"], late["id"], urgent["id"], loose["id"]}
    listed = next(
        item for item in workspace.list_applications()["items"] if item["id"] == late["id"]
    )
    assert listed["blocking_requirements"] == listed["open_requirements"] == 1
    assert "requirements" not in listed
    with pytest.raises(DomainError):
        workspace.list_applications(stage="maybe")


def test_applications_filter_by_the_time_they_were_applied(tmp_path):
    app = create_app(tmp_path / "applied.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    workspace = app.state.workspace
    token = app.state.auth.create_token("Synthetic tracking client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}

    def applied(title, when):
        job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build."})
        created = workspace.create_application({"job_id": job["id"]})
        fields = {"status": "applied", "applied_at": when} if when else {}
        return workspace.update_application(
            created["id"], {"expected_version": created["version"], **fields}
        )["id"]

    old = applied("Old", "2026-09-01T09:00:00Z")
    recent = applied("Recent", "2026-11-01T09:00:00Z")
    applied("Preparing", None)

    def ids(**query):
        return [item["id"] for item in workspace.list_applications(**query)["items"]]

    assert ids(stage="applied", applied_until="2026-10-12T00:00:00+00:00") == [old]
    assert ids(applied_since="2026-10-12T00:00:00+00:00") == [recent]
    # An application never recorded as applied has no time to compare.
    assert set(ids(applied_until="2027-01-01T00:00:00+00:00")) == {old, recent}
    waiting = workspace.list_applications(stage="applied", applied_until="2026-10-12", limit=1)
    assert (waiting["total"], waiting["stage_counts"]["applied"]) == (1, 1)
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:
        # A date without a time includes its whole day, as the other ranges do.
        rest = client.get("/api/v1/applications", params={"applied_until": "2026-09-01"})
        assert [item["id"] for item in rest.json()["items"]] == [old]
        mcp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "applications_list",
                    "arguments": {"applied_until": "2026-09-01"},
                },
            },
        ).json()["result"]
        assert json.loads(mcp["content"][0]["text"]) == without_empty(rest.json())
        invalid = client.get("/api/v1/applications", params={"applied_since": "soon"})
        assert invalid.status_code == 422


def test_planning_fields_have_rest_and_mcp_parity(tmp_path):
    """REST's one-application routes and MCP's batch tools set the same planning fields."""
    app = create_app(tmp_path / "parity.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic planning client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    workspace = app.state.workspace
    jobs = [workspace.ingest_job({"title": f"Role {n}", "posting": "Build."}) for n in (1, 2)]
    planning = {
        "priority": 2,
        "deadline": "2026-12-15",
        "requirements": [{"id": "ai", "kind": "authorship", "text": "No AI.", "blocking": True}],
    }
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:

        def tool(name, arguments):
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            result = response.json()["result"]
            assert not result.get("isError"), result
            return json.loads(result["content"][0]["text"])

        rest = client.post("/api/v1/applications", json={"job_id": jobs[0]["id"], **planning})
        assert rest.status_code == 200
        rest = rest.json()
        created = tool("applications_create", {"items": [{"job_id": jobs[1]["id"], **planning}]})
        item = created["items"][0]
        assert item["ok"] and item["result"]["created"] is True
        assert rest["missing"] == item["result"]["missing"] == ["cv", "letter", "requirement:ai"]

        resolved = [{**rest["requirements"][0], "resolved": True}]
        rest = client.patch(
            f"/api/v1/applications/{rest['id']}",
            json={"expected_version": rest["version"], "requirements": resolved, "deadline": None},
        ).json()
        changed = tool(
            "applications_update",
            {"items": [{"application_id": item["id"], "requirements": resolved, "deadline": None}]},
        )
        assert changed["items"][0]["result"]["missing"] == rest["missing"] == ["cv", "letter"]
        assert (
            client.patch(
                f"/api/v1/applications/{rest['id']}",
                json={"expected_version": rest["version"], "priority": 9},
            ).status_code
            == 422
        )
        both = tool("applications_get", {"ids": [rest["id"], item["id"]]})["items"]
        for read in both:
            assert (read["priority"], read.get("deadline"), read["ready"]) == (2, None, False)
            assert read["requirements"] == without_empty(rest["requirements"])
        listed = client.get(
            "/api/v1/applications", params={"needs": "documents", "sort": "priority"}
        ).json()
        assert listed["total"] == 2
