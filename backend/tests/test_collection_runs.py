"""Complete collection workflows across saved settings, resumable tasks and scoring."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from openings import discovery as module
from openings.app import create_app
from openings.collectors.policy import ProviderDeferred
from openings.discovery import (
    CollectionWrite,
    DiscoveryService,
    SourceBulk,
    SourceCreate,
    SourcePatch,
)
from openings.errors import DomainError
from openings.scheduling import next_due, schedule_adapter
from openings.workspace import Workspace


@pytest.fixture
def collection(tmp_path):
    workspace = Workspace(tmp_path / "collection.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    return workspace, service


def make_source(service, **changes):
    return service.create_source(
        SourceCreate(
            name="Example board", kind="greenhouse", config={"board": "example"}, **changes
        )
    )


def run_next(service):
    task = service.claim_task("worker", "collect")
    assert task
    service.run_task(task, "worker")
    return service.get_task(task["id"])


def test_daily_slots_coalesce_and_handle_clock_changes():
    schedule = {"kind": "daily", "times": ["05:00", "13:00", "21:00"], "timezone": "Europe/Paris"}
    now = datetime(2026, 10, 30, 20, 10, tzinfo=timezone.utc)
    assert (
        next_due(schedule, "2026-10-29T04:00:00+00:00", now).isoformat()
        == "2026-10-30T20:00:00+00:00"
    )
    assert (
        next_due(schedule, "2026-10-30T20:00:00+00:00", now).isoformat()
        == "2026-10-31T04:00:00+00:00"
    )
    spring = {"kind": "daily", "times": ["02:30"], "timezone": "Europe/Paris"}
    assert (
        next_due(
            spring, "2026-03-28T01:30:00+00:00", datetime(2026, 3, 29, 2, tzinfo=timezone.utc)
        ).isoformat()
        == "2026-03-29T01:30:00+00:00"
    )
    with pytest.raises(ValidationError):
        schedule_adapter.validate_python({"kind": "interval", "minutes": 60, "timezone": "UTC"})


def test_frozen_options_resume_with_cumulative_unique_observations(collection, monkeypatch):
    workspace, service = collection
    source = make_source(service)
    queued = service.queue_collection(source["id"], overrides={"max_results": 50})
    service.update_source(
        source["id"], SourcePatch(expected_version=source["version"], config={"max_results": 10})
    )
    posting = {
        "title": "Backend engineer",
        "company": "Example",
        "url": "https://example.org/jobs/1",
        "source_key": "greenhouse:example:1",
        "posting": "Build reliable APIs.",
    }
    calls = []

    def collect(source):
        calls.append((source["config"]["max_results"], source["checkpoint"].get("page", 0)))
        source["on_item"](posting)
        source["streamed"] = True
        if not source["checkpoint"]:
            source["on_checkpoint"]({"page": 1, "complete": False, "pending_details": 1})
            raise ProviderDeferred("greenhouse", "collection_batch")
        source["on_checkpoint"]({"page": 2, "complete": True, "pending_details": 0})
        return []

    monkeypatch.setattr(module, "fetch_postings", collect)
    first = run_next(service)
    assert first["state"] == "queued"
    assert first["result"]["created"] == 1
    assert (
        service.get_task(first["id"], include_checkpoint=True)["payload"]["checkpoint"]["page"] == 1
    )
    workspace.db.execute("UPDATE tasks SET next_run_at=? WHERE id=?", (module.now(), queued["id"]))
    second = run_next(service)
    assert second["state"] == "succeeded"
    assert second["result"]["received"] == second["result"]["created"] == 1
    assert second["result"]["existing"] == 0
    assert len(second["result"]["attempt_history"]) == 2
    assert calls == [(50, 0), (50, 1)]
    run = service.get_run(queued["run_id"])
    assert run["counts"]["pending_descriptions"] == 0
    assert run["counts"]["created"] == 1 and run["state"] == "succeeded"
    assert service.get_source(source["id"])["config"]["max_results"] == 10
    assert service.get_source(source["id"])["last_run"]["id"] == run["id"]
    assert service.list_runs(state="succeeded")["total"] == 1


def test_new_partial_initial_score_does_not_rescore_history(collection, monkeypatch):
    workspace, service = collection
    workspace.set_settings("profile", {"summary": "Backend engineer"})
    workspace.set_settings("scoring", {"enabled": True, "auto_rescore_updates": False})
    monkeypatch.setattr(
        module,
        "score_call",
        lambda *args: {"score": 75, "model": "example", "elapsed_seconds": 0, "response": {}},
    )
    new = workspace.ingest_job(
        {
            "title": "Engineer",
            "company": "Example",
            "url": "https://example.org/new",
            "metadata": {"description_complete": False},
        }
    )
    historical = workspace.ingest_job(
        {
            "title": "Engineer",
            "company": "Example",
            "url": "https://example.org/old",
            "metadata": {"description_complete": False},
        }
    )
    workspace.db.execute("UPDATE jobs SET initial_score_pending=0 WHERE id=?", (historical["id"],))
    for job in (new, historical):
        workspace.ingest_job(
            {
                "title": "Engineer",
                "company": "Example",
                "url": job["url"],
                "posting": "Build APIs.",
                "metadata": {"description_complete": True},
            }
        )
    tasks = service.list_tasks(kind="score")["items"]
    assert len(tasks) == 1 and tasks[0]["job_id"] == new["id"]
    task = service.claim_task("worker", "score")
    service.run_task(task, "worker")
    assert workspace.get_job(new["id"])["initial_score_pending"] == 0
    workspace.ingest_job(
        {
            "title": "Engineer",
            "company": "Example",
            "url": new["url"],
            "posting": "Build APIs and queues.",
        }
    )
    assert service.list_tasks(kind="score", state="queued")["total"] == 0


def test_bulk_configuration_preserves_untouched_fields_and_service(collection):
    _, service = collection
    source = make_source(service)
    result = service.bulk_sources(
        SourceBulk.model_validate(
            {
                "action": "configure",
                "items": [
                    {"id": source["id"], "expected_version": 1},
                    {"id": "missing", "expected_version": 1},
                ],
                "patch": {
                    "config": {"max_results": 50},
                    "schedule": {"kind": "daily", "times": ["08:00", "17:00"], "timezone": "UTC"},
                },
            }
        )
    )
    assert result["succeeded"] == result["failed"] == 1
    current = service.get_source(source["id"])
    assert current["config"]["board"] == "example"
    assert "max_details" not in current["config"]
    assert current["config"]["max_results"] == 50
    with pytest.raises(DomainError, match="Create a new source"):
        service.update_source(
            source["id"], SourcePatch(expected_version=current["version"], kind="lever")
        )


def test_pause_and_delete_preserve_run_history(collection, monkeypatch):
    workspace, service = collection
    source = make_source(service, enabled=True)
    queued = service.queue_collection(source["id"], manual=False)
    service.update_collection(CollectionWrite(expected_version=0, enabled=False))
    assert service.get_task(queued["id"])["state"] == "queued"
    monkeypatch.setattr(module, "fetch_postings", lambda source: [])
    assert run_next(service)["state"] == "succeeded"
    service.delete_source(source["id"], source["version"])
    run = service.get_run(queued["run_id"])
    assert run["source_id"] is None and run["source_name"] == "Example board"
    assert run["state"] == "succeeded" and workspace.list_jobs()["total"] == 0


def test_rest_versions_overrides_and_schema_discovery(tmp_path):
    app = create_app(tmp_path / "api.sqlite", start_worker=False)
    with TestClient(app) as client:
        setup = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        client.headers["X-CSRF-Token"] = setup.json()["csrf_token"]
        source = client.post(
            "/api/v1/sources",
            json={
                "name": "Backend",
                "kind": "jobspy",
                "config": {"query": "backend", "providers": ["linkedin"]},
            },
        ).json()
        assert client.post(f"/api/v1/sources/{source['id']}/run").status_code == 422
        assert client.delete(f"/api/v1/sources/{source['id']}").status_code == 422
        assert (
            client.post(
                f"/api/v1/sources/{source['id']}/run", json={"expected_version": 99}
            ).status_code
            == 409
        )
        response = client.post(
            f"/api/v1/sources/{source['id']}/run",
            json={"expected_version": 1, "overrides": {"hours_old": 168, "results_wanted": 50}},
        )
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        assert (
            client.get(f"/api/v1/collection/runs/{run_id}").json()["source_snapshot"]["config"][
                "hours_old"
            ]
            == 168
        )
        assert client.get(f"/api/v1/sources/{source['id']}").json()["config"]["hours_old"] == 72
        schemas = client.get("/api/v1/sources/schemas").json()
        assert schemas["items"][0]["config_schema"]["properties"]["results_wanted"]["default"] == 20
        assert not {"jobcloud", "adzuna"}.intersection(item["kind"] for item in schemas["items"])
        assert (
            client.post(f"/api/v1/collection/runs/{run_id}/cancel").json()["state"] == "cancelled"
        )


def test_explicit_retry_preserves_progress_and_renews_error_allowance(collection, monkeypatch):
    workspace, service = collection
    source = make_source(service)
    queued = service.queue_collection(source["id"])
    workspace.db.execute(
        "UPDATE tasks SET state='failed',attempts=3,result=?,payload=json_set(payload,'$.checkpoint',json(?),'$.observed_identities',json(?)) WHERE id=?",
        (
            module.encode({"created": 2, "failure_attempts": 3}),
            module.encode({"page": 2}),
            module.encode(["known"]),
            queued["id"],
        ),
    )
    public = service.get_task(queued["id"])
    assert "checkpoint" not in public["payload"] and "observed_identities" not in public["payload"]
    service.retry_task(queued["id"])
    claimed = service.claim_task("worker", "collect")
    assert claimed["attempts"] == 4 and claimed["payload"]["checkpoint"] == {"page": 2}
    assert claimed["result"]["created"] == 2 and claimed["result"]["failure_attempts"] == 0
    monkeypatch.setattr(
        module,
        "fetch_postings",
        lambda source: (_ for _ in ()).throw(DomainError(502, "temporary", "Try later.")),
    )
    service.run_task(claimed, "worker")
    assert service.get_task(queued["id"])["state"] == "queued"
    assert service.get_task(queued["id"])["result"]["failure_attempts"] == 1


@pytest.mark.parametrize("preview", ["", "Python and SQL preview"])
def test_partial_refresh_keeps_complete_body_and_records_raw_observation(collection, preview):
    workspace, _ = collection
    source = {"url": "https://example.org/job", "title": "Engineer", "company": "Example"}
    original = workspace.ingest_job(
        {
            **source,
            "posting": "Build APIs and maintain production data systems.",
            "metadata": {"description_complete": True, "description_status": "complete"},
        }
    )
    refreshed = workspace.ingest_job(
        {
            **source,
            "posting": preview,
            "metadata": {"description_complete": False, "description_status": "pending"},
        }
    )
    assert refreshed["complete"] and refreshed["posting"] == original["posting"]
    assert refreshed["content_version"] == original["content_version"]
    observation = workspace.db.one("SELECT payload FROM postings WHERE job_id=?", (original["id"],))
    assert '"description_complete":false' in observation["payload"]


def test_initial_score_can_wait_for_profile_without_rescoring_history(collection):
    workspace, service = collection
    workspace.set_settings("scoring", {"enabled": True, "auto_rescore_updates": False})
    posting = {"url": "https://example.org/job", "posting": "Build APIs.", "title": "Engineer"}
    job = workspace.ingest_job(posting)
    assert job["initial_score_pending"] and service.list_tasks(kind="score")["total"] == 0
    workspace.set_settings("profile", {"summary": "Backend engineer"})
    refreshed = workspace.ingest_job(posting)
    assert refreshed["content_version"] == job["content_version"]
    assert service.list_tasks(kind="score", state="queued")["total"] == 1


def test_partial_filter_patch_preserves_other_terms_and_explicit_empty_clears(collection):
    _, service = collection
    source = service.create_source(
        SourceCreate(
            name="Example",
            kind="greenhouse",
            config={"board": "example"},
            filters={"titles": ["engineer"], "locations": ["Canada"]},
        )
    )
    changed = service.bulk_sources(
        SourceBulk.model_validate(
            {
                "action": "configure",
                "items": [{"id": source["id"], "expected_version": source["version"]}],
                "patch": {"filters": {"titles": ["developer"]}},
            }
        )
    )["items"][0]["result"]
    assert changed["filters"] == {"titles": ["developer"], "locations": ["Canada"]}
    cleared = service.update_source(
        source["id"],
        SourcePatch.model_validate(
            {"expected_version": changed["version"], "filters": {"locations": []}}
        ),
    )
    assert cleared["filters"] == {"titles": ["developer"], "locations": []}
