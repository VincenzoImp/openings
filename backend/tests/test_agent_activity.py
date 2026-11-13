"""Attribution of changes, agent runs with stored reports and questions for the owner (schema 8)."""

import json
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from openings.activity import ActivityService
from openings.actors import OWNER, UNKNOWN_LABEL, acting_as, current_actor, token_actor
from openings.app import create_app
from openings.career import (
    CareerService,
    ClaimCreate,
    ClaimUpdate,
    InstructionsUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.db import SCHEMA_VERSION, Database
from openings.discovery import CollectionWrite, DiscoveryService, SourceCreate, SourcePatch
from openings.documents import ContextCreate, DocumentCreate, DocumentService, UploadReservation
from openings.errors import DomainError
from openings.operations import restore_database
from openings.worker import Worker
from openings.workspace import Workspace
from outcome_fixtures import SCHEMA_ELEVEN_COLUMNS
from schema_fixtures import (
    SCHEMA_EIGHT_COLUMNS,
    columns,
    index_names,
    make_schema_seven,
    table_names,
)
from signal_fixtures import SCHEMA_TWELVE_COLUMNS
from timeline_fixtures import older_rows

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
AGENT = token_actor("token-agent", "Synthetic agent")
OTHER = token_actor("token-other", "Second synthetic agent")
REPORT = {
    "summary": "Reviewed the synthetic Inbox.",
    "changes": "Saved one job and asked one question.",
    "not_done": [{"item": "One posting", "reason": "The salary is not stated."}],
    "checks": [
        {"check": "Final Inbox query returned zero jobs."},
        {"check": "PDF render", "verified": False},
    ],
    "limits": "No application was submitted and no employer was contacted.",
    "method": "The workflow lacks a salary filter.",
}


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "activity.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    return app


@pytest.fixture
def services(tmp_path):
    workspace = Workspace(tmp_path / "services.sqlite")
    return workspace, ActivityService(workspace)


def owner_client(app):
    client = TestClient(app)
    session = client.post("/api/v1/auth/login", json={"password": "synthetic-password"})
    client.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    return client


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


def add_job(workspace, title="Synthetic engineer"):
    return workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})


def events(workspace, **filters):
    return ActivityService(workspace).list_events(filters)["items"]


def test_changes_record_the_owner_session_the_named_token_and_the_system(app):
    workspace = app.state.workspace
    token = app.state.auth.create_token("Synthetic agent")
    owner = owner_client(app)
    with TestClient(app, base_url="http://localhost:8080") as anonymous:
        # Async REST handler, sync REST handler in a worker thread, sync and async MCP tools.
        job = owner.post(
            "/api/v1/jobs", json={"title": "Owner job", "company": "Example", "posting": "Build."}
        ).json()
        saved = anonymous.post(
            f"/api/v1/jobs/{job['id']}/triage",
            json={"triage": "saved", "expected_version": job["version"]},
            headers=bearer(token),
        ).json()
        edited, error = tool(
            anonymous,
            token,
            "jobs_update",
            {
                "job_id": job["id"],
                "value": {"expected_version": saved["version"], "location": "Zurich"},
            },
        )
        assert error is None and edited["location"] == "Zurich"
        ingested, error = tool(
            anonymous,
            token,
            "jobs_create",
            {"value": {"title": "Agent job", "company": "Example", "posting": "Run services."}},
        )
        assert error is None
        system = add_job(workspace, "Collected job")
        history = owner.get("/api/v1/events").json()["items"]
    actors = {(item["kind"], item["subject"]["id"]): item["actor"] for item in history}
    agent = {
        "kind": "token",
        "id": token["id"],
        "name": "Synthetic agent",
        "token_kind": "owner",
        "label": "Synthetic agent",
    }
    assert actors[("job_added", job["id"])] == {
        "kind": "owner",
        "id": None,
        "name": None,
        "token_kind": None,
        "label": "Owner (dashboard)",
    }
    assert actors[("triage_changed", job["id"])] == agent
    assert actors[("job_edited", job["id"])] == agent
    assert actors[("job_added", ingested["id"])] == agent
    assert actors[("job_added", system["id"])]["kind"] == "system"
    # The name recorded with the change survives revoking the token.
    app.state.auth.revoke_token(token["id"])
    assert events(workspace, kind="triage_changed")[0]["actor"] == agent


def test_worker_threads_record_the_system_even_when_started_inside_a_request(tmp_path):
    workspace = Workspace(tmp_path / "worker.sqlite")
    seen, ready = [], threading.Event()

    class Discovery:
        def schedule_due(self, stopping):
            seen.append(("schedule", current_actor().kind))

        def claim_task(self, owner, kind):
            seen.append(("claim", current_actor().kind))
            workspace.event("synthetic_worker_change", subject=("task", "synthetic"))
            ready.set()

    worker = Worker(workspace, Discovery())
    # A restore restarts the worker from inside the restoring request.
    with acting_as(AGENT):
        worker.start()
    assert ready.wait(5)
    worker.stop()
    assert {kind for _, kind in seen} == {"system"}
    assert events(workspace, kind="synthetic_worker_change")[0]["actor"]["kind"] == "system"


def test_every_kind_of_write_leaves_an_attributed_record_without_content(tmp_path):
    workspace = Workspace(tmp_path / "writes.sqlite")
    career, documents = CareerService(workspace), DocumentService(workspace)
    discovery, activity = DiscoveryService(workspace), ActivityService(workspace)
    secret = "Synthetic narrative that must never reach the change log"
    with acting_as(AGENT):
        run = activity.start_run({"workflow": "maintain-career", "scope": "Synthetic scope"})
        profile = career.get_profile()
        career.update_profile(
            ProfileUpdate(expected_version=profile["version"], email="owner@example.test")
        )
        career.update_instructions(InstructionsUpdate(expected_version=1, general=secret))
        entry = career.create_knowledge(KnowledgeCreate(title="Synthetic role", narrative=secret))
        entry = career.update_knowledge(
            entry["id"], KnowledgeUpdate(expected_version=entry["version"], narrative=secret + "!")
        )
        claim = career.create_claim(ClaimCreate(knowledge_id=entry["id"], text=secret))
        claim = career.update_claim(
            claim["id"], ClaimUpdate(expected_version=claim["version"], approved=True)
        )
        template = career.create_template(TemplateCreate(name="Synthetic CV", tex=secret))
        template = career.update_template(
            template["id"], TemplateUpdate(expected_version=template["version"], guidance=secret)
        )
        job = add_job(workspace)
        note = workspace.add_note(job["id"], {"body": secret})
        note = workspace.update_note(
            note["id"], {"expected_version": note["version"], "body": secret + "!"}
        )
        application = workspace.create_application({"job_id": job["id"]})
        context = documents.prepare_context(ContextCreate(application_id=application["id"]))
        document = documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                context_id=context["id"],
                kind="other",
                content={"text": secret},
            )
        )
        grant = documents.reserve_upload(
            UploadReservation(
                owner_type="knowledge", owner_id=entry["id"], name="evidence.txt", size=5
            )
        )
        source = discovery.create_source(
            SourceCreate(name="Example board", kind="greenhouse", config={"board": "example"})
        )
        source = discovery.update_source(
            source["id"], SourcePatch(expected_version=source["version"], name="Renamed board")
        )
        discovery.update_collection(
            CollectionWrite(expected_version=discovery.get_collection()["version"], enabled=False)
        )
        workspace.delete_note(note["id"])
        documents.delete_document(document["id"])
        career.delete_claim(claim["id"], claim["version"])
        career.delete_template(template["id"], template["version"])
        discovery.delete_source(source["id"], source["version"])
    # The raw upload authenticates with its grant only and is attributed to who reserved it.
    with TestClient(create_app(workspace.db.path, start_worker=False)) as client:
        uploaded = client.put("/api/v1/transfers", content=b"bytes", headers=grant["headers"])
        assert uploaded.status_code == 200, uploaded.text
    rows = workspace.db.all("SELECT * FROM events ORDER BY created_at")
    assert {row["kind"] for row in rows} >= {
        "profile_updated",
        "instructions_updated",
        "knowledge_created",
        "knowledge_updated",
        "claim_created",
        "claim_updated",
        "claim_deleted",
        "template_created",
        "template_updated",
        "template_deleted",
        "note_added",
        "note_edited",
        "note_deleted",
        "context_prepared",
        "document_created",
        "document_deleted",
        "file_uploaded",
        "source_created",
        "source_updated",
        "source_deleted",
        "collection_updated",
    }
    assert all(
        (row["actor_kind"], row["actor_id"], row["run_id"]) == ("token", AGENT.id, run["id"])
        for row in rows
    )
    assert all(row["subject_type"] and row["subject_id"] for row in rows)
    assert "must never reach" not in json.dumps([row["payload"] for row in rows])
    assert "owner@example.test" not in json.dumps([row["payload"] for row in rows])
    assert all(len(row["payload"]) < 300 for row in rows)
    updated = next(row for row in rows if row["kind"] == "profile_updated")
    assert json.loads(updated["payload"]) == {"fields": ["email"], "version": 2}
    # Reads and unchanged writes add nothing.
    before = len(rows)
    with acting_as(AGENT):
        career.get_profile()
        activity.list_events({})
        career.update_profile(ProfileUpdate(expected_version=2, email="owner@example.test"))
    assert workspace.db.one("SELECT count(*) n FROM events")["n"] == before
    # Deleting an attempt or forgetting a job deliberately removes its own history;
    # the deletion itself stays recorded.
    with acting_as(AGENT):
        application = workspace.get_application(application["id"])
        workspace.delete_application(application["id"], application["version"])
        assert not events(workspace, application_id=application["id"])
        deleted = events(workspace, kind="application_deleted")[0]
        assert deleted["subject"]["id"] == application["id"] and deleted["run_id"] == run["id"]
        workspace.forget_job(job["id"], workspace.get_job(job["id"])["version"])
    assert not events(workspace, job_id=job["id"])
    forgotten = events(workspace, kind="job_forgotten")
    assert [(item["subject"], item["run_id"]) for item in forgotten] == [
        ({"type": "job", "id": job["id"], "label": ""}, run["id"])
    ]


def test_notes_keep_their_author(services):
    workspace, _ = services
    job = add_job(workspace)
    with acting_as(AGENT):
        note = workspace.add_note(job["id"], {"body": "Synthetic note"})
    with acting_as(OWNER):
        workspace.update_note(note["id"], {"expected_version": 1, "body": "Edited"})
    assert workspace.get_note(note["id"])["author"]["label"] == "Synthetic agent"
    assert workspace.list_notes(job["id"])["items"][0]["author"]["kind"] == "token"
    assert [item["actor"]["kind"] for item in events(workspace, subject_type="note")] == [
        "owner",
        "token",
    ]


def test_writes_join_the_open_run_of_their_own_token_only(services):
    workspace, activity = services
    first, second = add_job(workspace, "First"), add_job(workspace, "Second")
    with acting_as(AGENT):
        workspace.set_triage(first["id"], "saved", first["version"])
        run = activity.start_run({"workflow": "review-inbox", "scope": "Two synthetic jobs"})
    with acting_as(OTHER):
        other = activity.start_run({"workflow": "track-applications"})
        workspace.set_triage(second["id"], "dismissed", second["version"])
    with acting_as(AGENT):
        workspace.set_triage(first["id"], "dismissed", 2)
    with acting_as(OWNER):
        workspace.set_triage(first["id"], "saved", 3)
    add_job(workspace, "Collected while both runs are open")
    with acting_as(AGENT):
        finished = activity.finish_run(run["id"], {"expected_version": 1, **REPORT})
        workspace.set_triage(first["id"], "inbox", 4)
    changes = {
        (item["payload"].get("to"), item["actor"]["label"]): item["run_id"]
        for item in events(workspace, kind="triage_changed")
    }
    assert changes == {
        ("saved", "Synthetic agent"): None,  # before the run
        ("dismissed", "Second synthetic agent"): other["id"],
        ("dismissed", "Synthetic agent"): run["id"],
        ("saved", "Owner (dashboard)"): None,
        ("inbox", "Synthetic agent"): None,  # after the run
    }
    assert all(item["run_id"] is None for item in events(workspace, kind="job_added"))
    assert finished["report"]["changes"] == {
        "text": REPORT["changes"],
        "counts": {"triage_changed": 1},
        "total": 1,
    }
    assert [item["id"] for item in finished["changes"]["items"]] == [
        item["id"] for item in events(workspace, run_id=run["id"])
    ]
    assert activity.get_run(other["id"])["change_counts"] == {"triage_changed": 1}


def test_one_open_run_per_token_and_explicit_supersede(services):
    workspace, activity = services
    job = add_job(workspace)
    with acting_as(AGENT):
        first = activity.start_run({"workflow": "review-inbox", "idempotency_key": "run-1"})
        assert (
            activity.start_run({"workflow": "review-inbox", "idempotency_key": "run-1"})["id"]
            == (first["id"])
        )
        workspace.set_triage(job["id"], "saved", job["version"])
        with pytest.raises(DomainError) as refused:
            activity.start_run({"workflow": "prepare-shortlist"})
        assert (refused.value.status, refused.value.code) == (409, "run_open")
        assert refused.value.details["run"]["id"] == first["id"]
        assert refused.value.details["run"]["workflow"] == "review-inbox"
        second = activity.start_run({"workflow": "prepare-shortlist", "supersede": True})
        assert second["superseded_run_id"] == first["id"]
        with pytest.raises(DomainError) as closed:
            activity.finish_run(first["id"], {"expected_version": 2, **REPORT})
        assert closed.value.code == "run_closed"
    old = activity.get_run(first["id"])
    assert (old["status"], old["interruption"], old["superseded_by"]) == (
        "interrupted",
        "superseded",
        second["id"],
    )
    assert old["change_counts"] == {"triage_changed": 1} and old["report"] is None
    with acting_as(OTHER):
        assert activity.start_run({"workflow": "review-inbox"})["status"] == "open"
        with pytest.raises(DomainError) as foreign:
            activity.update_run(second["id"], {"expected_version": 1, "note": "Not mine"})
        assert foreign.value.code == "run_owner"
    with acting_as(OWNER), pytest.raises(DomainError) as session:
        activity.start_run({"workflow": "review-inbox"})
    assert (session.value.status, session.value.code) == (403, "run_actor")
    # SQLite enforces the rule as well.
    with pytest.raises(sqlite3.IntegrityError), workspace.db.transaction() as conn:
        conn.execute(
            "INSERT INTO runs(id,token_id,token_name,workflow,started_at,last_activity_at,updated_at) VALUES('x',?,?,?,?,?,?)",
            (AGENT.id, AGENT.name, "duplicate", "2026-01-01", "2026-01-01", "2026-01-01"),
        )


def test_progress_notes_and_reports_use_versions(services):
    _, activity = services
    with acting_as(AGENT):
        run = activity.start_run({"workflow": "review-inbox", "scope": "Synthetic"})
        noted = activity.update_run(run["id"], {"expected_version": 1, "note": "Halfway"})
        assert (noted["note"], noted["version"], noted["scope"]) == ("Halfway", 2, "Synthetic")
        with pytest.raises(DomainError) as stale:
            activity.finish_run(run["id"], {"expected_version": 1, **REPORT})
        assert stale.value.details == {"current_version": 2}
        finished = activity.finish_run(run["id"], {"expected_version": 2, **REPORT})
    assert (finished["status"], finished["version"]) == ("finished", 3)
    assert finished["ended_at"] and finished["summary"] == REPORT["summary"]
    report = finished["report"]
    assert report["not_done"] == [
        {**REPORT["not_done"][0], "subject_type": None, "subject_id": None, "label": ""}
    ]
    assert report["checks"] == [
        {"check": "Final Inbox query returned zero jobs.", "verified": True},
        {"check": "PDF render", "verified": False},
    ]
    assert (report["limits"], report["method"]) == (REPORT["limits"], REPORT["method"])


def test_a_run_without_activity_is_reported_interrupted_but_never_closed(services):
    workspace, activity = services
    job = add_job(workspace)
    with acting_as(AGENT):
        run = activity.start_run({"workflow": "review-inbox"})
        workspace.set_triage(job["id"], "saved", job["version"])
    assert activity.list_runs({"status": "open"})["total"] == 1
    workspace.db.execute("UPDATE runs SET last_activity_at='2026-01-01T00:00:00.000000+00:00'")
    stale = activity.get_run(run["id"])
    assert (stale["status"], stale["interruption"]) == ("interrupted", "no_activity")
    assert stale["ended_at"] is None and stale["change_counts"] == {"triage_changed": 1}
    assert stale["changes"]["total"] == 1
    assert activity.list_runs({"status": "open"})["total"] == 0
    assert [item["id"] for item in activity.list_runs({"status": "interrupted"})["items"]] == [
        run["id"]
    ]
    assert workspace.db.one("SELECT status FROM runs")["status"] == "open"
    with acting_as(AGENT):
        # The token still has this run: a new start names it, a new write revives it.
        with pytest.raises(DomainError) as refused:
            activity.start_run({"workflow": "review-inbox"})
        assert refused.value.details["run"]["status"] == "interrupted"
        workspace.set_triage(job["id"], "dismissed", 2)
        assert activity.get_run(run["id"])["status"] == "open"
        assert activity.finish_run(run["id"], {"expected_version": 1, **REPORT})["status"] == (
            "finished"
        )


def test_runs_list_filters_by_status_workflow_and_time(services):
    _, activity = services
    with acting_as(AGENT):
        first = activity.start_run({"workflow": "review-inbox"})
        activity.finish_run(first["id"], {"expected_version": 1, "summary": "Done."})
        second = activity.start_run({"workflow": "manage-sources"})
    listed = activity.list_runs({})
    assert [item["id"] for item in listed["items"]] == [second["id"], first["id"]]
    assert "report" not in listed["items"][0] and listed["items"][1]["summary"] == "Done."
    assert activity.list_runs({"status": "finished"})["items"][0]["id"] == first["id"]
    assert activity.list_runs({"workflow": "manage-sources"})["total"] == 1
    assert activity.list_runs({"token_id": OTHER.id})["total"] == 0
    assert activity.list_runs({"started_since": second["started_at"]})["total"] == 1
    assert activity.list_runs({"started_until": first["started_at"]})["total"] == 1


def test_runs_list_finds_runs_active_since_a_time(services):
    workspace, activity = services
    job = add_job(workspace)
    with acting_as(AGENT):
        old = activity.start_run({"workflow": "review-inbox"})
        activity.finish_run(old["id"], {"expected_version": 1, "summary": "Done."})
    with acting_as(OTHER):
        long = activity.start_run({"workflow": "prepare-shortlist"})
    # Both started long ago; only the second changed something afterwards.
    workspace.db.execute(
        "UPDATE runs SET started_at='2026-01-01T00:00:00.000000+00:00',"
        "last_activity_at='2026-01-01T00:10:00.000000+00:00'"
    )
    with acting_as(OTHER):
        workspace.set_triage(job["id"], "saved", job["version"])
    since = "2026-01-02T00:00:00Z"
    assert [item["id"] for item in activity.list_runs({"active_since": since})["items"]] == [
        long["id"]
    ]
    assert activity.list_runs({"started_since": since})["total"] == 0
    assert activity.list_runs({"active_since": "2026-01-01"})["total"] == 2
    with pytest.raises(ValueError, match="ISO8601"):
        activity.list_runs({"active_since": "yesterday"})


def test_changes_filter_by_several_kinds_of_record_and_name_their_run(services):
    workspace, activity = services
    job = add_job(workspace)
    with acting_as(AGENT):
        run = activity.start_run({"workflow": "review-inbox"})
        workspace.add_note(job["id"], {"body": "Synthetic note."})
        asked = activity.ask_question({"question": "Synthetic question?"})
    with acting_as(OWNER):
        workspace.set_triage(job["id"], "saved", job["version"])
    kinds = lambda **filters: sorted(item["kind"] for item in events(workspace, **filters))
    assert kinds(subject_types=["note", "question"]) == ["note_added", "question_asked"]
    assert kinds(subject_types=["job"]) == ["job_added", "triage_changed"]
    assert kinds(subject_types=["template"]) == []
    # An event from before schema 8 has no stored subject: it belongs to its job.
    workspace.db.execute(
        "UPDATE events SET subject_type=NULL,subject_id=NULL WHERE kind='job_added'"
    )
    assert kinds(subject_types=["job"]) == ["job_added", "triage_changed"]
    assert kinds(subject_types=["application"]) == []
    with pytest.raises(ValueError):
        activity.list_events({"subject_types": [""]})
    # Changes, questions and requests name the workflow of their run.
    by_kind = {item["kind"]: item for item in events(workspace)}
    assert by_kind["note_added"]["run_workflow"] == "review-inbox"
    assert by_kind["triage_changed"]["run_workflow"] is None
    assert activity.get_question(asked["id"])["run_workflow"] == "review-inbox"
    assert activity.get_run(run["id"])["questions"][0]["run_workflow"] == "review-inbox"


def test_question_lifecycle_versions_and_answers_since(services):
    workspace, activity = services
    job = add_job(workspace)
    with acting_as(AGENT):
        run = activity.start_run({"workflow": "review-inbox"})
        asked = activity.ask_question(
            {
                "question": "Is relocation to Zurich acceptable?",
                "why": "The role is on site.",
                "subject_type": "job",
                "subject_id": job["id"],
                "choices": ["Yes", "No"],
                "idempotency_key": "relocation",
            }
        )
        again = activity.ask_question(
            {"question": "Is relocation to Zurich acceptable?", "idempotency_key": "relocation"}
        )
        general = activity.ask_question({"question": "Which notice period applies?"})
        with pytest.raises(DomainError) as other_key:
            activity.ask_question({"question": "Another question", "idempotency_key": "relocation"})
        with pytest.raises(DomainError, match="Job was not found"):
            activity.ask_question(
                {"question": "Unknown?", "subject_type": "job", "subject_id": "none"}
            )
    assert again["id"] == asked["id"] and other_key.value.status == 409
    assert (asked["state"], asked["version"], asked["run_id"]) == ("open", 1, run["id"])
    assert asked["asked_by"]["label"] == "Synthetic agent" and asked["answered_by"] is None
    assert asked["subject"] == {
        "type": "job",
        "id": job["id"],
        "label": "Synthetic engineer · Example",
        "deleted": False,
        "job_id": job["id"],
    }
    assert general["subject"] is None
    assert activity.list_questions({"state": "open"})["total"] == 2
    assert activity.list_questions({"subject_type": "job", "subject_id": job["id"]})["total"] == 1
    assert activity.list_questions({"run_id": run["id"]})["total"] == 2
    assert activity.list_questions({"answered_since": "2000-01-01"})["total"] == 0

    with acting_as(OWNER):
        with pytest.raises(DomainError) as invalid:
            activity.answer_question(asked["id"], {"expected_version": 1, "choice": "Maybe"})
        assert invalid.value.code == "answer_choice"
        with pytest.raises(DomainError) as empty:
            activity.answer_question(asked["id"], {"expected_version": 1})
        assert empty.value.code == "answer_required"
        answered = activity.answer_question(
            asked["id"], {"expected_version": 1, "choice": "Yes", "answer": "Within a year."}
        )
        with pytest.raises(DomainError) as stale:
            activity.answer_question(asked["id"], {"expected_version": 1, "choice": "No"})
        assert stale.value.details == {"current_version": 2}
    assert (answered["state"], answered["answer_choice"], answered["answer"]) == (
        "answered",
        "Yes",
        "Within a year.",
    )
    assert answered["answered_by"]["kind"] == "owner" and answered["answered_at"]
    assert answered["version"] == 2 and answered["withdrawn_at"] is None

    since = activity.list_questions({"answered_since": answered["answered_at"]})
    assert [item["id"] for item in since["items"]] == [asked["id"]]
    with acting_as(OWNER):
        corrected = activity.answer_question(asked["id"], {"expected_version": 2, "choice": "No"})
    # A corrected answer is newer than the first one, so the next run sees it again.
    assert corrected["answered_at"] > answered["answered_at"]
    assert activity.list_questions({"answered_since": corrected["answered_at"]})["total"] == 1

    with acting_as(AGENT):
        with pytest.raises(DomainError) as closed:
            activity.withdraw_question(asked["id"], {"expected_version": 3})
        assert closed.value.code == "question_closed"
        withdrawn = activity.withdraw_question(general["id"], {"expected_version": 1})
    assert withdrawn["state"] == "withdrawn" and withdrawn["withdrawn_by"]["kind"] == "token"
    with acting_as(OWNER), pytest.raises(DomainError) as late:
        activity.answer_question(general["id"], {"expected_version": 2, "answer": "Three months"})
    assert late.value.code == "question_withdrawn"
    # Asking and answering appear in the job's history with their actors.
    history = events(workspace, job_id=job["id"])
    assert [(item["kind"], item["actor"]["kind"]) for item in history][:3] == [
        ("question_answered", "owner"),
        ("question_answered", "owner"),
        ("question_asked", "token"),
    ]
    assert activity.get_run(run["id"])["questions_count"] == 2


def test_questions_outlive_their_subject_with_a_label(tmp_path):
    workspace = Workspace(tmp_path / "subjects.sqlite")
    career, activity = CareerService(workspace), ActivityService(workspace)
    job, duplicate = add_job(workspace), add_job(workspace, "Synthetic engineer copy")
    application = workspace.create_application({"job_id": job["id"]})
    entry = career.create_knowledge(KnowledgeCreate(title="Synthetic role", organization="Labs"))
    with acting_as(AGENT):
        on_job = activity.ask_question(
            {"question": "Job?", "subject_type": "job", "subject_id": duplicate["id"]}
        )
        on_application = activity.ask_question(
            {"question": "Attempt?", "subject_type": "application", "subject_id": application["id"]}
        )
        on_entry = activity.ask_question(
            {"question": "Entry?", "subject_type": "knowledge", "subject_id": entry["id"]}
        )
    assert on_application["subject"]["job_id"] == job["id"]
    # A merge keeps the question on the surviving job.
    job = workspace.get_job(job["id"])
    workspace.merge_jobs(duplicate["id"], job["id"], duplicate["version"], job["version"])
    merged = activity.get_question(on_job["id"])["subject"]
    assert (merged["id"], merged["label"]) == (job["id"], "Synthetic engineer · Example")
    # Deleting the subject keeps the question, its state and the name it had.
    career.delete_knowledge(entry["id"], entry["version"])
    workspace.forget_job(job["id"], workspace.get_job(job["id"])["version"])
    labels = {
        on_job["id"]: "Synthetic engineer copy · Example",
        on_application["id"]: "Synthetic engineer · Example",
        on_entry["id"]: "Synthetic role · Labs",
    }
    for identifier, label in labels.items():
        question = activity.get_question(identifier)
        assert question["state"] == "open"
        assert (question["subject"]["id"], question["subject"]["deleted"]) == (None, True)
        assert question["subject"]["label"] == label
    assert activity.list_questions({"state": "open"})["total"] == 3
    with acting_as(OWNER):
        assert (
            activity.answer_question(
                on_job["id"], {"expected_version": 1, "answer": "Still valid"}
            )["state"]
            == "answered"
        )


def schema_seven_workspace(path):
    workspace = Workspace(path)
    job = add_job(workspace)
    application = workspace.create_application({"job_id": job["id"], "note": "Synthetic guidance"})
    workspace.update_application(
        application["id"], {"expected_version": application["version"], "status": "applied"}
    )
    note = workspace.add_note(job["id"], {"body": "Synthetic note"})
    make_schema_seven(path)
    return job, application, note


def test_schema_seven_upgrade_preserves_rows_and_matches_a_new_workspace(tmp_path):
    path = tmp_path / "schema7.sqlite"
    job, application, note = schema_seven_workspace(path)
    preserved = ("jobs", "applications", "events", "notes", "postings", "settings")
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
        assert not {"runs", "questions"} & table_names(conn)
        assert "actor_kind" not in {row[0] for row in columns(conn, "events")}
        before = {table: older_rows(conn, table) for table in preserved}
    assert len(before["events"]) >= 4

    upgraded = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with sqlite3.connect(path) as conn, sqlite3.connect(fresh.path) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert table_names(conn) == table_names(reference)
        assert index_names(conn) == index_names(reference)
        for table in table_names(reference) - {"jobs_fts"}:
            if table.startswith("jobs_fts"):
                continue
            assert sorted(columns(conn, table)) == sorted(columns(reference, table)), table
        for table, rows in before.items():
            added = (
                SCHEMA_EIGHT_COLUMNS.get(table, ())
                + SCHEMA_ELEVEN_COLUMNS.get(table, ())
                + SCHEMA_TWELVE_COLUMNS.get(table, ())
            )
            assert older_rows(conn, table, added) == rows, table
    # The application note is its pinned note, by an unknown author before 0.17.
    pinned = upgraded.get_application(application["id"])["pinned_note"]
    assert (pinned["body"], pinned["origin"]) == ("Synthetic guidance", "upgrade")
    assert pinned["author"]["label"] == UNKNOWN_LABEL
    # Earlier changes have no recorded actor and say so; they are never guessed.
    history = upgraded.application_events(application["id"])["items"]
    assert len(history) == 2
    assert {item["actor"]["label"] for item in history} == {UNKNOWN_LABEL}
    assert history[0]["actor"] == {
        "kind": "unknown",
        "id": None,
        "name": None,
        "token_kind": None,
        "label": "unknown (before 0.17)",
    }
    assert history[0]["subject"] == {"type": "application", "id": application["id"]}
    assert history[0]["run_id"] is None
    assert upgraded.get_note(note["id"])["author"]["kind"] == "unknown"
    assert ActivityService(upgraded).list_events({"actor": "unknown"})["total"] == len(
        before["events"]
    )
    # New changes are attributed straight away.
    with acting_as(AGENT):
        ActivityService(upgraded).start_run({"workflow": "track-applications"})
        upgraded.add_note(job["id"], {"body": "After the upgrade"})
    newest = upgraded.db.one("SELECT * FROM events ORDER BY created_at DESC LIMIT 1")
    assert newest["actor_name"] == "Synthetic agent" and newest["run_id"]


def test_failed_schema_eight_upgrade_rolls_back(tmp_path):
    path = tmp_path / "partial.sqlite"
    schema_seven_workspace(path)
    with sqlite3.connect(path) as conn:
        # A conflicting column makes a later migration statement fail.
        conn.execute("ALTER TABLE notes ADD COLUMN author_id TEXT")
    with pytest.raises(sqlite3.OperationalError):
        Workspace(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
        assert not {"runs", "questions"} & table_names(conn)
        assert "actor_kind" not in {row[0] for row in columns(conn, "events")}


def test_restore_upgrades_a_schema_seven_backup_without_changing_it(tmp_path):
    source = tmp_path / "backup.sqlite"
    job, application, note = schema_seven_workspace(source)
    original = source.read_bytes()
    with sqlite3.connect(source) as conn:
        count = conn.execute("SELECT count(*) FROM events").fetchone()[0]
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    app = create_app(tmp_path / "live.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic agent")
    with TestClient(app) as client:
        restored = client.post(
            "/api/v1/backup/restore",
            content=original,
            headers={**bearer(token), "Content-Type": "application/vnd.sqlite3"},
        )
        assert restored.status_code == 200, restored.text
        history = client.get("/api/v1/events", headers=bearer(token)).json()
    assert source.read_bytes() == original
    target = app.state.workspace
    with target.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert target.get_application(application["id"])["note"] == "Synthetic guidance"
    assert target.get_note(note["id"])["body"] == "Synthetic note"
    # The backup's own history is intact and unattributed; the restore itself is recorded.
    assert history["total"] == count + 1
    assert history["items"][0]["kind"] == "workspace_restored"
    assert history["items"][0]["actor"]["label"] == "Synthetic agent"
    assert {item["actor"]["kind"] for item in history["items"][1:]} == {"unknown"}
    # Runs and questions work on the restored workspace.
    with acting_as(token_actor(token["id"], token["name"])):
        assert app.state.activity.start_run({"workflow": "review-inbox"})["status"] == "open"
    direct = Workspace(tmp_path / "direct.sqlite")
    restore_database(direct, source)
    assert direct.get_job(job["id"])["title"] == "Synthetic engineer"


def test_rest_and_mcp_expose_the_same_runs_questions_and_changes(app):
    workspace = app.state.workspace
    token = app.state.auth.create_token("Synthetic agent")
    job = add_job(workspace)
    owner = owner_client(app)
    with TestClient(app, base_url="http://localhost:8080") as rest:
        headers = bearer(token)
        # Open over MCP, write over REST, ask over MCP, answer in the owner session.
        run, error = tool(
            rest, token, "runs_start", {"value": {"workflow": "review-inbox", "scope": "Inbox"}}
        )
        assert error is None and run["status"] == "open"
        conflict = rest.post("/api/v1/runs", json={"workflow": "review-inbox"}, headers=headers)
        _, mcp_conflict = tool(rest, token, "runs_start", {"value": {"workflow": "review-inbox"}})
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == mcp_conflict["code"] == "run_open"
        assert conflict.json()["error"]["details"]["run"]["id"] == run["id"]
        assert mcp_conflict["details"]["run"]["id"] == run["id"]
        saved = rest.post(
            f"/api/v1/jobs/{job['id']}/triage",
            json={"triage": "saved", "expected_version": job["version"]},
            headers=headers,
        )
        assert saved.status_code == 200
        question, error = tool(
            rest,
            token,
            "questions_ask",
            {
                "value": {
                    "question": "Is a hybrid role acceptable?",
                    "why": "Two office days are required.",
                    "subject_type": "job",
                    "subject_id": job["id"],
                    "choices": ["Yes", "No"],
                }
            },
        )
        assert error is None and question["run_id"] == run["id"]
        assert owner.post("/api/v1/runs", json={"workflow": "x"}).json()["error"]["code"] == (
            "run_actor"
        )
        stale = owner.post(
            f"/api/v1/questions/{question['id']}/answer",
            json={"expected_version": 9, "choice": "Yes"},
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["details"] == {"current_version": 1}
        answered = owner.post(
            f"/api/v1/questions/{question['id']}/answer",
            json={"expected_version": 1, "choice": "Yes"},
        ).json()
        assert answered["answered_by"]["label"] == "Owner (dashboard)"
        # The agent reads the answer given since its run started, over MCP.
        answers, error = tool(
            rest, token, "questions_list", {"value": {"answered_since": run["started_at"]}}
        )
        assert error is None
        assert [(item["id"], item["answer_choice"]) for item in answers["items"]] == [
            (question["id"], "Yes")
        ]
        noted = rest.patch(
            f"/api/v1/runs/{run['id']}",
            json={"expected_version": run["version"], "note": "One job saved"},
            headers=headers,
        ).json()
        finished, error = tool(
            rest,
            token,
            "runs_finish",
            {"run_id": run["id"], "value": {"expected_version": noted["version"], **REPORT}},
        )
        assert error is None
        assert finished["report"]["changes"]["counts"] == {
            "question_asked": 1,
            "triage_changed": 1,
        }
        # Every read returns the same record over REST and MCP.
        for path, name, arguments in (
            (f"/api/v1/runs/{run['id']}", "runs_get", {"run_id": run["id"]}),
            ("/api/v1/runs", "runs_list", {}),
            ("/api/v1/runs?status=finished", "runs_list", {"value": {"status": "finished"}}),
            (
                f"/api/v1/questions/{question['id']}",
                "questions_get",
                {"question_id": question["id"]},
            ),
            (
                "/api/v1/questions?state=answered",
                "questions_list",
                {"value": {"state": "answered"}},
            ),
            (
                f"/api/v1/events?run_id={run['id']}",
                "events_list",
                {"value": {"run_id": run["id"]}},
            ),
            (
                "/api/v1/events?subject_types=question&subject_types=job",
                "events_list",
                {"value": {"subject_types": ["question", "job"]}},
            ),
            (
                "/api/v1/runs?active_since=2026-01-01",
                "runs_list",
                {"value": {"active_since": "2026-01-01"}},
            ),
            (
                f"/api/v1/applications/{'missing'}/events",
                "applications_history",
                {"application_id": "missing"},
            ),
        ):
            over_rest = rest.get(path, headers=headers)
            over_mcp, error = tool(rest, token, name, arguments)
            if error:
                assert over_rest.json()["error"]["code"] == error["code"]
            else:
                assert over_rest.status_code == 200 and over_rest.json() == over_mcp, path
        detail = rest.get(f"/api/v1/runs/{run['id']}", headers=headers).json()
    assert detail["actor"]["label"] == "Synthetic agent"
    assert [item["kind"] for item in detail["changes"]["items"]] == [
        "question_asked",
        "triage_changed",
    ]
    assert detail["changes"]["items"][1]["subject"]["label"] == "Synthetic engineer · Example"
    assert [item["id"] for item in detail["questions"]] == [question["id"]]
    assert detail["questions"][0]["state"] == "answered"
    # The owner's answer is not part of the agent's run.
    assert events(workspace, kind="question_answered")[0]["run_id"] is None
