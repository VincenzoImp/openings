"""Exact identities, concurrent review and current workspace format boundaries."""

import sqlite3

import pytest

from openings.db import Database
from openings.documents import DocumentCreate, UploadReservation
from openings.errors import DomainError
from openings.operations import restore_database
from openings.workspace import Workspace


def test_source_identity_keeps_dismissal_across_url_changes_and_detects_conflicts(tmp_path):
    workspace = Workspace(tmp_path / "identity.sqlite")
    value = {"title": "Engineer", "posting": "Build APIs", "source_key": "rss:stable-guid"}
    first = workspace.ingest_job({**value, "url": "https://example.org/old"})
    dismissed = workspace.set_triage(first["id"], "dismissed", first["version"])
    refreshed = workspace.ingest_job({**value, "url": "https://example.org/new"})
    assert refreshed["id"] == first["id"] and refreshed["triage"] == "dismissed"
    assert workspace.db.one("SELECT count(*) n FROM postings")["n"] == 1
    assert workspace.ingest_job({"url": "https://example.org/old"})["id"] == first["id"]
    other = workspace.ingest_job({"url": "https://example.org/other"})
    with pytest.raises(DomainError) as error:
        workspace.ingest_job({**value, "url": "https://example.org/other"})
    assert error.value.code == "identity_conflict"
    assert set(error.value.details["job_ids"]) == {first["id"], other["id"]}
    workspace.merge_jobs(
        other["id"], first["id"], other["version"], workspace.get_job(first["id"])["version"]
    )
    merged = workspace.ingest_job({**value, "url": "https://example.org/other"})
    assert merged["id"] == first["id"] and merged["triage"] == dismissed["triage"]
    workspace.forget_job(first["id"], workspace.get_job(first["id"])["version"])
    assert not workspace.db.all("SELECT * FROM job_identities")
    assert workspace.ingest_job(value)["id"] != first["id"]


def test_unsupported_formats_are_rejected_without_modifying_the_database(tmp_path):
    target = Workspace(tmp_path / "current.sqlite")
    job = target.ingest_job({"posting": "Build APIs"})
    for version in (1, 4):
        archive = tmp_path / f"unsupported-{version}.sqlite"
        with sqlite3.connect(archive) as connection:
            connection.execute(f"PRAGMA user_version={version}")
            connection.execute("CREATE TABLE marker(value TEXT)")
            connection.execute("INSERT INTO marker VALUES('preserve')")
        original = archive.read_bytes()
        with pytest.raises(DomainError, match="older than 0.23"):
            Database(archive)
        with pytest.raises(DomainError) as error:
            restore_database(target, archive)
        assert error.value.code == "backup_version"
        assert archive.read_bytes() == original
        assert target.get_job(job["id"])["posting"] == "Build APIs"


def test_parallel_upload_grants_remain_valid_until_a_revision_is_complete(app, client):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"posting": "Build APIs"})
    application = workspace.create_application({"job_id": job["id"]})
    doc = documents.create_document(DocumentCreate(application_id=application["id"], kind="other"))
    grants = [
        documents.reserve_upload(
            UploadReservation(owner_type="document", owner_id=doc["id"], name=name, size=3)
        )
        for name in ("cv.tex", "cv.txt", "late.txt")
    ]
    for grant in grants[:2]:
        assert client.put(grant["url"], headers=grant["headers"], content=b"abc").status_code == 200
    current = documents.get_document(doc["id"])
    assert current["version"] == 3 and len(current["files"]) == 2
    # The identical completed transfer is a retry, not another mutation.
    assert (
        client.put(grants[0]["url"], headers=grants[0]["headers"], content=b"abc").status_code
        == 200
    )
    assert documents.get_document(doc["id"])["version"] == 3
    # A file of another kind of revision may still be added.
    assert (
        client.put(grants[2]["url"], headers=grants[2]["headers"], content=b"abc").status_code
        == 200
    )
    assert len(documents.get_document(doc["id"])["files"]) == 3
    # A CV is complete once its PDF is stored: a grant reserved before is refused.
    cv = documents.create_document(
        DocumentCreate(
            application_id=application["id"], kind="cv", pdf={"name": "cv.pdf", "size": 8}
        )
    )
    late = documents.reserve_upload(
        UploadReservation(owner_type="document", owner_id=cv["id"], name="photo.png", size=3)
    )
    pdf = cv["uploads"]["pdf"]
    assert client.put(pdf["url"], headers=pdf["headers"], content=b"%PDF-1.4").status_code == 200
    assert documents.get_document(cv["id"])["complete"]
    refused = client.put(late["url"], headers=late["headers"], content=b"abc")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "revision_complete"
    assert len(documents.get_document(cv["id"])["files"]) == 1
