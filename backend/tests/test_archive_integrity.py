"""Exact identities, concurrent review and current workspace format boundaries."""

import sqlite3

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from openings.db import Database
from openings.documents import DocumentCreate, DocumentService, UploadReservation, register_api
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


@pytest.mark.parametrize("version", [1, 4])
def test_unsupported_formats_are_rejected_without_modifying_the_database(tmp_path, version):
    archive = tmp_path / "unsupported.sqlite"
    with sqlite3.connect(archive) as connection:
        connection.execute(f"PRAGMA user_version={version}")
        connection.execute("CREATE TABLE marker(value TEXT)")
        connection.execute("INSERT INTO marker VALUES('preserve')")
    original = archive.read_bytes()
    with pytest.raises(DomainError, match="Unsupported workspace"):
        Database(archive)
    target = Workspace(tmp_path / "current.sqlite")
    job = target.ingest_job({"posting": "Build APIs"})
    with pytest.raises(DomainError) as error:
        restore_database(target, archive)
    assert error.value.code == "backup_version"
    assert archive.read_bytes() == original
    assert target.get_job(job["id"])["posting"] == "Build APIs"


def test_approval_checks_file_set_but_parallel_upload_grants_remain_valid(tmp_path):
    workspace = Workspace(tmp_path / "review.sqlite")
    documents = DocumentService(workspace)
    job = workspace.ingest_job({"posting": "Build APIs"})
    application = workspace.create_application({"job_id": job["id"]})
    doc = documents.create_document(DocumentCreate(application_id=application["id"]))
    api = FastAPI()

    @api.exception_handler(DomainError)
    async def failure(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=error.status)

    router = APIRouter(prefix="/api/v1")
    register_api(router, documents)
    api.include_router(router)
    grants = [
        documents.reserve_upload(
            UploadReservation(owner_type="document", owner_id=doc["id"], name=name, size=3)
        )
        for name in ("cv.tex", "cv.txt", "late.txt")
    ]
    with TestClient(api) as client:
        for grant in grants[:2]:
            assert (
                client.put(grant["url"], headers=grant["headers"], content=b"abc").status_code
                == 200
            )
        current = documents.get_document(doc["id"])
        assert current["version"] == 3 and len(current["files"]) == 2
        # The identical completed transfer is a retry, not another mutation.
        assert (
            client.put(grants[0]["url"], headers=grants[0]["headers"], content=b"abc").status_code
            == 200
        )
        assert documents.get_document(doc["id"])["version"] == 3
        path = f"/api/v1/documents/{doc['id']}/review"
        assert client.post(path, json={"expected_version": doc["version"]}).status_code == 409
        assert client.post(path, json={"expected_review_state": "draft"}).status_code == 422
        approved = client.post(path, json={"expected_version": current["version"]})
        assert approved.status_code == 200 and approved.json()["version"] == 4
        assert (
            client.put(grants[2]["url"], headers=grants[2]["headers"], content=b"abc").status_code
            == 409
        )
        assert len(documents.get_document(doc["id"])["files"]) == 2
