"""Complete collection workflows across saved settings, resumable tasks."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from discovery_fixtures import patch_discovery
from openings.collectors.policy import ProviderDeferred
from openings.common import encode, now
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
    now = datetime(2026, 10, 30, 20, 10, tzinfo=UTC)
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
            spring, "2026-03-28T01:30:00+00:00", datetime(2026, 3, 29, 2, tzinfo=UTC)
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

    patch_discovery(monkeypatch, "fetch_postings", collect)
    first = run_next(service)
    assert first["state"] == "queued"
    assert first["result"]["created"] == 1
    assert (
        service.get_task(first["id"], include_checkpoint=True)["payload"]["checkpoint"]["page"] == 1
    )
    workspace.db.execute("UPDATE tasks SET next_run_at=? WHERE id=?", (now(), queued["id"]))
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


def test_bulk_configuration_and_filter_patches_preserve_untouched_fields(collection):
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

    # A partial filter patch keeps the other terms; an explicit empty list clears one.
    source = service.create_source(
        SourceCreate(
            name="Example",
            kind="greenhouse",
            config={"board": "example"},
            filters={"titles": ["engineer"], "locations": ["Canada"], "exclude_titles": ["sales"]},
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
    assert changed["filters"] == {
        "titles": ["developer"],
        "locations": ["Canada"],
        "exclude_titles": ["sales"],
    }
    cleared = service.update_source(
        source["id"],
        SourcePatch.model_validate(
            {"expected_version": changed["version"], "filters": {"locations": []}}
        ),
    )
    assert cleared["filters"] == {
        "titles": ["developer"],
        "locations": [],
        "exclude_titles": ["sales"],
    }


def test_a_stored_search_without_its_query_is_refused_not_a_server_error(collection):
    workspace, service = collection
    source = service.create_source(
        SourceCreate(
            name="Example search",
            kind="jobspy",
            config={"query": "data", "providers": ["linkedin"]},
        )
    )
    # A record written before the query was required, as an old workspace holds.
    with workspace.db.transaction() as connection:
        connection.execute(
            "UPDATE sources SET config=? WHERE id=?",
            (encode({"providers": ["linkedin"]}), source["id"]),
        )
    item = {"id": source["id"], "expected_version": source["version"]}
    result = service.bulk_sources(SourceBulk.model_validate({"action": "run", "items": [item]}))
    assert result["failed"] == 1
    error = result["items"][0]["error"]
    assert (error["status"], error["code"]) == (422, "source_config")
    assert list(error["details"][0]["loc"]) == ["query"]
    with pytest.raises(DomainError, match="saved search configuration is invalid"):
        service.queue_collection(source["id"], expected_version=source["version"])
    assert service.list_runs()["total"] == 0


def test_a_source_that_no_longer_validates_is_reported_and_the_others_still_run(collection):
    workspace, service = collection
    broken = service.create_source(
        SourceCreate(
            name="Example search",
            kind="jobspy",
            enabled=True,
            config={"query": "data", "providers": ["linkedin"]},
        )
    )
    feed = make_source(service, enabled=True)
    old = "2000-01-01T00:00:00+00:00"
    with workspace.db.transaction() as connection:
        connection.execute(
            "UPDATE sources SET config=? WHERE id=?",
            (encode({"providers": ["linkedin"]}), broken["id"]),
        )
        connection.execute("UPDATE sources SET last_scheduled_at=?", (old,))
    service.schedule_due()
    assert [run["source_id"] for run in service.list_runs()["items"]] == [feed["id"]]
    reported = service.get_source(broken["id"])
    assert "saved search configuration is invalid" in reported["last_error"]
    # It waits for its next slot instead of failing every scheduler cycle.
    assert reported["last_scheduled_at"] > old


def test_a_stored_empty_schedule_is_the_default_interval(collection):
    workspace, service = collection
    source = make_source(service)
    workspace.db.execute("UPDATE sources SET schedule='{}' WHERE id=?", (source["id"],))
    stored = service.get_source(source["id"])
    renamed = service.update_source(
        source["id"], SourcePatch(name="Renamed board", expected_version=stored["version"])
    )
    assert renamed["schedule"] == {"kind": "interval", "minutes": 1440}


def test_pause_and_delete_preserve_run_history(collection, monkeypatch):
    workspace, service = collection
    source = make_source(service, enabled=True)
    queued = service.queue_collection(source["id"], manual=False)
    service.update_collection(CollectionWrite(expected_version=0, enabled=False))
    assert service.get_task(queued["id"])["state"] == "queued"
    patch_discovery(monkeypatch, "fetch_postings", lambda source: [])
    assert run_next(service)["state"] == "succeeded"
    service.delete_source(source["id"], source["version"])
    run = service.get_run(queued["run_id"])
    assert run["source_id"] is None and run["source_name"] == "Example board"
    assert run["state"] == "succeeded" and workspace.list_jobs()["total"] == 0


def test_rest_versions_overrides_and_schema_discovery(client):
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
    assert client.post(f"/api/v1/collection/runs/{run_id}/cancel").json()["state"] == "cancelled"


def test_explicit_retry_preserves_progress_and_renews_error_allowance(collection, monkeypatch):
    workspace, service = collection
    source = make_source(service)
    queued = service.queue_collection(source["id"])
    workspace.db.execute(
        "UPDATE tasks SET state='failed',attempts=3,result=?,payload=json_set(payload,'$.checkpoint',json(?),'$.observed_identities',json(?)) WHERE id=?",
        (
            encode({"created": 2, "failure_attempts": 3}),
            encode({"page": 2}),
            encode(["known"]),
            queued["id"],
        ),
    )
    public = service.get_task(queued["id"])
    assert "checkpoint" not in public["payload"] and "observed_identities" not in public["payload"]
    service.retry_task(queued["id"])
    claimed = service.claim_task("worker", "collect")
    assert claimed["attempts"] == 4 and claimed["payload"]["checkpoint"] == {"page": 2}
    assert claimed["result"]["created"] == 2 and claimed["result"]["failure_attempts"] == 0
    patch_discovery(
        monkeypatch,
        "fetch_postings",
        lambda source: (_ for _ in ()).throw(DomainError(502, "temporary", "Try later.")),
    )
    service.run_task(claimed, "worker")
    assert service.get_task(queued["id"])["state"] == "queued"
    assert service.get_task(queued["id"])["result"]["failure_attempts"] == 1


def test_partial_refresh_keeps_complete_body_and_records_the_observation(collection):
    workspace, _ = collection
    for number, preview in enumerate(["", "Python and SQL preview"]):
        source = {
            "url": f"https://example.org/job/{number}",
            "title": "Engineer",
            "company": "Example",
        }
        original = workspace.ingest_job(
            {
                **source,
                "posting": "Build APIs and maintain production data systems.",
                "metadata": {"description_complete": True, "description_status": "complete"},
            }
        )
        first = workspace.db.one("SELECT * FROM postings WHERE job_id=?", (original["id"],))
        refreshed = workspace.ingest_job(
            {
                **source,
                "posting": preview,
                "metadata": {"description_complete": False, "description_status": "pending"},
            }
        )
        assert refreshed["complete"] and refreshed["posting"] == original["posting"]
        assert refreshed["content_version"] == original["content_version"]
        # The same observation records the sighting and that its content differed; the
        # provider's response itself is not stored.
        observation = workspace.db.one("SELECT * FROM postings WHERE job_id=?", (original["id"],))
        assert observation["id"] == first["id"] and observation["payload"] == "{}"
        assert observation["content_hash"] != first["content_hash"]
        assert observation["last_seen_at"] > first["last_seen_at"]
        assert (
            workspace.db.one("SELECT count(*) n FROM events WHERE kind='job_refreshed'")["n"] == 0
        )
