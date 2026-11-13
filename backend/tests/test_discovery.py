"""A few shared-service invariants for collection and task recovery."""

from datetime import UTC, datetime

import pytest

from discovery_fixtures import patch_discovery
from openings.discovery import DiscoveryService, SourceCreate
from openings.errors import DomainError
from openings.scheduling import next_due
from openings.workspace import Workspace


@pytest.fixture
def case(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    workspace.set_settings(
        "profile",
        {
            "headline": "Backend engineer",
            "summary": "Python backend engineer, five years building APIs.",
        },
    )
    return workspace, service


def run_next(service, owner="test-worker"):
    task = service.claim_task(owner)
    assert task is not None
    service.run_task(task, owner)
    return task


def test_user_completed_posting_survives_source_preview_refresh(case):
    workspace, _ = case
    source = {
        "title": "Engineer",
        "company": "Example",
        "posting": "Python, SQL",
        "url": "https://example.test/jobs/preview",
        "metadata": {"description_complete": False},
        "raw": {"preview": "Python, SQL"},
    }
    preview = workspace.ingest_job(source)
    assert not preview["complete"]
    completed = workspace.update_job(
        preview["id"], {"expected_version": preview["version"], "posting": "Build SQL services."}
    )
    refreshed = workspace.ingest_job({**source, "posting": "New source preview"})
    assert completed["complete"] and refreshed["complete"]
    assert refreshed["posting"] == "Build SQL services."
    assert refreshed["metadata"]["description_complete"] is False
    assert workspace.list_jobs(complete=True)["total"] == 1
    assert workspace.overview()["incomplete"] == 0
    # The observation is refreshed in place and stores no provider response.
    seen = workspace.db.all("SELECT payload FROM postings WHERE job_id=?", (preview["id"],))
    assert [row["payload"] for row in seen] == ["{}"]


def test_source_failure_is_isolated(case, monkeypatch):
    workspace, service = case
    first = service.create_source(
        SourceCreate(name="Failing", kind="ashby", config={"board": "bad"})
    )
    second = service.create_source(
        SourceCreate(name="Working", kind="ashby", config={"board": "good"})
    )

    def feed(source):
        if source["id"] == first["id"]:
            raise DomainError(502, "source_http", "The source returned HTTP 503.")
        return [
            {
                "title": "API Engineer",
                "company": "Working",
                "posting": "Build reliable APIs.",
                "url": "https://jobs.ashbyhq.com/good/example",
                "source_key": "ashby:good:example",
            }
        ]

    patch_discovery(monkeypatch, "fetch_postings", feed)
    service.queue_collection(first["id"])
    service.queue_collection(second["id"])
    run_next(service)
    run_next(service)
    assert service.get_source(first["id"])["last_run"]["tasks"][0]["error"]
    assert service.get_source(second["id"])["last_error"] is None
    assert workspace.list_jobs()["total"] == 1


def test_daily_schedule_avoids_double_run_during_fall_back():
    schedule = {"kind": "daily", "times": ["02:30"], "timezone": "Europe/Zurich"}
    current = datetime(2026, 10, 25, 1, 45, tzinfo=UTC)
    previous = "2026-10-25T00:30:00+00:00"
    assert next_due(schedule, previous, current).date().isoformat() == "2026-10-26"


def test_cancel_between_claim_and_collection_does_not_touch_source(case, monkeypatch):
    _, service = case
    source = service.create_source(
        SourceCreate(name="Example", kind="greenhouse", config={"board": "example"})
    )
    service.queue_collection(source["id"])
    task = service.claim_task("test-worker")
    service.cancel_task(task["id"])
    patch_discovery(monkeypatch, "fetch_postings", lambda source: pytest.fail("Cancelled fetch"))
    service.run_task(task, "test-worker")
    assert service.get_source(source["id"])["last_run_at"] is None
