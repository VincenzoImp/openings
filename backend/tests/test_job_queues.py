"""Jobs by triage (New, Shortlisted, Dismissed) across shared interfaces."""

import pytest

from openings.errors import DomainError
from openings.workspace import Workspace


def add(workspace, title):
    return workspace.ingest_job(
        {
            "title": title,
            "company": "Example",
            "posting": "Build APIs.",
            "url": "https://example.test/jobs/" + title.replace(" ", "-"),
        }
    )


def test_triage_follows_the_application_and_explicit_deletion(tmp_path):
    ws = Workspace(tmp_path / "queues.sqlite")
    job = add(ws, "Backend engineer")
    assert ws.list_jobs(triage="new")["total"] == 1
    job = ws.set_triage(job["id"], "shortlisted", job["version"])
    assert ws.list_jobs(triage="new")["total"] == 0
    assert ws.list_jobs(triage="shortlisted")["total"] == 1
    first = ws.get_application(job["application"]["id"])
    with pytest.raises(DomainError) as duplicate:
        ws.create_application({"job_id": job["id"]})
    assert duplicate.value.status == 409
    for stage in ("applied", "interview", "offer", "closed"):
        first = ws.update_application(
            first["id"],
            {
                "expected_version": first["version"],
                "stage": stage,
                **({"outcome": "rejected"} if stage == "closed" else {}),
            },
        )
        # Closing an application never changes the job's triage.
        assert ws.list_jobs(triage="shortlisted")["total"] == 1
        assert ws.list_jobs(triage="new")["total"] == 0
    job = ws.get_job(job["id"])
    dismissed = ws.set_triage(job["id"], "dismissed", job["version"])
    assert dismissed["application"]["stage"] == "closed"
    restored = ws.set_triage(job["id"], "shortlisted", dismissed["version"])
    # Shortlisting a job whose applications are all closed starts a new one.
    later = restored["application"]
    assert later["stage"] == "shortlisted" and later["id"] != first["id"]
    ws.delete_application(later["id"], later["version"])
    assert ws.get_job(job["id"])["triage"] == "shortlisted"  # Older attempt remains.
    assert ws.get_application(first["id"])["applied_at"]
    pending = add(ws, "Platform engineer")
    started = ws.create_application({"job_id": pending["id"]})
    assert ws.get_job(pending["id"])["triage"] == "shortlisted"
    with pytest.raises(DomainError):
        ws.delete_application(started["id"], started["version"] + 1)
    ws.delete_application(started["id"], started["version"])
    # Deleting a job's only application returns it to New.
    assert [j["id"] for j in ws.list_jobs(triage="new")["items"]] == [pending["id"]]
    counts = ws.list_jobs(include_counts=True)["counts"]
    assert {key: counts[key] for key in ("all", "new", "shortlisted", "dismissed")} == {
        "all": 2,
        "new": 1,
        "shortlisted": 1,
        "dismissed": 0,
    }


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
