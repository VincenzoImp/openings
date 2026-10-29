import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.common import now
from openings.errors import DomainError
from openings.workspace import Workspace


@pytest.fixture
def workspace(tmp_path):
    return Workspace(tmp_path / "workspace.sqlite")


def job(workspace, **updates):
    return workspace.ingest_job(
        {
            "url": "https://jobs.lever.co/example/abc-123",
            "title": "API engineer",
            "company": "Example",
            "posting": "Build Python APIs.",
            **updates,
        }
    )


def test_reingestion_preserves_disposition_and_user_corrections(workspace):
    original = job(workspace)
    corrected = workspace.update_job(
        original["id"], {"expected_version": 1, "title": "Corrected role"}
    )
    workspace.set_triage(original["id"], "dismissed", corrected["version"])
    again = job(workspace, title="Source title", source_key="lever:example:abc-123")
    assert again["id"] == original["id"]
    assert again["triage"] == "dismissed"
    assert again["title"] == "Corrected role"
    assert workspace.list_jobs()["total"] == 1


def test_source_timestamp_is_not_material_job_content(workspace):
    original = job(workspace, raw={"updated_at": "2026-01-01"})
    refreshed = job(workspace, raw={"updated_at": "2026-01-02"})
    assert refreshed["content_version"] == original["content_version"]
    assert refreshed["version"] == original["version"]


def test_stale_edit_is_rejected(workspace):
    original = job(workspace)
    workspace.update_job(original["id"], {"expected_version": 1, "title": "Changed"})
    with pytest.raises(DomainError) as error:
        workspace.update_job(original["id"], {"expected_version": 1, "title": "Lost edit"})
    assert error.value.status == 409


def test_attempts_and_recorded_funnel_are_separate_from_job_triage(workspace):
    original = job(workspace)
    first = workspace.create_application({"job_id": original["id"], "idempotency_key": "once"})
    assert (
        workspace.create_application({"job_id": original["id"], "idempotency_key": "once"})["id"]
        == first["id"]
    )
    assert workspace.overview()["sent"] == 0
    first = workspace.update_application(
        first["id"], {"expected_version": first["version"], "status": "applied"}
    )
    first = workspace.update_application(
        first["id"], {"expected_version": first["version"], "status": "interview"}
    )
    assert workspace.overview()["interviews"] == 1
    workspace.update_application(
        first["id"],
        {"expected_version": first["version"], "status": "closed", "outcome": "rejected"},
    )
    second = workspace.create_application({"job_id": original["id"]})
    assert second["id"] != first["id"]
    assert workspace.list_applications()["total"] == 2


def test_forget_cascades_owned_bytes_and_allows_fresh_acquisition(workspace):
    original = job(workspace)
    application = workspace.create_application({"job_id": original["id"]})
    workspace.add_note(original["id"], {"body": "Retained note"})
    pdf = b"%PDF-1.4 synthetic storage fixture"
    sha = hashlib.sha256(pdf).hexdigest()
    with workspace.db.transaction() as c:
        c.execute("INSERT INTO blobs VALUES(?,?,?)", (sha, pdf, len(pdf)))
        c.execute(
            "INSERT INTO files(id,sha256,name,size,job_id,created_at) VALUES(?,?,?,?,?,?)",
            ("f1", sha, "example.pdf", len(pdf), original["id"], now()),
        )
    workspace.forget_job(original["id"])
    assert workspace.db.one("SELECT count(*) n FROM applications")["n"] == 0
    assert workspace.db.one("SELECT count(*) n FROM files")["n"] == 0
    assert workspace.db.one("SELECT count(*) n FROM blobs")["n"] == 0
    assert job(workspace)["id"] != original["id"]
    assert not workspace.db.one("SELECT id FROM applications WHERE id=?", (application["id"],))


def test_online_backup_preserves_exact_files(workspace, tmp_path):
    original = job(workspace)
    value = b"synthetic file bytes"
    sha = hashlib.sha256(value).hexdigest()
    with workspace.db.transaction() as c:
        c.execute("INSERT INTO blobs VALUES(?,?,?)", (sha, value, len(value)))
        c.execute(
            "INSERT INTO files(id,sha256,name,size,job_id,created_at) VALUES(?,?,?,?,?,?)",
            ("f1", sha, "source.tex", len(value), original["id"], now()),
        )
    workspace.db.backup(tmp_path / "backup.sqlite")
    with sqlite3.connect(tmp_path / "backup.sqlite") as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT content FROM blobs").fetchone()[0] == value


def test_http_owner_csrf_and_revocable_tokens(tmp_path):
    app = create_app(tmp_path / "auth.sqlite", start_worker=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/jobs").status_code == 401
        setup = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        assert setup.status_code == 200
        assert client.post("/api/v1/jobs", json={"posting": "Text"}).status_code == 403
        client.headers["X-CSRF-Token"] = setup.json()["csrf_token"]
        token = client.post("/api/v1/tokens", json={"name": "test"}).json()
        client.delete("/api/v1/tokens/" + token["id"])
        client.cookies.clear()
        assert (
            client.get(
                "/api/v1/jobs", headers={"Authorization": "Bearer " + token["token"]}
            ).status_code
            == 401
        )
