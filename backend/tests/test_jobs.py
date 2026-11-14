"""Jobs: triage and list filters before totals, identities across URLs, and merges."""

import pytest

from openings.common import now
from openings.errors import DomainError
from openings.models import JobQuery


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


def add(workspace, title):
    return job(workspace, title=title, url="https://example.test/jobs/" + title.replace(" ", "-"))


def test_rest_triage_filters_before_totals_and_pagination(app, client):
    ws = app.state.workspace
    for title in ["C role", "A role", "B role"]:
        job = add(ws, title)
        if title != "B role":
            ws.set_triage(job["id"], "shortlisted", job["version"])
    result = client.get("/api/v1/jobs?triage=shortlisted&sort=title&limit=1&offset=1").json()
    assert result["total"] == 2 and result["items"][0]["title"] == "C role"
    assert client.get("/api/v1/jobs?queue=shortlist").status_code == 422
    job = result["items"][0]
    stale = client.post(
        "/api/v1/jobs/bulk",
        json={
            "action": "dismissed",
            "items": [{"id": job["id"], "expected_version": job["version"] + 1}],
        },
    ).json()
    assert stale["failed"] == 1
    assert client.get("/api/v1/jobs?triage=shortlisted").json()["total"] == 2


def test_completeness_and_active_filters_match_page_totals(app, client):
    workspace = app.state.workspace
    complete = job(workspace)
    incomplete = job(workspace, url="https://jobs.lever.co/example/missing-text", posting="   ")
    preview = job(
        workspace,
        url="https://jobs.lever.co/example/preview",
        posting="Python, SQL, cloud",
        metadata={"description_complete": False},
    )
    placeholder = job(workspace, url="https://jobs.lever.co/example/placeholder", posting=" — - … ")
    short = job(workspace, url="https://jobs.lever.co/example/short", posting="Build APIs.")
    non_latin = job(
        workspace, url="https://jobs.lever.co/example/non-latin", posting="開発者を募集"
    )
    missing_ids = {incomplete["id"], preview["id"], placeholder["id"]}
    missing = client.get("/api/v1/jobs?complete=false&limit=1").json()
    assert missing["total"] == 3
    assert missing["items"][0]["id"] in missing_ids
    assert not missing["items"][0]["complete"]
    assert client.get("/api/v1/jobs?complete=false&offset=3").json()["items"] == []
    present = client.get("/api/v1/jobs?complete=true").json()
    assert present["total"] == 3
    assert {row["id"] for row in present["items"]} == {complete["id"], short["id"], non_latin["id"]}
    for item in (complete, incomplete, preview, placeholder, short, non_latin):
        assert client.get(f"/api/v1/jobs/{item['id']}").json()["complete"] == (
            item["id"] not in missing_ids
        )
    assert client.get("/api/v1/jobs?complete=invalid").status_code == 422

    # Active means not dismissed; it matches the attention counts.
    workspace.set_triage(incomplete["id"], "shortlisted", incomplete["version"])
    workspace.set_triage(preview["id"], "dismissed", preview["version"])
    result = client.get("/api/v1/jobs?triage=active&complete=false").json()
    assert result["total"] == 2
    assert {row["triage"] for row in result["items"]} == {"new", "shortlisted"}
    assert client.get("/api/v1/jobs?triage=dismissed&complete=false").json()["total"] == 1


def test_list_filters_previews_and_a_stale_bulk_change(app, client):
    workspace = app.state.workspace
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
    assert client.get("/api/v1/jobs?created_since=not-a-date").status_code == 422
    result = workspace.bulk_jobs(
        {
            "action": "shortlisted",
            "items": [
                {"id": first["id"], "expected_version": 1},
                {"id": other["id"], "expected_version": 1},
            ],
        }
    )
    assert result["succeeded"] == result["failed"] == 1
    assert result["items"][1]["error"]["status"] == 409


def test_source_identity_keeps_dismissal_across_url_changes_and_detects_conflicts(workspace):
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


def test_merge_cancels_old_work(workspace):
    source = job(workspace)
    target = job(workspace, url="https://jobs.lever.co/example/duplicate")
    workspace.db.execute(
        "INSERT INTO tasks(id,kind,job_id,state,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        ("old-work", "collect", source["id"], "running", now(), now(), now()),
    )
    merged = workspace.merge_jobs(source["id"], target["id"], source["version"], target["version"])
    assert merged["id"] == target["id"]
    assert workspace.db.one("SELECT state FROM tasks WHERE id='old-work'")["state"] == "cancelled"
