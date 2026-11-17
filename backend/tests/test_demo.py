"""The demo workspace: seeded from the package, dated back only in a file the demo created,
and served by `openings demo` from a temporary file with a closed provider gate."""

import re
import sys
import tempfile
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from openings import __main__ as cli
from openings.auth import COOKIE
from openings.demo import NotADemo, is_demo, mark_demo, seed_demo, stamp
from openings.demo.postings import COMPANIES, FICTIONAL_DOMAINS

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
URL = re.compile(r"https?://([^/\s\"'\\)<>{}]+)")


def test_the_demo_fills_every_stage_with_fictional_names_only(app):
    seed_demo(app)
    workspace = app.state.workspace
    db = workspace.db
    jobs = db.all("SELECT company,triage FROM jobs")
    assert 40 <= len(jobs) <= 60
    assert sum(job["triage"] == "new" for job in jobs) >= 25
    applications = workspace.list_applications(limit=1)
    stages = applications["stage_counts"]
    assert stages["ready"] >= 3 and stages["shortlisted"] > stages["ready"]
    assert all(stages[stage] for stage in ("applied", "interview", "offer", "closed"))
    assert applications["no_reply"]["overdue"]
    # The agent's dismissal names its reason.
    reasons = [
        row["reason"]
        for row in db.all(
            "SELECT json_extract(payload,'$.reason') AS reason FROM events "
            "WHERE kind='triage_changed' AND actor='agent:Claude Code'"
        )
    ]
    assert "Requires fluent German; you speak English and Italian." in reasons
    # Ready: priorities 1 to 3, deadlines, the agent's CV and letter, a salary basis.
    ready = workspace.list_applications(stage="ready", limit=50)["items"]
    assert {item["priority"] for item in ready} >= {1, 2, 3}
    assert all(item["deadline"] for item in ready)
    for item in ready:
        authors = db.all(
            "SELECT d.kind,e.actor FROM documents d JOIN events e ON e.subject_id=d.id "
            "AND e.kind='document_created' WHERE d.application_id=?",
            (item["id"],),
        )
        assert {(row["kind"], row["actor"]) for row in authors} >= {
            ("cv", "agent:Claude Code"),
            ("letter", "agent:Claude Code"),
        }
        notes = db.all("SELECT body FROM notes WHERE application_id=?", (item["id"],))
        assert any(note["body"].startswith(("Salary basis:", "Salary range:")) for note in notes)
    # Only invented companies and reserved example domains.
    assert {job["company"] for job in jobs} <= COMPANIES
    with db.connect() as conn:
        dump = "\n".join(conn.iterdump())
    hosts = {host.split(":")[0].lower() for host in URL.findall(dump)}
    assert hosts and all(
        any(host == domain or host.endswith("." + domain) for domain in FICTIONAL_DOMAINS)
        for host in hosts
    ), hosts


def test_openings_demo_serves_a_temporary_workspace_and_removes_it(tmp_path, monkeypatch, capsys):
    real = tmp_path / "data" / "openings.sqlite"
    monkeypatch.setenv("OPENINGS_DATABASE", str(real))
    monkeypatch.delenv("OPENINGS_PUBLIC_URL", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["openings", "demo", "--port", "8080"])
    served = {}

    def run(app, **options):
        served["files"] = sorted(path.name for path in tmp_path.glob("openings-demo-*/*"))
        notice = capsys.readouterr().out
        served["notice"] = notice
        link = re.search(r"http://127\.0\.0\.1:8080(/api/v1/auth/demo\?ticket=\S+)", notice)[1]
        token = re.search(r"export OPENINGS_TOKEN=(\S+)", notice)[1]
        bearer = {"Authorization": "Bearer " + token}
        with TestClient(app, base_url="http://127.0.0.1:8080") as client:
            assert client.get("/health").json()["demo"] is True
            assert client.get("/api/v1/auth/session").json()["authenticated"] is False
            signed = client.get(link, follow_redirects=False)
            assert signed.status_code == 303 and signed.headers["location"] == "/"
            assert COOKIE in signed.cookies
            session = client.get("/api/v1/auth/session").json()
            assert session["authenticated"] and session["demo"] is True
            client.cookies.clear()
            again = client.get(link, follow_redirects=False)
            assert again.status_code == 401 and again.json()["error"]["code"] == "link_used"
            # The printed agent token works over MCP.
            initialize = {"protocolVersion": "2025-06-18", "capabilities": {}}
            initialize["clientInfo"] = {"name": "synthetic", "version": "1"}
            for method, params in (("initialize", initialize), ("tools/list", {})):
                response = client.post(
                    "/mcp/",
                    headers={**MCP_HEADERS, **bearer},
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                )
                assert response.status_code == 200, response.text
            assert 44 <= len(response.json()["result"]["tools"]) <= 45
            context = client.get("/api/v1/workspace/context", headers=bearer).json()
            assert context["workspace"]["demo"] is True and context["counts"]["jobs"]
            assert client.get("/api/v1/workspace", headers=bearer).json()["demo"] is True

    monkeypatch.setattr(cli.uvicorn, "run", run)
    cli.main()
    assert "demo.sqlite" in served["files"]
    assert (
        "claude mcp add --transport http openings http://127.0.0.1:8080/mcp/ " in served["notice"]
    )
    assert "--header 'Authorization: Bearer ${OPENINGS_TOKEN}'" in served["notice"]
    assert "Mapped another port? Replace 8080." in served["notice"]
    # The temporary workspace is gone, and $OPENINGS_DATABASE was never opened.
    assert not list(tmp_path.glob("openings-demo-*"))
    assert not real.exists() and not real.parent.exists()


def test_the_sign_in_link_exists_only_in_a_demo(client):
    response = client.get("/api/v1/auth/demo?ticket=synthetic", follow_redirects=False)
    assert response.status_code == 404
    assert client.get("/api/v1/auth/session").json()["demo"] is False
    assert "demo" not in client.get("/api/v1/workspace/context").json()["workspace"]


def test_dates_are_rewritten_only_in_a_file_with_the_demo_marker(workspace):
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    before = workspace.get_job(job["id"])["created_at"]
    with pytest.raises(NotADemo):
        stamp(workspace.db, "", datetime.now(UTC) - timedelta(days=30))
    assert workspace.get_job(job["id"])["created_at"] == before
    # A workspace with records never becomes a demo, so it can never be stamped.
    with pytest.raises(NotADemo):
        mark_demo(workspace)
    assert not is_demo(workspace.db)


def test_the_demo_seeds_a_new_workspace_with_dates_relative_to_now(app):
    token = seed_demo(app)
    workspace = app.state.workspace
    assert is_demo(workspace.db) and token["name"] == "Claude Code" and token["token"]
    oldest = workspace.db.one("SELECT min(created_at) AS at FROM jobs")["at"]
    age = datetime.now(UTC) - datetime.fromisoformat(oldest)
    assert timedelta(days=30) < age < timedelta(days=90)
    # Every CV and letter is a complete revision built from its stored TeX source.
    pdfs = workspace.db.all(
        "SELECT source_sha256 FROM files WHERE media_type='application/pdf' "
        "AND document_id IS NOT NULL"
    )
    assert pdfs and all(row["source_sha256"] for row in pdfs)
    # Each template has one sample PDF for its Preview.
    templates = app.state.career.list_templates()["items"]
    assert {template["name"] for template in templates} == {"Main CV", "Cover letter", "Compact CV"}
    for template in templates:
        files = app.state.documents.list_files(owner_type="template", owner_id=template["id"])
        assert [file["media_type"] for file in files["items"]] == ["application/pdf"]
