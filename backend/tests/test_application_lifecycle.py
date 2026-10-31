"""Application intent, shared interface contracts and destructive ownership."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.errors import DomainError
from openings.workspace import Workspace


def test_only_one_open_attempt_survives_concurrent_creation_and_reopening(tmp_path):
    path = tmp_path / "attempts.sqlite"
    workspace = Workspace(path)
    job = workspace.ingest_job({"title": "Engineer", "posting": "Build APIs."})

    def start(_):
        try:
            return Workspace(path).create_application({"job_id": job["id"]})
        except DomainError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, range(2)))
    first = next(result for result in results if isinstance(result, dict))
    conflict = next(result for result in results if isinstance(result, DomainError))
    assert conflict.code == "application_in_progress"
    assert conflict.details == {"application_id": first["id"], "status": "draft"}
    assert workspace.get_job(job["id"])["triage"] == "saved"
    with pytest.raises(sqlite3.IntegrityError):
        with workspace.db.transaction() as connection:
            connection.execute(
                "INSERT INTO applications(id,job_id,created_at,updated_at) VALUES('bypass',?,?,?)",
                (job["id"], first["created_at"], first["created_at"]),
            )

    first = workspace.update_application(
        first["id"],
        {"expected_version": first["version"], "status": "closed", "outcome": "not_pursued"},
    )
    second = workspace.create_application({"job_id": job["id"]})
    with pytest.raises(DomainError) as reopening:
        workspace.update_application(
            first["id"], {"expected_version": first["version"], "status": "draft"}
        )
    assert reopening.value.details["application_id"] == second["id"]
    assert workspace.get_application(first["id"])["status"] == "closed"


def test_summaries_filtering_and_merge_preserve_application_intent(tmp_path):
    workspace = Workspace(tmp_path / "summaries.sqlite")
    first = workspace.ingest_job({"title": "First", "posting": "Build APIs."})
    second = workspace.ingest_job({"title": "Second", "posting": "Operate infrastructure."})
    assert first["application"] is None and first["application_count"] == 0
    previous = workspace.create_application({"job_id": first["id"], "idempotency_key": "first"})
    previous = workspace.update_application(
        previous["id"],
        {"expected_version": previous["version"], "status": "closed", "outcome": "rejected"},
    )
    current = workspace.create_application({"job_id": first["id"]})
    workspace.create_application({"job_id": second["id"]})
    expected = {key: current[key] for key in ("id", "status", "outcome", "version")}
    summary = next(row for row in workspace.list_jobs()["items"] if row["id"] == first["id"])
    assert summary["application"] == workspace.get_job(first["id"])["application"] == expected
    assert summary["application_count"] == 2
    attempts = workspace.list_applications(job_id=first["id"], limit=1)
    assert attempts["total"] == 2 and len(attempts["items"]) == 1
    assert attempts["stage_counts"]["draft"] == attempts["stage_counts"]["closed"] == 1
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
    assert workspace.get_job(first["id"])["triage"] == "saved"
    workspace.set_triage(first["id"], "dismissed", workspace.get_job(first["id"])["version"])
    assert (
        workspace.create_application({"job_id": first["id"], "idempotency_key": "first"})["id"]
        == previous["id"]
    )


@pytest.mark.parametrize("transport", ["rest", "mcp"])
def test_interface_workflow_requires_explicit_outcomes_and_versioned_deletion(tmp_path, transport):
    app = create_app(tmp_path / f"workflow-{transport}.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic workflow client")["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:

        def call(tool, method, path, arguments, *, error=None):
            if transport == "rest":
                response = client.request(
                    method,
                    "/api/v1" + path,
                    params=arguments if method in ("GET", "DELETE") else None,
                    json=arguments.get("value") if method in ("POST", "PATCH") else None,
                )
                if error:
                    assert response.status_code == error
                    return response.json()
                response.raise_for_status()
                return response.json()
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            response.raise_for_status()
            result = response.json()["result"]
            if error:
                assert result.get("isError"), result
                return result
            assert not result.get("isError"), result
            return result.get("structuredContent") or json.loads(result["content"][0]["text"])

        job = call(
            "job_ingest",
            "POST",
            "/jobs",
            {
                "value": {
                    "title": "Engineer",
                    "company": "Example",
                    "posting": "Build APIs.",
                }
            },
        )
        attempt = call(
            "application_create",
            "POST",
            "/applications",
            {
                "value": {
                    "job_id": job["id"],
                    "note": "Keep this intent",
                    "idempotency_key": "start",
                }
            },
        )
        retry = call(
            "application_create",
            "POST",
            "/applications",
            {
                "value": {
                    "job_id": job["id"],
                    "note": "Keep this intent",
                    "idempotency_key": "start",
                }
            },
        )
        assert retry["id"] == attempt["id"]
        call(
            "application_create",
            "POST",
            "/applications",
            {
                "value": {
                    "job_id": job["id"],
                    "note": "Must not overwrite the existing intent",
                }
            },
            error=409,
        )
        assert (
            client.get(f"/api/v1/applications/{attempt['id']}").json()["note"] == "Keep this intent"
        )
        listed = call(
            "applications_list",
            "GET",
            "/applications",
            {
                "value": {"job_id": job["id"]},
            }
            if transport == "mcp"
            else {"job_id": job["id"]},
        )
        assert listed["total"] == 1 and listed["stage_counts"]["draft"] == 1

        path = f"/applications/{attempt['id']}"
        attempt = call(
            "application_update",
            "PATCH",
            path,
            {
                "application_id": attempt["id"],
                "value": {
                    "expected_version": attempt["version"],
                    "status": "applied",
                },
            },
        )
        assert attempt["applied_at"]
        attempt = call(
            "application_update",
            "PATCH",
            path,
            {
                "application_id": attempt["id"],
                "value": {
                    "expected_version": attempt["version"],
                    "applied_at": None,
                },
            },
        )
        assert attempt["applied_at"] is None
        call(
            "application_update",
            "PATCH",
            path,
            {
                "application_id": attempt["id"],
                "value": {
                    "expected_version": attempt["version"],
                    "status": "closed",
                },
            },
            error=422,
        )
        attempt = call(
            "application_update",
            "PATCH",
            path,
            {
                "application_id": attempt["id"],
                "value": {
                    "expected_version": attempt["version"],
                    "status": "closed",
                    "outcome": "rejected",
                },
            },
        )
        attempt = call(
            "application_update",
            "PATCH",
            path,
            {
                "application_id": attempt["id"],
                "value": {
                    "expected_version": attempt["version"],
                    "note": "Outcome remains rejected",
                },
            },
        )
        assert attempt["outcome"] == "rejected"
        call(
            "application_delete",
            "DELETE",
            path,
            {
                "application_id": attempt["id"],
            }
            if transport == "mcp"
            else {},
            error=422,
        )
        call(
            "application_delete",
            "DELETE",
            path,
            {
                **({"application_id": attempt["id"]} if transport == "mcp" else {}),
                "expected_version": attempt["version"] - 1,
            },
            error=409,
        )
        call(
            "application_delete",
            "DELETE",
            path,
            {
                **({"application_id": attempt["id"]} if transport == "mcp" else {}),
                "expected_version": attempt["version"],
            },
        )
        retained = client.get(f"/api/v1/jobs/{job['id']}").json()
        assert retained["triage"] == "saved" and retained["application_count"] == 0
        call(
            "job_forget",
            "DELETE",
            f"/jobs/{job['id']}",
            {
                "job_id": job["id"],
            }
            if transport == "mcp"
            else {},
            error=422,
        )
        call(
            "job_forget",
            "DELETE",
            f"/jobs/{job['id']}",
            {
                **({"job_id": job["id"]} if transport == "mcp" else {}),
                "expected_version": job["version"],
            },
            error=409,
        )
        call(
            "job_forget",
            "DELETE",
            f"/jobs/{job['id']}",
            {
                **({"job_id": job["id"]} if transport == "mcp" else {}),
                "expected_version": retained["version"],
            },
        )
        assert client.get("/api/v1/jobs").json()["total"] == 0
