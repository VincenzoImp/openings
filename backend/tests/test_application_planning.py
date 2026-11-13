"""Application priority, deadline, employer requirements and readiness (schema 7)."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.db import SCHEMA_VERSION, Database
from openings.documents import DocumentCreate, ReviewUpdate, UploadReservation
from openings.errors import DomainError
from openings.operations import restore_database
from openings.workspace import Workspace
from outcome_fixtures import SCHEMA_ELEVEN_COLUMNS
from schema_fixtures import SCHEMA_EIGHT_COLUMNS, columns, make_schema_seven
from signal_fixtures import SCHEMA_TWELVE_COLUMNS
from timeline_fixtures import older_rows

SCHEMA_SEVEN_COLUMNS = ("requirements", "deadline", "priority")


def make_schema_six(path):
    """Turn a current workspace into the released schema 6 layout, keeping its rows."""
    make_schema_seven(path)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX applications_deadline")
        for column in SCHEMA_SEVEN_COLUMNS:
            conn.execute(f"ALTER TABLE applications DROP COLUMN {column}")
        conn.execute("PRAGMA user_version=6")


def seeded(path):
    workspace = Workspace(path)
    job = workspace.ingest_job(
        {"title": "Synthetic platform engineer", "company": "Example", "posting": "Run APIs."}
    )
    application = workspace.create_application(
        {
            "job_id": job["id"],
            "note": "Synthetic guidance",
            "questions": [{"id": "why", "label": "Why this role?"}],
        }
    )
    application = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "answers": {"why": "Synthetic answer."}},
    )
    return workspace, job, application


def test_schema_six_upgrade_preserves_records_and_matches_a_new_workspace(tmp_path):
    path = tmp_path / "schema6.sqlite"
    workspace, job, application = seeded(path)
    job = workspace.get_job(job["id"])
    make_schema_six(path)
    with sqlite3.connect(path) as conn:
        assert "priority" not in {row[0] for row in columns(conn, "applications")}
        before = {
            table: older_rows(conn, table) for table in ("jobs", "applications", "events", "notes")
        }

    upgraded = Workspace(path)
    current = upgraded.get_application(application["id"])
    assert current["version"] == application["version"]
    assert current["answers"] == {"why": "Synthetic answer."}
    assert (current["priority"], current["deadline"], current["requirements"]) == (None, None, [])
    assert current["readiness"] == "none"
    assert upgraded.get_job(job["id"])["version"] == job["version"]
    fresh = Database(tmp_path / "fresh.sqlite")
    with (
        sqlite3.connect(path) as conn,
        sqlite3.connect(fresh.path) as reference,
    ):
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert sorted(columns(conn, "applications")) == sorted(columns(reference, "applications"))
        index = "SELECT name FROM sqlite_master WHERE type='index' AND name='applications_deadline'"
        assert conn.execute(index).fetchone()
        for table, rows in before.items():
            added = (
                *SCHEMA_SEVEN_COLUMNS,
                *SCHEMA_EIGHT_COLUMNS.get(table, ()),
                *SCHEMA_ELEVEN_COLUMNS.get(table, ()),
                *SCHEMA_TWELVE_COLUMNS.get(table, ()),
            )
            assert older_rows(conn, table, added) == rows, table
    assert current["note"] == current["pinned_note"]["body"] == "Synthetic guidance"
    # The new fields are usable straight away.
    updated = upgraded.update_application(
        application["id"], {"expected_version": current["version"], "priority": 2}
    )
    assert updated["priority"] == 2 and updated["version"] == current["version"] + 1


def test_failed_upgrade_rolls_back_and_leaves_schema_six(tmp_path):
    path = tmp_path / "partial.sqlite"
    seeded(path)
    make_schema_six(path)
    with sqlite3.connect(path) as conn:
        # A conflicting column makes the second migration statement fail.
        conn.execute("ALTER TABLE applications ADD COLUMN deadline TEXT")
    with pytest.raises(sqlite3.OperationalError):
        Workspace(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        names = {row[0] for row in columns(conn, "applications")}
        assert "priority" not in names and "requirements" not in names


def test_restore_upgrades_a_schema_six_backup_without_changing_it(tmp_path):
    source = tmp_path / "backup.sqlite"
    _, _, application = seeded(source)
    make_schema_six(source)
    original = source.read_bytes()
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, source)
    assert source.read_bytes() == original
    restored = target.get_application(application["id"])
    assert restored["requirements"] == [] and restored["note"] == "Synthetic guidance"
    with target.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


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
    assert application["readiness"] == "blocked"
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
    assert application["readiness"] == "none" and application["blocking_requirements"] == 0
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


def test_readiness_follows_current_revisions_and_sorts_by_plan(tmp_path):
    app = create_app(tmp_path / "readiness.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents

    def start(title, **fields):
        job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build."})
        return workspace.create_application({"job_id": job["id"], **fields})

    def readiness(application):
        return workspace.get_application(application["id"])["readiness"]

    def ids(**query):
        return [item["id"] for item in workspace.list_applications(**query)["items"]]

    late = start("Late", deadline="2027-03-01", priority=3)
    soon = start("Soon", deadline="2026-12-01")
    urgent = start("Urgent", deadline="2027-03-01", priority=1)
    loose = start("Loose")
    assert ids(sort="deadline") == [soon["id"], urgent["id"], late["id"], loose["id"]]
    assert ids(sort="priority") == [urgent["id"], late["id"], soon["id"], loose["id"]]

    cv = documents.create_document(
        DocumentCreate(application_id=soon["id"], kind="resume", title="CV", content={"text": "A"})
    )
    answers = documents.create_document(
        DocumentCreate(
            application_id=soon["id"], kind="answers", title="Form", content={"text": "B"}
        )
    )
    assert readiness(soon) == "missing_pdf"
    pdf = b"%PDF-1.4\nSynthetic test PDF"
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=cv["id"],
            name="cv.pdf",
            size=len(pdf),
            media_type="application/pdf",
        )
    )
    with TestClient(app) as client:
        assert client.put(grant["url"], headers=grant["headers"], content=pdf).status_code == 200
    assert readiness(soon) == "unreviewed"
    for document in (cv, answers):
        current = documents.get_document(document["id"])
        documents.review_document(document["id"], ReviewUpdate(expected_version=current["version"]))
    # Every check passes; Ready itself is the stored step (test_application_ready.py).
    assert readiness(soon) == "reviewed"
    assert ids(readiness="reviewed") == [soon["id"]] and ids(readiness="ready") == []
    # A new revision replaces the approved leaf; its parent's PDF does not count.
    documents.create_document(
        DocumentCreate(
            application_id=soon["id"],
            kind="resume",
            title="CV v2",
            previous_id=cv["id"],
            content={"text": "Changed"},
        )
    )
    assert readiness(soon) == "missing_pdf"
    workspace.update_application(
        late["id"],
        {
            "expected_version": late["version"],
            "requirements": [{"kind": "eligibility", "text": "Work permit", "blocking": True}],
        },
    )
    assert ids(readiness="missing_pdf") == [soon["id"]]
    assert ids(readiness="blocked") == [late["id"]]
    assert set(ids(readiness="none")) == {urgent["id"], loose["id"]}
    assert ids(readiness="ready") == []
    listed = workspace.list_applications(readiness="blocked")["items"][0]
    assert listed["blocking_requirements"] == listed["open_requirements"] == 1
    assert "requirements" not in listed
    with pytest.raises(DomainError):
        workspace.list_applications(readiness="maybe")


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
            created["id"], {"expected_version": created["version"], "note": title, **fields}
        )["id"]

    old = applied("Old", "2026-09-01T09:00:00Z")
    recent = applied("Recent", "2026-11-01T09:00:00Z")
    applied("Preparing", None)

    def ids(**query):
        return [item["id"] for item in workspace.list_applications(**query)["items"]]

    assert ids(status="applied", applied_until="2026-10-12T00:00:00+00:00") == [old]
    assert ids(applied_since="2026-10-12T00:00:00+00:00") == [recent]
    # An application never recorded as applied has no time to compare.
    assert set(ids(applied_until="2027-01-01T00:00:00+00:00")) == {old, recent}
    waiting = workspace.list_applications(status="applied", applied_until="2026-10-12", limit=1)
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
            "application_create",
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
        assert status == 200 and created["readiness"] == "blocked"
        status, updated = call(
            "application_update",
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
        assert status == 200 and updated["readiness"] == "none" and updated["deadline"] is None
        status, _ = call(
            "application_update",
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
            {"value": {"readiness": "none", "sort": "priority"}},
        )
        assert status == 200 and listed["total"] == 1
        item = listed["items"][0]
        assert (item["priority"], item["deadline"], item["readiness"]) == (2, None, "none")
        assert item["open_requirements"] == item["blocking_requirements"] == 0
        status, got = call(
            "application_get",
            "GET",
            f"/applications/{created['id']}",
            {"application_id": created["id"]},
        )
        assert status == 200 and got["requirements"] == updated["requirements"]
