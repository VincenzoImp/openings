"""Ready is computed: required documents x complete revisions x blocking requirements x stage.

The truth table builds every combination in one workspace and checks that the
application read, the list, the ``ready`` pseudo-stage, the ``needs=documents``
filter and the stage counts all agree with the rule.
"""

import itertools
import json
import sqlite3

import pytest

from document_fixtures import PDF, pdf_revision, source_revision
from openings.common import new_id, now
from openings.db import encode

KINDS = ("cv", "letter")
REQUIRED = ([], ["cv"], ["letter"], ["cv", "letter"])
# The state of each kind's current revision: none, incomplete (no PDF), complete,
# or a complete revision replaced by an incomplete one.
STATES = ("none", "incomplete", "complete", "replaced")
BLOCKING = ("none", "open", "resolved")
STAGES = ("shortlisted", "applied")


def expected(required, states, blocking, stage):
    missing = [kind for kind in required if states[kind] != "complete"]
    if blocking == "open":
        missing.append("requirement:r1")
    return stage == "shortlisted" and not missing, missing


def insert_revision(conn, application_id, kind, complete, previous_id=None):
    document_id = new_id()
    conn.execute(
        "INSERT INTO documents(id,application_id,kind,previous_id,created_at) VALUES(?,?,?,?,?)",
        (document_id, application_id, kind, previous_id, now()),
    )
    if complete:
        conn.execute(
            "INSERT INTO files(id,sha256,name,media_type,size,document_id,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (new_id(), "pdf", f"{kind}.pdf", "application/pdf", len(PDF), document_id, now()),
        )
    return document_id


def seed(conn, required, states, blocking, stage):
    job_id, application_id, stamp = new_id(), new_id(), now()
    conn.execute(
        "INSERT INTO jobs(id,title,company,triage,created_at,updated_at) "
        "VALUES(?,'Synthetic','Example','shortlisted',?,?)",
        (job_id, stamp, stamp),
    )
    requirements = []
    if blocking != "none":
        requirements = [
            {"id": "r1", "text": "Synthetic", "blocking": True, "resolved": blocking == "resolved"}
        ]
    conn.execute(
        "INSERT INTO applications(id,job_id,status,applied_at,requirements,required_documents,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            application_id,
            job_id,
            stage,
            None if stage == "shortlisted" else stamp,
            encode(requirements),
            encode(required),
            stamp,
            stamp,
        ),
    )
    for kind in KINDS:
        state = states[kind]
        if state == "none":
            continue
        first = insert_revision(conn, application_id, kind, state != "incomplete")
        if state == "replaced":
            insert_revision(conn, application_id, kind, False, previous_id=first)
    return application_id


def test_ready_truth_table(workspace):
    with workspace.db.transaction() as conn:
        conn.execute("INSERT INTO blobs(sha256,content,size) VALUES('pdf',?,?)", (PDF, len(PDF)))
    cases = {}
    with workspace.db.transaction() as conn:
        for required, cv, letter, blocking, stage in itertools.product(
            REQUIRED, STATES, STATES, BLOCKING, STAGES
        ):
            states = {"cv": cv, "letter": letter}
            identifier = seed(conn, required, states, blocking, stage)
            cases[identifier] = expected(required, states, blocking, stage)
    # The read of one application uses the same rule as the list.
    for identifier in list(cases)[::17]:
        read = workspace.get_application(identifier)
        assert (read["ready"], read["missing"]) == cases[identifier]
    listed = {}
    for offset in range(0, len(cases), 200):
        page = workspace.list_applications(limit=200, offset=offset)
        listed.update({item["id"]: (item["ready"], item["missing"]) for item in page["items"]})
    assert listed == cases
    ready = {identifier for identifier, (flag, _) in cases.items() if flag}
    page = workspace.list_applications(stage="ready", limit=200)
    assert {item["id"] for item in page["items"]} == ready and page["total"] == len(ready)
    assert page["stage_counts"]["ready"] == len(ready)
    shortlisted = {
        item["id"]
        for offset in range(0, len(cases), 200)
        for item in workspace.list_applications(stage="shortlisted", limit=200, offset=offset)[
            "items"
        ]
    }
    needs = {
        identifier
        for identifier, (_, missing) in cases.items()
        if any(not item.startswith("requirement:") for item in missing)
        and identifier in shortlisted
    }
    page = workspace.list_applications(needs="documents", limit=200)
    assert {item["id"] for item in page["items"]} == needs and page["total"] == len(needs)


@pytest.fixture
def put(app):
    from fastapi.testclient import TestClient

    # No lifespan: an application starts its MCP session manager only once.
    return TestClient(app).put


def start(app, **fields):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": "Synthetic", "company": "Example", "posting": "x"})
    return workspace.create_application({"job_id": job["id"], **fields})


def test_ready_follows_uploads_new_revisions_and_required_documents(app, put):
    workspace, documents = app.state.workspace, app.state.documents
    application = start(app)
    cv = pdf_revision(documents, put, application["id"], "cv")
    read = workspace.get_application(application["id"])
    assert (read["ready"], read["missing"]) == (False, ["letter"])
    letter = source_revision(documents, put, application["id"], "letter")
    assert workspace.get_application(application["id"])["ready"] is True
    # A new revision is incomplete until its PDF is stored: it never counts.
    documents.create_document(
        {
            "application_id": application["id"],
            "kind": "letter",
            "previous_id": letter["id"],
            "pdf": {"name": "letter.pdf", "size": len(PDF)},
        }
    )
    read = workspace.get_application(application["id"])
    assert (read["ready"], read["missing"]) == (False, ["letter"])
    # Requiring only the CV makes it Ready again; the change is stored canonically.
    read = workspace.update_application(
        application["id"],
        {"expected_version": read["version"], "required_documents": ["cv", "cv"]},
    )
    assert read["required_documents"] == ["cv"] and read["ready"] is True
    stored = workspace.db.one(
        "SELECT required_documents FROM applications WHERE id=?", (application["id"],)
    )
    assert json.loads(stored["required_documents"]) == ["cv"]
    # Mark applied leaves Ready; its undo returns to it.
    applied = workspace.update_application(
        application["id"], {"expected_version": read["version"], "status": "applied"}
    )
    assert applied["ready"] is False and applied["missing"] == []
    undone = workspace.update_application(
        application["id"], {"expected_version": applied["version"], "status": "shortlisted"}
    )
    assert undone["ready"] is True
    # Deleting the complete CV removes Ready.
    documents.delete_document(cv["id"], documents.get_document(cv["id"])["version"])
    assert workspace.get_application(application["id"])["missing"] == ["cv"]


def test_nothing_about_ready_is_stored(workspace):
    columns = {row["name"] for row in workspace.db.all("PRAGMA table_info(applications)")}
    assert not {name for name in columns if name.startswith("ready")}
    assert "review_state" not in {
        row["name"] for row in workspace.db.all("PRAGMA table_info(documents)")
    }
    job = workspace.ingest_job({"title": "T", "company": "C", "posting": "x"})
    with (
        pytest.raises(sqlite3.IntegrityError, match="CHECK"),
        workspace.db.transaction() as conn,
    ):
        conn.execute(
            "INSERT INTO applications(id,job_id,required_documents,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (new_id(), job["id"], encode(["answers"]), now(), now()),
        )
