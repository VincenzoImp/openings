"""Exact identities, concurrent review, persisted freshness and safe format upgrades."""

import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from openings.db import Database, encode
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
    workspace.forget_job(first["id"])
    assert not workspace.db.all("SELECT * FROM job_identities")
    assert workspace.ingest_job(value)["id"] != first["id"]


def v1_archive(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(
            Path(__file__).with_name("fixtures").joinpath("schema-v1.sql").read_text()
        )
        for job_id, url in [
            ("first", "https://example.org/old"),
            ("second", "https://example.org/new"),
        ]:
            conn.execute(
                "INSERT INTO jobs(id,title,company,url,posting,triage,created_at,updated_at) VALUES(?,?,?,?,?,'dismissed','2026-01-01','2026-01-01')",
                (job_id, "Engineer", "Example", url, "Build APIs"),
            )
            conn.execute(
                "INSERT INTO postings(id,job_id,identity,url,payload,content_hash,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,'hash','2026-01-01','2026-01-01')",
                (job_id, job_id, "url:" + url, url, encode({"source_key": "bamboohr:example:1"})),
            )
        conn.execute(
            "INSERT INTO applications(id,job_id,created_at,updated_at) VALUES('attempt','first','2026-01-01','2026-01-01')"
        )
        conn.execute(
            "INSERT INTO documents(id,application_id,kind,review_state,created_at) VALUES('cv','attempt','resume','approved','2026-01-01')"
        )
        data = b"%PDF-1.4 synthetic archive"
        sha = hashlib.sha256(data).hexdigest()
        conn.execute("INSERT INTO blobs VALUES(?,?,?)", (sha, data, len(data)))
        conn.execute(
            "INSERT INTO files(id,sha256,name,size,document_id,created_at) VALUES('pdf',?,'cv.pdf',?,'cv','2026-01-01')",
            (sha, len(data)),
        )
        conn.commit()


def old_records(path):
    with sqlite3.connect(path) as conn:
        return {
            table: conn.execute("SELECT * FROM " + table).fetchall()
            for table in ("jobs", "postings", "applications", "files", "blobs")
        }


def test_v1_upgrade_and_restore_preserve_history_bytes_and_ambiguous_identities(tmp_path):
    archive = tmp_path / "v1.sqlite"
    v1_archive(archive)
    original = old_records(archive)
    workspace = Workspace(archive)
    assert workspace.db.one("PRAGMA user_version")["user_version"] == 2
    assert old_records(archive) == original
    assert workspace.db.one("SELECT review_state,version FROM documents") == {
        "review_state": "approved",
        "version": 1,
    }
    assert workspace.db.one("PRAGMA quick_check")["quick_check"] == "ok"
    assert workspace.db.all("PRAGMA foreign_key_check") == []
    with pytest.raises(DomainError) as error:
        workspace.ingest_job(
            {"source_key": "bamboohr:example:1", "url": "https://example.org/third"}
        )
    assert error.value.code == "identity_conflict" and workspace.list_jobs()["total"] == 2
    workspace.merge_jobs("second", "first", 1, 1)
    assert (
        workspace.ingest_job(
            {"source_key": "bamboohr:example:1", "url": "https://example.org/third"}
        )["id"]
        == "first"
    )

    backup = tmp_path / "backup-v1.sqlite"
    v1_archive(backup)
    target = Workspace(tmp_path / "target.sqlite")
    target.set_settings("auth", {"secret": "installation", "password_hash": "preserved"})
    restore_database(target, backup)
    assert old_records(target.db.path) == original
    assert target.get_settings("auth")["data"]["secret"] == "installation"
    with sqlite3.connect(backup) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert Database(target.db.path).all("PRAGMA foreign_key_check") == []


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
