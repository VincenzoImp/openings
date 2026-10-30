"""A few shared-service invariants for collection, assessment and task recovery."""

from datetime import datetime, timezone

import httpx
import pytest

from openings import discovery as module
from openings.discovery import (
    DiscoveryService,
    RescoreRequest,
    ScoringWrite,
    SourceCreate,
    next_due,
    score_call,
)
from openings.errors import DomainError
from openings.workspace import Workspace


@pytest.fixture
def case(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    workspace.set_settings(
        "profile",
        {
            "summary": "Python backend engineer, five years building APIs.",
            "roles": "Backend engineer",
            "preferences": "Remote roles",
        },
    )
    workspace.bump_scoring_profile()
    monkeypatch.setattr(
        module,
        "score_call",
        lambda config, state: {
            "score": 75.0,
            "model": "synthetic-model",
            "elapsed_seconds": 0.01,
            "response": {
                "model": "synthetic-model",
                "answers": {"fit": {"type": "score", "score": 3.0}},
                "usage": {"truncated": False},
            },
            "request": {"state": state},
        },
    )
    service.update_scoring(
        ScoringWrite(
            expected_version=0,
            enabled=True,
            mode="remote",
            provider="systemone",
            base_url="https://model.example",
            api_key="synthetic-key",
        )
    )
    return workspace, service


def run_next(service, owner="test-worker"):
    task = service.claim_task(owner)
    assert task is not None
    service.run_task(task, owner)
    return task


def test_partial_postings_stay_archived_without_entering_scoring_batches(case):
    workspace, service = case
    complete = workspace.ingest_job(
        {"title": "Engineer", "company": "Example", "posting": "Build APIs."}
    )
    partial = [
        workspace.ingest_job(
            {"title": "Engineer", "company": "Example", "posting": text, "metadata": metadata}
        )
        for text, metadata in (
            ("Python, SQL, cloud", {"description_complete": False}),
            ("— - …", {}),
        )
    ]
    tasks = service.list_tasks(kind="score")["items"]
    assert len(tasks) == 1 and tasks[0]["job_id"] == complete["id"]
    assert workspace.list_jobs()["total"] == 3
    assert service.queue_rescore(
        RescoreRequest(job_ids=[item["id"] for item in partial], outdated_only=False)
    ) == {"queued": [], "skipped": [item["id"] for item in partial], "count": 0}
    service.cancel_task(tasks[0]["id"])
    config = service.get_scoring()
    service.update_scoring(
        ScoringWrite(
            expected_version=config["version"],
            periodic_rescore={"enabled": True, "minutes": 1440, "batch_size": 1},
        )
    )
    service.schedule_due()
    queued = service.list_tasks(kind="score", state="queued")["items"]
    assert len(queued) == 1 and queued[0]["job_id"] == complete["id"]


def test_user_completed_posting_survives_source_preview_refresh(case):
    workspace, service = case
    source = {
        "title": "Engineer",
        "company": "Example",
        "posting": "Python, SQL",
        "url": "https://example.test/jobs/preview",
        "metadata": {"description_complete": False},
        "raw": {"preview": "Python, SQL"},
    }
    preview = workspace.ingest_job(source)
    assert not preview["complete"] and not service.list_tasks(kind="score")["items"]
    completed = workspace.update_job(
        preview["id"], {"expected_version": preview["version"], "posting": "Build SQL services."}
    )
    refreshed = workspace.ingest_job({**source, "posting": "New source preview"})
    assert completed["complete"] and refreshed["complete"]
    assert refreshed["posting"] == "Build SQL services."
    assert refreshed["metadata"]["description_complete"] is False
    assert workspace.list_jobs(complete=True)["total"] == 1
    assert workspace.overview()["incomplete"] == 0
    assert service.list_tasks(kind="score", state="queued")["total"] == 1
    raw = workspace.db.one("SELECT payload FROM postings WHERE job_id=?", (preview["id"],))
    assert '"posting":"New source preview"' in raw["payload"]


def test_task_queued_before_posting_became_partial_does_not_infer(case, monkeypatch):
    workspace, service = case
    original = workspace.ingest_job(
        {"title": "Engineer", "company": "Example", "posting": "Build APIs."}
    )
    workspace.update_job(
        original["id"],
        {"expected_version": original["version"], "metadata": {"description_complete": False}},
    )
    monkeypatch.setattr(
        module, "score_call", lambda *args: pytest.fail("Incomplete postings must not infer")
    )
    task = run_next(service)
    assert service.get_task(task["id"])["result"] == {"skipped": "job_not_eligible_for_scoring"}
    assert workspace.get_job(original["id"])["score"] is None


def test_collection_and_scoring_preserve_identity_and_deliberate_freshness(case, monkeypatch):
    workspace, service = case
    source = service.create_source(
        SourceCreate(name="Example Co", kind="greenhouse", config={"board": "example"})
    )
    posting = {
        "title": "Backend engineer",
        "company": "Example Co",
        "posting": "Build Python APIs.",
        "url": "https://boards.greenhouse.io/example/jobs/123",
        "source_key": "greenhouse:example:123",
        "raw": {"id": 123, "updated_at": "first"},
    }
    monkeypatch.setattr(module, "fetch_postings", lambda source: [posting])
    service.queue_collection(source["id"])
    run_next(service)
    job = workspace.list_jobs()["items"][0]
    run_next(service)
    assert workspace.get_job(job["id"])["score"] == 75
    assert not workspace.get_job(job["id"])["score_outdated"]
    posting["raw"]["updated_at"] = "later timestamp only"
    service.queue_collection(source["id"])
    run_next(service)
    assert workspace.list_jobs()["total"] == 1
    assert service.claim_task("test-worker") is None
    old_config = service.get_scoring()
    assert "api_key" not in old_config and old_config["api_key_set"]
    service.update_scoring(ScoringWrite(expected_version=old_config["version"], enabled=False))
    assert not workspace.get_job(job["id"])["score_outdated"]
    assert workspace.get_job(job["id"])["score"] == 75
    workspace.bump_scoring_profile()
    assert workspace.get_job(job["id"])["score_outdated"]
    assert service.claim_task("test-worker") is None


def test_late_assessment_cannot_resurrect_forgotten_job(case, monkeypatch):
    workspace, service = case
    job = workspace.ingest_job(
        {"title": "Backend engineer", "company": "Example", "posting": "Build APIs"}
    )
    task = service.claim_task("test-worker")
    assert task and task["job_id"] == job["id"]

    def forget_then_answer(config, state):
        workspace.forget_job(job["id"])
        return {"score": 90, "model": "synthetic-model", "elapsed_seconds": 0, "response": {}}

    monkeypatch.setattr(module, "score_call", forget_then_answer)
    service.run_task(task, "test-worker")
    assert workspace.list_jobs()["total"] == 0
    assert not workspace.db.all("SELECT * FROM assessments")
    assert not workspace.db.all("SELECT * FROM tasks")


@pytest.mark.parametrize(
    "initial_mode, updates, should_unload",
    [
        ("local", {"enabled": False}, True),
        ("local", {"mode": "remote", "base_url": "https://remote.example"}, True),
        ("local", {"provider": "systemone"}, True),
        ("local", {"base_url": "http://other-local-scorer:8000"}, True),
        ("local", {"base_url": "http://scorer:8000/v1"}, False),
        ("local", {"timeout_seconds": 60}, False),
        ("remote", {"enabled": False}, False),
    ],
)
def test_leaving_local_scorer_releases_only_previously_owned_runtime(
    case, monkeypatch, initial_mode, updates, should_unload
):
    workspace, service = case
    current = service.get_scoring()
    service.update_scoring(
        ScoringWrite(
            expected_version=current["version"],
            mode=initial_mode,
            provider="laya",
            base_url="http://scorer:8000",
        )
    )
    unloaded = []

    def unload_old(config):
        # Unload follows the successful settings commit and uses old credentials/URL.
        saved = workspace.get_settings("scoring")["data"]
        assert all(saved[key] == value for key, value in updates.items())
        unloaded.append(config)

    monkeypatch.setattr(service, "_unload_local", unload_old)
    service.update_scoring(
        ScoringWrite(expected_version=service.get_scoring()["version"], **updates)
    )
    assert len(unloaded) == int(should_unload)
    if unloaded:
        assert unloaded[0]["mode"] == "local"
        assert unloaded[0]["base_url"] == "http://scorer:8000"


def test_failed_replacement_keeps_previous_score_and_source_failure_is_isolated(case, monkeypatch):
    workspace, service = case
    job = workspace.ingest_job(
        {"title": "Engineer", "company": "Example", "posting": "Python API work"}
    )
    run_next(service)
    workspace.bump_scoring_profile()
    service.queue_rescore(RescoreRequest(job_ids=[job["id"]]))

    def too_long(config, state):
        raise DomainError(422, "context_too_long", "The context did not fit.")

    monkeypatch.setattr(module, "score_call", too_long)
    task = run_next(service)
    assert service.get_task(task["id"])["state"] == "failed"
    assert workspace.get_job(job["id"])["score"] == 75
    assert workspace.get_job(job["id"])["score_outdated"]
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

    monkeypatch.setattr(module, "fetch_postings", feed)
    service.queue_collection(first["id"])
    service.queue_collection(second["id"])
    run_next(service)
    run_next(service)
    assert service.get_source(first["id"])["last_run"]["tasks"][0]["error"]
    assert service.get_source(second["id"])["last_error"] is None
    assert workspace.list_jobs()["total"] == 2


def test_daily_schedule_avoids_double_run_during_fall_back():
    schedule = {"kind": "daily", "times": ["02:30"], "timezone": "Europe/Zurich"}
    current = datetime(2026, 10, 25, 1, 45, tzinfo=timezone.utc)
    previous = "2026-10-25T00:30:00+00:00"
    assert next_due(schedule, previous, current).date().isoformat() == "2026-10-26"


@pytest.mark.parametrize(
    "payload, code",
    [
        ({"usage": ["invalid"]}, "scorer_format"),
        ({"answers": ["invalid"]}, "scorer_format"),
        ({"answers": {"fit": {"type": "score", "score": True}}}, "scorer_format"),
    ],
)
def test_score_protocol_rejects_malformed_results(monkeypatch, payload, code):
    original = httpx.Client

    def transport(request):
        return httpx.Response(
            200,
            json={
                "model": "synthetic",
                "answers": {"fit": {"type": "score", "score": 3}},
                "usage": {},
                **payload,
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    with pytest.raises(DomainError) as caught:
        score_call(
            {"base_url": "https://model.example", "provider": "systemone"}, {"job": "synthetic"}
        )
    assert caught.value.code == code


@pytest.mark.parametrize("include_preparation", [False, True])
def test_score_protocol_accepts_state_clipping_and_optional_preparation(
    monkeypatch, include_preparation
):
    original = httpx.Client
    preparation = {"version": 1, "state": "Candidate\nJob\nPosting prefix", "shortened": True}

    def transport(request):
        return httpx.Response(
            200,
            json={
                "model": "synthetic",
                "answers": {"fit": {"type": "score", "score": 3}},
                "usage": {
                    "truncated": True,
                    "state_tokens_dropped": 20,
                    "truncated_questions": ["fit"],
                },
                **({"input_preparation": preparation} if include_preparation else {}),
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    result = score_call(
        {"base_url": "https://model.example", "provider": "systemone"}, {"job": "synthetic"}
    )
    assert result["score"] == 75
    if include_preparation:
        assert result["response"]["input_preparation"] == preparation
    else:
        assert "input_preparation" not in result["response"]
    assert result["request"]["state"] == {"job": "synthetic"}


def test_score_protocol_reports_oversized_question_configuration(monkeypatch):
    original = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(422, json={"detail": {"code": "question_too_long"}})
    )
    monkeypatch.setattr(module.httpx, "Client", lambda **kwargs: original(transport=transport))
    with pytest.raises(DomainError) as caught:
        score_call({"base_url": "https://model.example"}, {"job": "synthetic"})
    assert caught.value.code == "scoring_question_too_long"
    assert "rubric or criteria" in caught.value.message


def test_cancel_between_claim_and_collection_does_not_touch_source(case, monkeypatch):
    _, service = case
    source = service.create_source(
        SourceCreate(name="Example", kind="greenhouse", config={"board": "example"})
    )
    service.queue_collection(source["id"])
    task = service.claim_task("test-worker")
    service.cancel_task(task["id"])
    monkeypatch.setattr(module, "fetch_postings", lambda source: pytest.fail("Cancelled fetch"))
    service.run_task(task, "test-worker")
    assert service.get_source(source["id"])["last_run_at"] is None


def test_worker_restart_ignores_old_inflight_result(case, monkeypatch):
    import threading
    import time

    from openings.worker import Worker

    workspace, service = case
    entered, release = threading.Event(), threading.Event()
    calls = []

    def delayed_score(config, state):
        calls.append(1)
        first = len(calls) == 1
        if first:
            entered.set()
            assert release.wait(5)
        return {
            "score": 95 if first else 65,
            "model": "synthetic",
            "elapsed_seconds": 0,
            "response": {},
        }

    monkeypatch.setattr(module, "score_call", delayed_score)
    job = workspace.ingest_job(
        {"company": "Example", "title": "Engineer", "posting": "Build Python APIs"}
    )
    worker = Worker(workspace, service)
    worker.start()
    old_thread = worker.thread
    try:
        assert entered.wait(3)
        worker.stop(timeout=0.01)
        worker.start()
        # A restart invalidates the old lease, but cannot abort an HTTP inference.
        # Its successor waits for that request; there is never overlapping inference.
        time.sleep(0.1)
        assert len(calls) == 1
        assert workspace.get_job(job["id"])["score"] is None
        release.set()
        deadline = time.monotonic() + 3
        while workspace.get_job(job["id"])["score"] is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert workspace.get_job(job["id"])["score"] == 65
        release.set()
        old_thread.join(timeout=2)
        assert not old_thread.is_alive()
        assert workspace.get_job(job["id"])["score"] == 65
        assert len(workspace.db.all("SELECT * FROM assessments")) == 1
    finally:
        release.set()
        worker.stop()
