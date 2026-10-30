import hashlib
import json
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


@pytest.mark.asyncio
async def test_completeness_filter_matches_overview_and_page_totals_on_rest_and_mcp(tmp_path):
    app = create_app(tmp_path / "complete.sqlite", start_worker=False)
    complete = job(app.state.workspace)
    incomplete = job(
        app.state.workspace,
        url="https://jobs.lever.co/example/missing-text",
        posting="   ",
    )
    preview = job(
        app.state.workspace,
        url="https://jobs.lever.co/example/preview",
        posting="Python, SQL, cloud",
        metadata={"description_complete": False},
    )
    placeholder = job(
        app.state.workspace, url="https://jobs.lever.co/example/placeholder", posting=" — - … "
    )
    short = job(
        app.state.workspace, url="https://jobs.lever.co/example/short", posting="Build APIs."
    )
    non_latin = job(
        app.state.workspace, url="https://jobs.lever.co/example/non-latin", posting="開発者を募集"
    )
    missing_ids = {incomplete["id"], preview["id"], placeholder["id"]}
    with TestClient(app) as client:
        client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        overview = client.get("/api/v1/overview").json()
        missing = client.get("/api/v1/jobs?complete=false&limit=1").json()
        assert missing["total"] == overview["incomplete"] == 3
        assert missing["items"][0]["id"] in missing_ids
        assert not missing["items"][0]["complete"]
        assert client.get("/api/v1/jobs?complete=false&offset=3").json()["items"] == []
        present = client.get("/api/v1/jobs?complete=true").json()
        assert present["total"] == 3
        assert {row["id"] for row in present["items"]} == {
            complete["id"], short["id"], non_latin["id"]
        }
        for item in (complete, incomplete, preview, placeholder, short, non_latin):
            assert client.get(f"/api/v1/jobs/{item['id']}").json()["complete"] == (
                item["id"] not in missing_ids
            )
        assert client.get("/api/v1/jobs?complete=invalid").status_code == 422
    result = await app.state.mcp.call_tool("jobs_search", {"value": {"complete": False}})
    structured = json.loads(result[0].text)
    assert structured["total"] == 3
    assert {row["id"] for row in structured["items"]} == missing_ids


@pytest.mark.asyncio
async def test_active_job_filter_matches_attention_counts_without_dismissed_jobs(tmp_path):
    app = create_app(tmp_path / "active.sqlite", start_worker=False)
    workspace = app.state.workspace
    for state in ("inbox", "saved", "dismissed"):
        item = job(workspace, url=f"https://example.test/{state}", posting="")
        if state != "inbox":
            workspace.set_triage(item["id"], state, item["version"])
    with TestClient(app) as client:
        client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        result = client.get("/api/v1/jobs?triage=active&complete=false").json()
        assert result["total"] == client.get("/api/v1/overview").json()["incomplete"] == 2
        assert {row["triage"] for row in result["items"]} == {"inbox", "saved"}
        assert client.get("/api/v1/jobs?triage=dismissed&complete=false").json()["total"] == 1
    result = await app.state.mcp.call_tool(
        "jobs_search", {"value": {"triage": "active", "complete": False}}
    )
    assert json.loads(result[0].text)["total"] == 2


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
    workspace.update_application(
        second["id"], {"expected_version": second["version"], "status": "offer"}
    )
    assert workspace.overview()["sent"] == 2
    assert workspace.overview()["offers"] == 1
    other = job(workspace, url="https://jobs.lever.co/example/different-role")
    with pytest.raises(DomainError):
        workspace.create_application({"job_id": other["id"], "idempotency_key": "once"})


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


def test_merge_preserves_scores_as_outdated_and_cancels_old_work(workspace):
    source = job(workspace)
    target = job(workspace, url="https://jobs.lever.co/example/duplicate")
    workspace.db.execute(
        "INSERT INTO assessments(id,job_id,signature,profile_version,job_version,config_version,score,model,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        ("old-score", source["id"], "source-signature", 0, 2, 0, 80, "synthetic", now()),
    )
    workspace.db.execute(
        "INSERT INTO tasks(id,kind,job_id,state,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        ("old-work", "score", source["id"], "running", now(), now(), now()),
    )
    merged = workspace.merge_jobs(source["id"], target["id"], source["version"], target["version"])
    assert merged["score"] == 80 and merged["score_outdated"]
    assert workspace.db.one("SELECT state FROM tasks WHERE id='old-work'")["state"] == "cancelled"


def test_unrelated_database_is_rejected_without_modification(tmp_path):
    path = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE jobs (old_field TEXT)")
        conn.execute("INSERT INTO jobs VALUES ('retained')")
    with pytest.raises(DomainError):
        Workspace(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT old_field FROM jobs").fetchone()[0] == "retained"
        assert (
            conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 1
        )


def test_compact_filters_bulk_conflicts_and_attempt_delete(workspace):
    from openings.models import JobQuery

    first = job(
        workspace,
        posting="Detailed Python work. " * 2000,
        metadata={"source": "linkedin", "is_remote": True, "job_type": "fulltime"},
    )
    other = job(workspace, url="https://jobs.lever.co/example/second", company="Other")
    workspace.update_job(other["id"], {"expected_version": 1, "location": "London"})
    query = JobQuery(
        remote=True, source="linkedin", job_type="fulltime", created_since="2026-01-01"
    )
    page = workspace.list_jobs(**query.model_dump())
    assert page["total"] == 1 and page["items"][0]["complete"]
    assert "posting" not in page["items"][0] and len(page["items"][0]["posting_preview"]) == 240
    result = workspace.bulk_jobs(
        {
            "action": "saved",
            "items": [
                {"id": first["id"], "expected_version": 1},
                {"id": other["id"], "expected_version": 1},
            ],
        }
    )
    assert result["succeeded"] == result["failed"] == 1
    assert result["items"][1]["error"]["status"] == 409
    attempt = workspace.create_application({"job_id": first["id"]})
    retained = workspace.create_application({"job_id": first["id"]})
    note = workspace.add_note(first["id"], {"body": "Original", "application_id": retained["id"]})
    workspace.update_note(note["id"], {"expected_version": 1, "body": "Edited"})
    workspace.delete_application(attempt["id"], attempt["version"])
    assert workspace.get_application(retained["id"])
    assert workspace.get_note(note["id"])["body"] == "Edited"
    summary = workspace.list_applications(limit=1)
    assert summary["stage_counts"]["draft"] == 1 and "questions" not in summary["items"][0]


def test_http_validates_answers_dates_and_rotation_preserves_tokens(tmp_path):
    app = create_app(tmp_path / "validation.sqlite", start_worker=False)
    with TestClient(app) as client:
        owner = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = owner["csrf_token"]
        token = client.post("/api/v1/tokens", json={"name": "automation"}).json()
        created = client.post("/api/v1/jobs", json={"posting": "Role details"}).json()
        attempt = client.post(
            "/api/v1/applications",
            json={
                "job_id": created["id"],
                "questions": [{"id": "years", "label": "Years", "type": "number"}],
            },
        ).json()
        for patch in (
            {"questions": None},
            {"answers": None},
            {"answers": {"years": True}},
            {"applied_at": "yesterday"},
        ):
            assert (
                client.patch(
                    "/api/v1/applications/" + attempt["id"], json={"expected_version": 1, **patch}
                ).status_code
                == 422
            )
        assert (
            client.patch(
                "/api/v1/applications/" + attempt["id"],
                json={"expected_version": 1, "answers": {"years": 4}},
            ).status_code
            == 200
        )
        assert client.get("/api/v1/jobs?created_since=not-a-date").status_code == 422
        assert (
            client.post(
                "/api/v1/auth/password", json={"password": "replacement-password"}
            ).status_code
            == 200
        )
        assert client.get("/api/v1/jobs").status_code == 401
        client.headers["Authorization"] = "Bearer " + token["token"]
        assert client.get("/api/v1/capabilities").json()["version"] == "0.6.0"
        assert client.get("/api/v1/tokens").json()["items"][0]["last_used_at"]
        source = client.post(
            "/api/v1/sources",
            json={
                "name": "Synthetic API source",
                "kind": "adzuna",
                "config": {
                    "query": "engineer",
                    "app_id": "synthetic",
                    "app_key": "synthetic-secret",
                },
            },
        )
        assert source.status_code == 201
        exported = client.get("/api/v1/export").json()
        assert "providers" in exported
        assert all(isinstance(provider["policy"], dict) for provider in exported["providers"])
        assert exported["sources"][0]["config"]["query"] == "engineer"
        assert "synthetic-secret" not in str(exported)


@pytest.mark.asyncio
async def test_scoped_export_and_auth_mcp_are_available(tmp_path):
    app = create_app(tmp_path / "operations.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    names = {tool.name for tool in await app.state.mcp.list_tools()}
    assert {
        "tokens_list",
        "token_create",
        "token_revoke",
        "owner_password_update",
        "capabilities_get",
        "workspace_export",
        "jobs_bulk",
        "application_delete",
    } <= names
    grant = app.state.auth.operation_ticket("export")
    with TestClient(app) as client:
        response = client.get("/api/v1/export", headers={"X-Operational-Token": grant})
        assert response.status_code == 200
        assert "auth" not in response.json()["settings"]
        assert (
            client.get("/api/v1/backup", headers={"X-Operational-Token": grant}).status_code == 403
        )


@pytest.mark.asyncio
async def test_url_extraction_does_not_score_challenge_or_generic_html():
    from openings.fetching import complete_input
    from openings.models import JobInput

    class Source:
        def __init__(self, body):
            self.body = body

        def fetch_bytes(self, *args, **kwargs):
            return self.body

    value = JobInput(url="https://example.org/jobs/1")
    challenge = (
        b"<html><title>Verify you are human</title><p>" + b"Security page " * 50 + b"</p></html>"
    )
    result = await complete_input(value, Source(challenge))
    assert not result.posting and result.metadata["extraction"] == "needs_text"
    structured = b'<script type="application/ld+json">{"@graph":[{"@type":"JobPosting","title":"Engineer","hiringOrganization":{"name":"Synthetic"},"description":"<p>Build Python tools.</p>"}]}</script>'
    result = await complete_input(value, Source(structured))
    assert result.posting == "Build Python tools." and result.company == "Synthetic"


def test_restore_keeps_provider_requests_and_future_cooldown(workspace, tmp_path):
    import json
    from datetime import datetime, timedelta, timezone
    from openings.discovery import DiscoveryService
    from openings.operations import restore_database

    discovery = DiscoveryService(workspace)
    provider = discovery.providers.get("linkedin")
    workspace.db.backup(tmp_path / "before-requests.sqlite")
    deadline = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(
        timespec="microseconds"
    )
    workspace.db.execute(
        "UPDATE providers SET runtime=? WHERE id='linkedin'",
        (
            json.dumps(
                {
                    "events": [datetime.now(timezone.utc).timestamp()],
                    "cooldown_until": deadline,
                    "total_requests": 1,
                }
            ),
        ),
    )
    restore_database(workspace, tmp_path / "before-requests.sqlite")
    restored = discovery.providers.get("linkedin")
    assert restored["runtime"]["cooldown_until"] == deadline
    assert restored["runtime"]["requests_day"] == 1
    assert restored["policy"] == provider["policy"]
