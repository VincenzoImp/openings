"""Application priority, deadline, requirements, questions and answers, and what is
missing for Ready."""

import json

import pytest

from document_fixtures import attach, attach_pdf
from openings.documents import DocumentCreate
from openings.errors import DomainError
from openings.workspace import Workspace


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
    events = workspace.db.all(
        "SELECT payload FROM events WHERE application_id=? ORDER BY created_at DESC",
        (application["id"],),
    )
    assert {"priority", "deadline"} <= set(json.loads(events[0]["payload"])["fields"])


def test_missing_documents_follow_current_revisions_and_sorts_by_plan(app, client):
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

    cv = documents.create_document(
        DocumentCreate(
            application_id=soon["id"], kind="cv", title="CV", pdf={"name": "cv.pdf", "size": 1}
        )
    )
    documents.create_document(
        DocumentCreate(
            application_id=soon["id"], kind="answers", title="Form", content={"text": "B"}
        )
    )
    assert missing(soon) == ["cv"]
    attach(documents, client.put, cv["id"], "A", pdf=False)
    assert missing(soon) == ["cv"]
    attach_pdf(documents, client.put, cv["id"], "A")
    # Form answers never affect Ready.
    assert missing(soon) == [] and ids(stage="ready") == [soon["id"]]
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
    assert ids(stage="ready") == [soon["id"]]
    assert set(ids(needs="documents")) == {late["id"], urgent["id"], loose["id"]}
    listed = next(
        item for item in workspace.list_applications()["items"] if item["id"] == late["id"]
    )
    assert listed["blocking_requirements"] == listed["open_requirements"] == 1
    assert "requirements" not in listed
    with pytest.raises(DomainError):
        workspace.list_applications(stage="maybe")


def test_applications_filter_by_the_time_they_were_applied(app, client):
    workspace = app.state.workspace

    def applied(title, when):
        job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build."})
        created = workspace.create_application({"job_id": job["id"]})
        fields = {"stage": "applied", "applied_at": when} if when else {}
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
    # A date without a time includes its whole day, as the other ranges do.
    rest = client.get("/api/v1/applications", params={"applied_until": "2026-09-01"})
    assert [item["id"] for item in rest.json()["items"]] == [old]
    invalid = client.get("/api/v1/applications", params={"applied_since": "soon"})
    assert invalid.status_code == 422


def test_preparation_counts_current_revisions_and_complete_ones(app, client):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    first = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="cv",
            title="CV",
            pdf={"name": "cv.pdf", "size": 1},
        )
    )

    def current():
        detail = workspace.get_application(application["id"])["preparation"]
        assert client.get("/api/v1/applications").json()["items"][0]["preparation"] == detail
        return detail

    assert current() == [{"kind": "cv", "revisions": 1, "complete": 0}]
    attach(documents, client.put, first["id"])
    assert current()[0]["complete"] == 1
    first = documents.get_document(first["id"])
    second = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="cv",
            title="Revised CV",
            previous_id=first["id"],
            pdf={"name": "cv.pdf", "size": 1},
        )
    )
    # The new revision is current and incomplete; its parent's PDF does not count.
    assert current() == [{"kind": "cv", "revisions": 1, "complete": 0}]
    assert workspace.get_application(application["id"])["stage"] == "shortlisted"
    documents.delete_document(second["id"], second["version"])
    assert current()[0]["complete"] == 1


def test_question_edits_retain_compatible_answers_and_reject_invalid_changes_atomically(
    workspace,
):
    job = workspace.ingest_job({"title": "Synthetic role", "posting": "Build reliable services."})
    questions = [
        {"id": "text", "label": "Motivation", "type": "text", "max_length": 30},
        {"id": "choice", "label": "Office", "type": "choice", "options": ["Remote", "Zurich"]},
        {"id": "boolean", "label": "Available", "type": "boolean"},
        {"id": "number", "label": "Years", "type": "number"},
    ]
    application = workspace.create_application({"job_id": job["id"], "questions": questions})
    answers = {"text": "Synthetic motivation", "choice": "Remote", "boolean": True, "number": 3}
    application = workspace.update_application(
        application["id"], {"expected_version": application["version"], "answers": answers}
    )
    questions[0].update(label="Why this role?", required=True, max_length=40)
    application = workspace.update_application(
        application["id"], {"expected_version": application["version"], "questions": questions}
    )
    assert application["answers"] == answers
    for changed in [
        {**questions[0], "max_length": 5},
        {**questions[1], "options": ["Zurich"]},
        {**questions[0], "type": "number"},
    ]:
        invalid = [
            changed if question["id"] == changed["id"] else question for question in questions
        ]
        with pytest.raises(DomainError):
            workspace.update_application(
                application["id"],
                {"expected_version": application["version"], "questions": invalid},
            )
        assert workspace.get_application(application["id"], compact_job=True) == application
    # Only an explicit answers patch can clear an incompatible live answer.
    questions[0]["max_length"] = 5
    kept = {key: value for key, value in answers.items() if key != "text"}
    application = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "questions": questions, "answers": kept},
    )
    assert application["answers"] == kept
    for invalid in (
        {"questions": None},
        {"answers": None},
        {"answers": {"number": True}},
        {"applied_at": "yesterday"},
    ):
        with pytest.raises((ValueError, DomainError)):
            workspace.update_application(
                application["id"], {"expected_version": application["version"], **invalid}
            )
