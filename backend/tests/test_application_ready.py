"""Ready as a stored step of an application: marking, automatic clearing and the ready queue."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from document_fixtures import PDF, attach, source_revision
from openings.activity import ActivityService
from openings.actors import OWNER, acting_as, token_actor
from openings.app import create_app
from openings.career import TemplateCreate
from openings.documents import ContextCreate, DocumentCreate, ReviewUpdate, UploadReservation
from openings.errors import DomainError
from openings.workspace import Workspace
from schema_fixtures import columns, make_schema_seven

AGENT = token_actor("token-agent", "Synthetic agent")
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "ready.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    return app


def start(app, title="Synthetic engineer", **fields):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})
    return workspace.create_application({"job_id": job["id"], **fields})


def put(app):
    # No lifespan: an application starts its MCP session manager only once.
    return TestClient(app).put


def upload(app, document_id, name="photo.png"):
    """Add a file that is neither the source nor the PDF to a revision."""
    grant = app.state.documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=document_id,
            name=name,
            size=len(PDF),
            media_type="image/png",
        )
    )
    return put(app)(grant["url"], headers=grant["headers"], content=PDF)


def approved(app, application, kind="resume", previous_id=None, text="Synthetic content."):
    """Save one revision with its source and PDF and approve it."""
    return source_revision(
        app.state.documents,
        put(app),
        application["id"],
        kind,
        text,
        title=kind,
        previous_id=previous_id,
        approve=True,
    )


def ready(app, title="Synthetic engineer", **fields):
    """An application with an approved CV and letter, marked ready by the agent."""
    workspace = app.state.workspace
    application = start(app, title, **fields)
    cv = approved(app, application)
    approved(app, application, "cover_letter")
    current = workspace.get_application(application["id"])
    with acting_as(AGENT):
        marked = workspace.set_ready(application["id"], {"expected_version": current["version"]})
    assert marked["readiness"] == "ready" and marked["ready_at"]
    return marked, cv


def refusal(workspace, application):
    current = workspace.get_application(application["id"])
    with pytest.raises(DomainError) as error:
        workspace.set_ready(application["id"], {"expected_version": current["version"]})
    assert (error.value.status, error.value.code) == (409, "application_not_ready")
    assert workspace.get_application(application["id"])["ready_at"] is None
    return error.value.details


def cleared(workspace, application, reason, actor="owner"):
    """The application is no longer ready and the newest clearing event says why and who."""
    current = workspace.get_application(application["id"])
    assert current["ready_at"] is None and current["ready_by"] is None
    assert current["readiness"] != "ready"
    assert current["version"] > application["version"]
    event = ActivityService(workspace).list_events(
        {"application_id": application["id"], "kind": "application_ready_cleared"}
    )["items"][0]
    assert event["payload"] == {"reason": reason, "automatic": reason != "unmarked"}
    assert event["actor"]["kind"] == actor
    assert event["subject"]["type"] == "application"
    return current


def test_marking_ready_is_refused_until_every_check_passes(app):
    workspace, documents = app.state.workspace, app.state.documents
    application = start(
        app, requirements=[{"id": "permit", "text": "Work permit", "blocking": True}]
    )
    details = refusal(workspace, application)
    assert (details["check"], details["blocking_requirements"]) == ("blocked", 1)
    application = workspace.update_application(
        application["id"],
        {
            "expected_version": application["version"],
            "requirements": [
                {"id": "permit", "text": "Work permit", "blocking": True, "resolved": True}
            ],
        },
    )
    assert refusal(workspace, application)["check"] == "none"
    cv = documents.create_document(DocumentCreate(application_id=application["id"], kind="resume"))
    assert refusal(workspace, application)["check"] == "missing_pdf"
    attach(documents, put(app), cv["id"], "A")
    details = refusal(workspace, application)
    assert (details["check"], details["readiness"]) == ("unreviewed", "unreviewed")
    cv = documents.get_document(cv["id"])
    documents.review_document(cv["id"], ReviewUpdate(expected_version=cv["version"]))
    current = workspace.get_application(application["id"])
    assert (current["readiness"], current["ready_at"], current["ready_by"]) == (
        "reviewed",
        None,
        None,
    )

    with pytest.raises(DomainError) as stale:
        workspace.set_ready(application["id"], {"expected_version": current["version"] + 1})
    assert stale.value.details == {"current_version": current["version"]}
    with acting_as(AGENT):
        marked = workspace.set_ready(application["id"], {"expected_version": current["version"]})
    assert (marked["readiness"], marked["version"]) == ("ready", current["version"] + 1)
    assert marked["ready_by"]["label"] == "Synthetic agent" and marked["status"] == "draft"
    # Marking again changes nothing; clearing the mark is explicit and recorded.
    again = workspace.set_ready(application["id"], {"expected_version": marked["version"]})
    assert (again["version"], again["ready_at"]) == (marked["version"], marked["ready_at"])
    with acting_as(OWNER):
        unmarked = workspace.set_ready(
            application["id"], {"expected_version": marked["version"], "ready": False}
        )
    assert (unmarked["readiness"], unmarked["ready_at"]) == ("reviewed", None)
    cleared(workspace, marked, "unmarked")
    assert (
        workspace.set_ready(
            application["id"], {"expected_version": unmarked["version"], "ready": False}
        )["version"]
        == unmarked["version"]
    )
    kinds = [item["kind"] for item in workspace.application_events(application["id"])["items"]]
    assert kinds[:2] == ["application_ready_cleared", "application_marked_ready"]
    with pytest.raises(DomainError, match="Application was not found"):
        workspace.set_ready("missing", {"expected_version": 1})


def test_only_a_preparing_application_can_be_marked_ready(app):
    workspace = app.state.workspace
    application = start(app)
    approved(app, application)
    current = workspace.get_application(application["id"])
    applied = workspace.update_application(
        application["id"], {"expected_version": current["version"], "status": "applied"}
    )
    details = refusal(workspace, applied)
    assert (details["check"], details["status"]) == ("stage", "applied")
    assert workspace.get_application(application["id"])["readiness"] == "reviewed"


def test_a_new_revision_or_context_clears_ready(app):
    workspace, documents = app.state.workspace, app.state.documents
    application, cv = ready(app)
    with acting_as(AGENT):
        revision = documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                kind="resume",
                previous_id=cv["id"],
            )
        )
    current = cleared(workspace, application, "document_created", "token")
    assert current["readiness"] == "missing_pdf"
    assert workspace.list_applications(readiness="ready")["total"] == 0
    # Saving the same empty revision again creates no revision and is not a change.
    count = len(workspace.application_events(application["id"])["items"])
    documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="resume",
            previous_id=cv["id"],
        )
    )
    assert len(workspace.application_events(application["id"])["items"]) == count
    # Removing the new revision makes the approved one current again: checks pass,
    # but the judgement has to be made again.
    documents.delete_document(revision["id"], revision["version"])
    assert workspace.get_application(application["id"])["readiness"] == "reviewed"

    second, _ = ready(app, "Second synthetic engineer")
    app.state.career.create_template(TemplateCreate(name="Synthetic CV", tex="Synthetic"))
    with acting_as(OWNER):
        documents.prepare_context(ContextCreate(application_id=second["id"]))
    current = cleared(workspace, second, "context_prepared")
    assert current["readiness"] == "reviewed"


def test_deleting_a_current_revision_clears_ready(app):
    workspace, documents = app.state.workspace, app.state.documents
    application, cv = ready(app)
    with acting_as(OWNER):
        documents.delete_document(cv["id"], cv["version"])
    current = cleared(workspace, application, "document_deleted")
    assert [item["kind"] for item in current["preparation"]] == ["cover_letter"]


def test_a_file_added_to_a_current_revision_clears_ready(app):
    workspace = app.state.workspace
    application, cv = ready(app)
    # Approved revisions refuse new files, so a ready application cannot change this way.
    with pytest.raises(DomainError, match="Approved documents are immutable"):
        upload(app, cv["id"])
    assert workspace.get_application(application["id"])["ready_at"]
    # Should a current revision ever be writable again, its upload clears the step.
    with sqlite3.connect(workspace.db.path) as conn:
        conn.execute("UPDATE documents SET review_state='draft' WHERE id=?", (cv["id"],))
    with acting_as(AGENT):
        grant = app.state.documents.reserve_upload(
            UploadReservation(
                owner_type="document",
                owner_id=cv["id"],
                name="photo.png",
                size=len(PDF),
                media_type="image/png",
            )
        )
    uploaded = put(app)(grant["url"], headers=grant["headers"], content=PDF)
    assert uploaded.status_code == 200
    # The raw upload is attributed to the token that reserved it.
    cleared(workspace, application, "file_uploaded", "token")


@pytest.mark.parametrize("change", ["added", "unresolved"])
def test_a_blocking_requirement_clears_ready(app, change):
    workspace = app.state.workspace
    resolved = {"id": "permit", "text": "Work permit", "blocking": True, "resolved": True}
    application, _ = ready(app, requirements=[resolved])
    # Changes that leave no unresolved blocking requirement keep the step.
    application = workspace.update_application(
        application["id"],
        {
            "expected_version": application["version"],
            "priority": 2,
            "requirements": [resolved, {"id": "format", "text": "One page", "blocking": False}],
        },
    )
    assert application["readiness"] == "ready" and application["ready_at"]
    requirements = (
        [resolved, {"id": "language", "text": "German C1", "blocking": True}]
        if change == "added"
        else [{**resolved, "resolved": False}]
    )
    with acting_as(AGENT):
        updated = workspace.update_application(
            application["id"],
            {"expected_version": application["version"], "requirements": requirements},
        )
    assert (updated["readiness"], updated["ready_at"]) == ("blocked", None)
    cleared(workspace, application, "blocking_requirement", "token")


@pytest.mark.parametrize(
    "patch", [{"status": "applied"}, {"status": "closed", "outcome": "not_pursued"}]
)
def test_leaving_preparing_clears_ready(app, patch):
    workspace = app.state.workspace
    application, _ = ready(app)
    with acting_as(OWNER):
        moved = workspace.update_application(
            application["id"], {"expected_version": application["version"], **patch}
        )
    assert (moved["status"], moved["ready_at"]) == (patch["status"], None)
    cleared(workspace, application, "left_preparing")
    # Coming back to Preparing does not restore the earlier judgement.
    back = workspace.update_application(
        application["id"], {"expected_version": moved["version"], "status": "draft"}
    )
    assert (back["readiness"], back["ready_at"]) == ("reviewed", None)


def test_the_ready_queue_lists_filters_sorts_and_counts(app):
    workspace = app.state.workspace
    first, _ = ready(app, "First ready")
    reviewed = start(app, "Reviewed only")
    approved(app, reviewed)
    second, _ = ready(app, "Second ready")
    untouched = start(app, "No documents")

    def ids(**query):
        return [item["id"] for item in workspace.list_applications(**query)["items"]]

    assert ids(readiness="ready", sort="ready") == [first["id"], second["id"]]
    assert ids(readiness="reviewed") == [reviewed["id"]]
    assert ids(readiness="none") == [untouched["id"]]
    # Longest waiting first, then everything that is not marked ready.
    assert ids(sort="ready")[:2] == [first["id"], second["id"]]
    assert ids(ready_since=second["ready_at"]) == [second["id"]]
    assert ids(ready_until=first["ready_at"]) == [first["id"]]
    listed = workspace.list_applications()
    assert (listed["total"], listed["ready_count"]) == (4, 2)
    item = next(item for item in listed["items"] if item["id"] == first["id"])
    assert (item["readiness"], item["ready_at"]) == ("ready", first["ready_at"])
    assert item["ready_by"]["label"] == "Synthetic agent"
    assert "ready_by_kind" not in item
    other = next(item for item in listed["items"] if item["id"] == reviewed["id"])
    assert (other["readiness"], other["ready_at"], other["ready_by"]) == ("reviewed", None, None)
    overview = workspace.overview()
    assert (overview["drafts"], overview["ready"]) == (4, 2)

    result = workspace.bulk_applications(
        {
            "action": "mark_ready",
            "items": [
                {"id": reviewed["id"], "expected_version": other["version"]},
                {"id": untouched["id"], "expected_version": untouched["version"]},
            ],
        }
    )
    assert (result["succeeded"], result["failed"]) == (1, 1)
    assert result["items"][0]["result"]["readiness"] == "ready"
    failure = result["items"][1]["error"]
    assert (failure["code"], failure["details"]["check"]) == ("application_not_ready", "none")
    assert workspace.list_applications()["ready_count"] == 3
    result = workspace.bulk_applications(
        {
            "action": "unmark_ready",
            "items": [{"id": first["id"], "expected_version": first["version"]}],
        }
    )
    assert result["items"][0]["result"]["ready_at"] is None
    assert ids(readiness="ready", sort="ready") == [second["id"], reviewed["id"]]


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
    if result.get("isError"):
        return None, json.loads(result["content"][0]["text"])["error"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"]), None


def test_rest_and_mcp_mark_ready_with_the_same_inputs_and_errors(app):
    workspace = app.state.workspace
    token = app.state.auth.create_token("Synthetic agent")
    headers = {"Authorization": "Bearer " + token["token"]}
    application = start(app)
    body = {"expected_version": application["version"]}
    with TestClient(app, base_url="http://localhost:8080") as client:
        refused = client.post(
            f"/api/v1/applications/{application['id']}/ready", json=body, headers=headers
        )
        _, error = tool(
            client,
            headers,
            "applications_ready",
            {"application_id": application["id"], "value": body},
        )
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == error["code"] == "application_not_ready"
        assert refused.json()["error"]["details"] == error["details"]
        assert error["details"]["check"] == "none"
        approved(app, application)
        current = workspace.get_application(application["id"])
        marked, error = tool(
            client,
            headers,
            "applications_ready",
            {
                "application_id": application["id"],
                "value": {"expected_version": current["version"]},
            },
        )
        assert error is None and marked["readiness"] == "ready"
        assert marked["ready_by"]["label"] == "Synthetic agent"
        over_rest = client.get(f"/api/v1/applications/{application['id']}", headers=headers).json()
        assert over_rest["ready_at"] == marked["ready_at"]
        for query in ({"readiness": "ready"}, {"sort": "ready"}, {"ready_since": "2000-01-01"}):
            listed = client.get("/api/v1/applications", params=query, headers=headers).json()
            over_mcp, error = tool(client, headers, "applications_list", {"value": query})
            assert error is None and listed == over_mcp and listed["ready_count"] == 1
        unmarked = client.post(
            f"/api/v1/applications/{application['id']}/ready",
            json={"expected_version": marked["version"], "ready": False},
            headers=headers,
        ).json()
        assert (unmarked["readiness"], unmarked["ready_at"]) == ("reviewed", None)
        bulk, error = tool(
            client,
            headers,
            "applications_bulk",
            {
                "value": {
                    "action": "mark_ready",
                    "items": [{"id": application["id"], "expected_version": unmarked["version"]}],
                }
            },
        )
        assert error is None and bulk["succeeded"] == 1
        invalid = client.get(
            "/api/v1/applications", params={"ready_since": "soon"}, headers=headers
        )
        assert invalid.status_code == 422


def test_schema_seven_applications_upgrade_without_a_ready_mark(tmp_path):
    path = tmp_path / "schema7.sqlite"
    app = create_app(path, start_worker=False)
    application = start(app)
    approved(app, application)
    before = app.state.workspace.get_application(application["id"])
    make_schema_seven(path)
    with sqlite3.connect(path) as conn:
        assert "ready_at" not in {row[0] for row in columns(conn, "applications")}
    upgraded = Workspace(path)
    after = upgraded.get_application(application["id"])
    assert (after["readiness"], after["ready_at"], after["ready_by"]) == ("reviewed", None, None)
    assert (after["version"], after["updated_at"]) == (before["version"], before["updated_at"])
    marked = upgraded.set_ready(application["id"], {"expected_version": after["version"]})
    assert marked["readiness"] == "ready"


def test_undoing_mark_applied_restores_the_ready_draft(app):
    workspace = app.state.workspace
    marked, _ = ready(app)
    applied = workspace.update_application(
        marked["id"], {"expected_version": marked["version"], "status": "applied"}
    )
    assert applied["applied_at"] and applied["ready_at"] is None
    # Undo, as the dashboard does: back to Preparing without a sent day, then Ready again.
    draft = workspace.update_application(
        marked["id"],
        {"expected_version": applied["version"], "status": "draft", "applied_at": None},
    )
    assert (draft["status"], draft["applied_at"]) == ("draft", None)
    assert not draft.get("responses")
    again = workspace.set_ready(marked["id"], {"expected_version": draft["version"]})
    assert again["readiness"] == "ready" and again["status"] == "draft"
