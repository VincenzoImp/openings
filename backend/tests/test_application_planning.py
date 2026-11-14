"""Application priority, deadline, employer requirements and readiness and what is missing for Ready."""

import json

import pytest
from fastapi.testclient import TestClient

from document_fixtures import attach, attach_pdf
from openings.app import create_app
from openings.documents import DocumentCreate
from openings.errors import DomainError
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
                    "arguments": {"value": {"applied_until": "2026-09-01"}},
                },
            },
        ).json()["result"]
        assert (
            mcp.get("structuredContent") or json.loads(mcp["content"][0]["text"])
        ) == rest.json()
        invalid = client.get("/api/v1/applications", params={"applied_since": "soon"})
        assert invalid.status_code == 422


@pytest.mark.parametrize("transport", ["rest", "mcp"])
def test_planning_fields_have_rest_and_mcp_parity(tmp_path, transport):
    app = create_app(tmp_path / f"parity-{transport}.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic planning client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    job = app.state.workspace.ingest_job({"title": "Synthetic role", "posting": "Build."})
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:

        def call(tool, method, path, arguments):
            if transport == "rest":
                response = client.request(
                    method,
                    "/api/v1" + path,
                    params=arguments.get("value") if method == "GET" else None,
                    json=arguments.get("value") if method != "GET" else None,
                )
                return response.status_code, response.json()
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            result = response.json()["result"]
            if result.get("isError"):
                return 422, result
            return 200, result.get("structuredContent") or json.loads(result["content"][0]["text"])

        status, created = call(
            "applications_create",
            "POST",
            "/applications",
            {
                "value": {
                    "job_id": job["id"],
                    "priority": 2,
                    "deadline": "2026-12-15",
                    "requirements": [
                        {"id": "ai", "kind": "authorship", "text": "No AI.", "blocking": True}
                    ],
                }
            },
        )
        assert status == 200 and created["missing"] == ["cv", "letter", "requirement:ai"]
        status, updated = call(
            "applications_update",
            "PATCH",
            f"/applications/{created['id']}",
            {
                "application_id": created["id"],
                "value": {
                    "expected_version": created["version"],
                    "requirements": [{**created["requirements"][0], "resolved": True}],
                    "deadline": None,
                },
            },
        )
        assert status == 200 and updated["missing"] == ["cv", "letter"]
        assert updated["deadline"] is None
        status, _ = call(
            "applications_update",
            "PATCH",
            f"/applications/{created['id']}",
            {
                "application_id": created["id"],
                "value": {"expected_version": updated["version"], "priority": 9},
            },
        )
        assert status == 422
        status, listed = call(
            "applications_list",
            "GET",
            "/applications",
            {"value": {"needs": "documents", "sort": "priority"}},
        )
        assert status == 200 and listed["total"] == 1
        item = listed["items"][0]
        assert (item["priority"], item["deadline"], item["ready"]) == (2, None, False)
        assert item["open_requirements"] == item["blocking_requirements"] == 0
        status, got = call(
            "applications_get",
            "GET",
            f"/applications/{created['id']}",
            {"application_id": created["id"]},
        )
        assert status == 200 and got["requirements"] == updated["requirements"]
