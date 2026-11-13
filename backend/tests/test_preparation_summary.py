"""Application summaries describe exact current revisions across interfaces."""

import pytest
from fastapi.testclient import TestClient

from document_fixtures import attach
from openings.app import create_app
from openings.documents import DocumentCreate
from openings.errors import DomainError


def test_preparation_counts_current_revisions_and_complete_ones(tmp_path):
    app = create_app(tmp_path / "preparation.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    first = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="cv",
            title="CV",
        )
    )
    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]

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
            )
        )
        # The new revision is current and incomplete; its parent's PDF does not count.
        assert current() == [{"kind": "cv", "revisions": 1, "complete": 0}]
        assert workspace.get_application(application["id"])["status"] == "shortlisted"
        documents.delete_document(second["id"], second["version"])
        assert current()[0]["complete"] == 1


def test_question_edits_retain_compatible_answers_and_reject_invalid_changes_atomically(tmp_path):
    app = create_app(tmp_path / "answers.sqlite", start_worker=False)
    workspace = app.state.workspace
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
