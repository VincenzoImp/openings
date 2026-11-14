"""Application intent, the one-application REST routes and versioned deletion.

Concurrent creation and the SQLite guard of one open application per job are in
test_shortlist.py.
"""

import pytest

from openings.errors import DomainError


def test_summaries_filtering_and_merge_preserve_application_intent(workspace):
    first = workspace.ingest_job({"title": "First", "posting": "Build APIs."})
    second = workspace.ingest_job({"title": "Second", "posting": "Operate infrastructure."})
    assert first["application"] is None and first["application_count"] == 0
    previous = workspace.create_application({"job_id": first["id"], "idempotency_key": "first"})
    previous = workspace.update_application(
        previous["id"],
        {"expected_version": previous["version"], "stage": "closed", "outcome": "rejected"},
    )
    current = workspace.create_application({"job_id": first["id"]})
    # A closed application cannot reopen while another one is open.
    with pytest.raises(DomainError) as reopening:
        workspace.update_application(
            previous["id"], {"expected_version": previous["version"], "stage": "shortlisted"}
        )
    assert reopening.value.code == "application_in_progress"
    assert reopening.value.details["application_id"] == current["id"]
    workspace.create_application({"job_id": second["id"]})
    expected = {key: current[key] for key in ("id", "stage", "outcome", "version")}
    summary = next(row for row in workspace.list_jobs()["items"] if row["id"] == first["id"])
    assert summary["application"] == workspace.get_job(first["id"])["application"] == expected
    assert summary["application_count"] == 2
    attempts = workspace.list_applications(job_id=first["id"], limit=1)
    assert attempts["total"] == 2 and len(attempts["items"]) == 1
    assert attempts["stage_counts"]["shortlisted"] == attempts["stage_counts"]["closed"] == 1
    assert attempts["items"][0]["job_id"] == first["id"]

    with pytest.raises(DomainError, match="Close one active application"):
        workspace.merge_jobs(
            first["id"],
            second["id"],
            workspace.get_job(first["id"])["version"],
            workspace.get_job(second["id"])["version"],
        )
    assert workspace.list_jobs()["total"] == 2
    workspace.delete_application(current["id"], current["version"])
    assert workspace.get_job(first["id"])["application"]["id"] == previous["id"]
    # Closing never changes the job's triage.
    assert workspace.get_job(first["id"])["triage"] == "shortlisted"
    workspace.set_triage(first["id"], "dismissed", workspace.get_job(first["id"])["version"])
    assert (
        workspace.create_application({"job_id": first["id"], "idempotency_key": "first"})["id"]
        == previous["id"]
    )
    # The key belongs to the first job's request; another job's is refused.
    with pytest.raises(DomainError):
        workspace.create_application({"job_id": second["id"], "idempotency_key": "first"})


def test_interface_workflow_requires_explicit_outcomes_and_versioned_deletion(client):
    """The one-application REST routes the dashboard uses (MCP: test_mcp_tools.py)."""

    def ok(response):
        assert response.is_success, response.text
        return response.json()

    def status(response):
        return response.status_code

    job = ok(
        client.post(
            "/api/v1/jobs", json={"title": "Engineer", "company": "Example", "posting": "Build."}
        )
    )

    def start(item):
        return ok(client.post("/api/v1/applications/batch", json={"items": [item]}))["items"][0]

    first = {"job_id": job["id"], "priority": 2, "idempotency_key": "start"}
    attempt = start(first)["result"]
    assert start(first)["id"] == attempt["id"]
    # The job's open application is returned, not doubled.
    assert start({"job_id": job["id"]})["result"]["created"] is False
    assert ok(client.get(f"/api/v1/applications/{attempt['id']}"))["priority"] == 2
    listed = ok(client.get("/api/v1/applications", params={"job_id": job["id"]}))
    assert listed["total"] == 1 and listed["stage_counts"]["shortlisted"] == 1

    path = f"/api/v1/applications/{attempt['id']}"

    def patch(**fields):
        return client.patch(path, json={"expected_version": attempt["version"], **fields})

    attempt = ok(patch(stage="applied"))
    assert attempt["applied_at"]
    attempt = ok(patch(applied_at=None))
    assert attempt["applied_at"] is None
    # Closing names its outcome.
    assert status(patch(stage="closed")) == 422
    attempt = ok(patch(stage="closed", outcome="rejected"))
    attempt = ok(patch(priority=1))
    assert attempt["outcome"] == "rejected"

    # Deletion is deliberate: it names the current version.
    assert status(client.delete(path)) == 422
    assert status(client.delete(path, params={"expected_version": attempt["version"] - 1})) == 409
    ok(client.delete(path, params={"expected_version": attempt["version"]}))
    retained = ok(client.get(f"/api/v1/jobs/{job['id']}"))
    # Deleting a job's last application returns it to New.
    assert retained["triage"] == "new" and retained["application_count"] == 0
    job_path = f"/api/v1/jobs/{job['id']}"
    assert status(client.delete(job_path)) == 422
    assert status(client.delete(job_path, params={"expected_version": job["version"]})) == 409
    ok(client.delete(job_path, params={"expected_version": retained["version"]}))
    assert ok(client.get("/api/v1/jobs"))["total"] == 0
