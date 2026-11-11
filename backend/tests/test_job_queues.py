"""Actionable queues use full application history across shared interfaces."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.errors import DomainError
from openings.workspace import Workspace
from schema_fixtures import make_schema_seven


def add(workspace, title):
    return workspace.ingest_job(
        {
            "title": title,
            "company": "Example",
            "posting": "Build APIs.",
            "url": "https://example.test/jobs/" + title.replace(" ", "-"),
        }
    )


def test_queues_follow_full_history_and_explicit_deletion(tmp_path):
    ws = Workspace(tmp_path / "queues.sqlite")
    job = add(ws, "Backend engineer")
    assert ws.list_jobs(queue="inbox")["total"] == ws.overview()["inbox"] == 1
    job = ws.set_triage(job["id"], "saved", job["version"])
    assert ws.list_jobs(queue="inbox")["total"] == 0
    assert ws.list_jobs(queue="shortlist")["total"] == 1
    first = ws.create_application({"job_id": job["id"], "idempotency_key": "first"})
    assert (
        ws.create_application({"job_id": job["id"], "idempotency_key": "first"})["id"]
        == first["id"]
    )
    with pytest.raises(DomainError) as duplicate:
        ws.create_application({"job_id": job["id"]})
    assert duplicate.value.status == 409
    for stage in ("draft", "applied", "interview", "offer", "closed"):
        first = ws.update_application(
            first["id"],
            {
                "expected_version": first["version"],
                "status": stage,
                **({"outcome": "rejected"} if stage == "closed" else {}),
            },
        )
        assert ws.list_jobs(queue="shortlist")["total"] == 0
        assert ws.list_jobs(queue="inbox")["total"] == 0
        assert ws.list_jobs(queue="applications")["total"] == 1
    job = ws.get_job(job["id"])
    dismissed = ws.set_triage(job["id"], "dismissed", job["version"])
    restored = ws.set_triage(job["id"], "saved", dismissed["version"])
    assert ws.list_jobs(queue="shortlist")["total"] == 0
    ws.ingest_job(
        {
            "title": "Backend engineer",
            "company": "Example",
            "posting": "Build APIs.",
            "url": job["url"],
        }
    )
    later = ws.create_application({"job_id": restored["id"]})
    ws.delete_application(later["id"], later["version"])
    assert ws.list_jobs(queue="shortlist")["total"] == 0  # Older submitted attempt remains.
    assert ws.get_application(first["id"])["applied_at"]
    pending = add(ws, "Platform engineer")
    draft = ws.create_application({"job_id": pending["id"]})
    with pytest.raises(DomainError):
        ws.delete_application(draft["id"], draft["version"] + 1)
    ws.delete_application(draft["id"], draft["version"])
    assert [j["id"] for j in ws.list_jobs(queue="shortlist")["items"]] == [pending["id"]]


@pytest.mark.asyncio
async def test_rest_mcp_queues_filter_before_totals_facets_and_pagination(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    ws = app.state.workspace
    for title in ["C role", "A role", "B role"]:
        job = add(ws, title)
        ws.set_triage(job["id"], "saved", job["version"])
        if title == "B role":
            ws.create_application({"job_id": job["id"]})
    with TestClient(app) as client:
        setup = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = setup["csrf_token"]
        result = client.get("/api/v1/jobs?queue=shortlist&sort=title&limit=1&offset=1").json()
        assert result["total"] == 2 and result["items"][0]["title"] == "C role"
        mcp = await app.state.mcp.call_tool(
            "jobs_search",
            {
                "value": {
                    "queue": "shortlist",
                    "sort": "title",
                    "limit": 1,
                    "offset": 1,
                }
            },
        )
        structured = json.loads(mcp.content[0].text)
        assert structured == result
        job = result["items"][0]
        stale = client.post(
            "/api/v1/jobs/bulk",
            json={
                "action": "dismissed",
                "items": [{"id": job["id"], "expected_version": job["version"] + 1}],
            },
        ).json()
        assert stale["failed"] == 1
        assert client.get("/api/v1/jobs?queue=shortlist").json()["total"] == 2
        assert client.get("/api/v1/scoring").status_code == 404
        assert (
            client.post(
                "/api/v1/jobs/bulk",
                json={
                    "action": "rescore",
                    "items": [{"id": job["id"], "expected_version": job["version"]}],
                },
            ).status_code
            == 422
        )
    tools = [tool.name for tool in await app.state.mcp.list_tools()]
    assert not any(name.startswith("scoring_") for name in tools)
    assert "score" not in result["items"][0]


def test_schema_five_upgrade_preserves_owned_records_and_versions(tmp_path):
    path = tmp_path / "upgrade.sqlite"
    ws = Workspace(path)
    job = add(ws, "Existing engineer")
    application = ws.create_application({"job_id": job["id"]})
    # Schema 5 also predates attribution, runs and questions (schema 8).
    make_schema_seven(path)
    with sqlite3.connect(path) as conn:
        # Schema 5 also predates the schema 7 application planning fields.
        conn.execute("DROP INDEX applications_deadline")
        for column in ("requirements", "deadline", "priority"):
            conn.execute(f"ALTER TABLE applications DROP COLUMN {column}")
        conn.execute("ALTER TABLE jobs ADD COLUMN initial_score_pending INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE TABLE assessments (id TEXT PRIMARY KEY, job_id TEXT, score REAL)")
        conn.execute("INSERT INTO assessments VALUES (?,?,?)", ("derived", job["id"], 75))
        conn.execute(
            "INSERT INTO settings VALUES ('scoring',?,1,'2026-01-01')",
            (json.dumps({"api_key": "synthetic"}),),
        )
        conn.execute("PRAGMA user_version=5")
    upgraded = Workspace(path)
    assert upgraded.get_job(job["id"])["version"] == ws.get_job(job["id"])["version"]
    assert upgraded.get_application(application["id"]) == application
    assert upgraded.list_jobs(queue="shortlist")["total"] == 0
    with upgraded.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 9
        assert not conn.execute(
            "SELECT name FROM sqlite_master WHERE name='assessments'"
        ).fetchall()
        assert "initial_score_pending" not in {
            row[1] for row in conn.execute("PRAGMA table_info(jobs)")
        }
        assert not conn.execute("SELECT key FROM settings WHERE key='scoring'").fetchall()
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
