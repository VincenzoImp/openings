"""Practical acquisition invariants: real transport seams, shared gates and queue fairness."""

import json
import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from openings import discovery as module
from openings.collectors import company
from openings.collectors.policy import ProviderDeferred, ProviderPatch, retry_after
from openings.discovery import (
    CollectionWrite,
    DiscoveryService,
    Filters,
    SourceBulk,
    SourceCreate,
    SourcePreview,
    SourceVersion,
    fetch_postings,
)
from openings.errors import DomainError
from openings.worker import Worker
from openings.workspace import Workspace


@pytest.fixture
def collection(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "collection.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    monkeypatch.setattr(module, "public_url", lambda url: url)
    return workspace, service


def policy(service, provider, **changes):
    return service.update_provider(
        provider,
        ProviderPatch(expected_version=service.providers.get(provider)["version"], **changes),
    )


def test_jobcloud_template_body_and_partial_preview_remain_distinct():
    source = {
        "name": "Example search",
        "kind": "jobcloud",
        "config": company.JobCloudConfig(query="engineer", max_details=1).model_dump(),
    }
    listing = {
        "documents": [
            {"job_id": "full", "title": "Engineer", "preview": "Python, SQL"},
            {"job_id": "partial", "title": "Engineer", "preview": "Keyword preview"},
        ]
    }
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        return json.dumps(
            {"template_lead_text": "<p>About us</p>", "template_text": "<p>Build APIs.</p>"}
            if url.endswith("/job/full")
            else listing
        ).encode()

    rows = company.collect(source, request, module.html_text)
    assert "About us" in rows[0]["posting"] and "Build APIs." in rows[0]["posting"]
    assert rows[0]["metadata"]["description_complete"] is True
    assert rows[1]["posting"] == "Keyword preview"
    assert rows[1]["metadata"]["description_complete"] is False
    assert len(calls) == 2
    calls.clear()
    known = {"jobcloud:jobs.ch:full": rows[0]["metadata"]}
    source["detail_checked"] = {key: module.now() for key in known}
    refreshed = company.collect(source, request, module.html_text, known=known)
    full = next(item for item in refreshed if item["source_key"] == "jobcloud:jobs.ch:full")
    assert full["posting"] == ""
    assert full["metadata"]["description_complete"] is True
    assert len(calls) == 2 and not any(url.endswith("/job/full") for url in calls)


def test_only_complete_postings_supply_preserved_body_metadata(collection, monkeypatch):
    workspace, service = collection
    source = service.create_source(
        SourceCreate(name="Example search", kind="jobcloud", config={"query": "engineer"})
    )
    for key, text, metadata in (
        ("full", "Build APIs.", {}),
        ("partial", "Python, SQL", {"description_complete": False}),
        ("placeholder", "-", {}),
    ):
        workspace.ingest_job(
            {
                "source_id": source["id"],
                "source_key": "jobcloud:jobs.ch:" + key,
                "posting": text,
                "metadata": metadata,
            }
        )
    observed = {}
    monkeypatch.setattr(
        module, "fetch_postings", lambda value: observed.update(value["known"]) or []
    )
    service.queue_collection(source["id"])
    task = service.claim_task("test-collector", kind="collect")
    service.run_task(task, "test-collector")
    assert set(observed) == {"jobcloud:jobs.ch:full"}


@pytest.mark.parametrize("header", ["120", "date"])
def test_every_http_attempt_obeys_persisted_cooldown_and_windows(collection, monkeypatch, header):
    workspace, service = collection
    policy(service, "manual", min_interval_seconds=0, max_requests_per_hour=2)
    calls = []
    retry = (
        "120"
        if header == "120"
        else format_datetime(datetime.now(timezone.utc) + timedelta(seconds=120), usegmt=True)
    )

    def send(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(302, headers={"location": "https://example.org/final"})
        return httpx.Response(429, headers={"Retry-After": retry})

    original = httpx.Client
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(send), **kwargs),
    )
    with pytest.raises(ProviderDeferred):
        service.fetch_bytes("https://example.org/start")
    assert len(calls) == 2
    runtime = service.providers.get("manual")["runtime"]
    assert runtime["requests_hour"] == 2 and runtime["last_status"] == 429
    assert runtime["cooldown_until"] > module.now()
    restarted = DiscoveryService(Workspace(workspace.db.path))
    with pytest.raises(ProviderDeferred) as caught:
        restarted.fetch_bytes("https://example.org/next")
    assert caught.value.next_run_at > module.now()
    assert len(calls) == 2
    assert restarted.providers.get("manual")["runtime"]["total_requests"] == 2
    with pytest.raises(DomainError) as conflict:
        restarted.update_provider("manual", ProviderPatch(expected_version=1, enabled=False))
    assert conflict.value.status == 409


def test_jobspy_uses_explicit_instance_transport_for_all_three_providers(collection, monkeypatch):
    from openings._vendor.jobspy import util
    from openings.collectors.jobspy import collect

    _, service = collection
    calls = []

    class Response:
        status_code = 429
        headers = {"Retry-After": "90"}

        def close(self):
            pass

    def attempted(self, method, url, **kwargs):
        calls.append((method, url, kwargs["allow_redirects"]))
        return Response()

    # Test the underlying send boundary. Provider constructors receive the hook;
    # unrelated requests and curl sessions keep their own production classes.
    monkeypatch.setattr(util.requests.Session, "request", attempted)
    monkeypatch.setattr(util.curl_requests.Session, "request", attempted)
    for provider in ("linkedin", "indeed", "glassdoor"):
        budget = service.http_budget(provider)
        rows, diagnostic = collect(
            {
                "query": "software engineer",
                "location": "New York",
                "country": "usa",
                "providers": [provider],
                "results_wanted": 2,
            },
            provider,
            budget,
        )
        assert not rows
        assert diagnostic["requests"] == 1
        assert diagnostic["responses"] == [{"status": 429, "retry_after": "90"}]
        assert diagnostic["state"] == "deferred"
    assert len(calls) == 3 and not any(follows for _, _, follows in calls)


def test_provider_split_bulk_pause_and_explicit_manual_run(collection, monkeypatch):
    workspace, service = collection
    source = service.create_source(
        SourceCreate(
            name="One explicit query",
            kind="jobspy",
            enabled=True,
            config={
                "query": "engineer",
                "location": "Zurich",
                "country": "switzerland",
                "providers": ["linkedin", "indeed", "glassdoor"],
            },
        )
    )
    scheduled = service.queue_collection(source["id"], manual=False)
    assert len(scheduled["task_ids"]) == 3
    assert service.queue_collection(source["id"], manual=False)["task_ids"] == scheduled["task_ids"]
    service.update_collection(CollectionWrite(enabled=False, expected_version=0))
    assert all(service.get_task(task)["state"] == "cancelled" for task in scheduled["task_ids"])
    service.schedule_due()
    assert not service.list_tasks(state="queued")["items"]
    manual = service.queue_collection(source["id"])
    assert len(manual["task_ids"]) == 3
    service.update_collection(CollectionWrite(enabled=False, expected_version=1))
    assert all(service.get_task(task)["state"] == "queued" for task in manual["task_ids"])
    result = service.bulk_sources(
        SourceBulk(
            action="pause",
            items=[
                SourceVersion(id=source["id"], expected_version=source["version"]),
                SourceVersion(id="missing", expected_version=1),
            ],
        )
    )
    assert result["succeeded"] == result["failed"] == 1
    assert not service.get_source(source["id"])["enabled"]
    assert all(service.get_task(task)["state"] == "queued" for task in manual["task_ids"])
    assert service.list_tasks(kind="collect", source_id=source["id"])["total"] == 6
    assert service.get_task(manual["id"])["source_name"] == "One explicit query"
    assert workspace.list_jobs()["total"] == 0


def test_preview_manual_and_worker_share_provider_gate(collection, monkeypatch):
    workspace, service = collection
    policy(service, "greenhouse", min_interval_seconds=0, max_requests_per_hour=1)
    calls = []
    original = httpx.Client

    def send(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": "1",
                        "title": "Engineer",
                        "content": "Build APIs",
                        "absolute_url": "https://example.org/1",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(send), **kwargs),
    )
    preview = service.preview_source(
        SourcePreview(name="Example", kind="greenhouse", config={"board": "example"})
    )
    assert preview["total"] == 0 and preview["diagnostics"][0]["requests"] == 1
    assert preview["diagnostics"][0]["state"] == "deferred"
    assert workspace.list_jobs()["total"] == 0
    source = service.create_source(
        SourceCreate(name="Example", kind="greenhouse", config={"board": "example"})
    )
    task = service.queue_collection(source["id"])
    claimed = service.claim_task("owner", "collect")
    service.run_task(claimed, "owner")
    deferred = service.get_task(task["id"])
    assert deferred["state"] == "queued" and deferred["next_run_at"] > module.now()
    assert deferred["result"]["diagnostics"][0]["state"] == "deferred"
    assert service.get_source(source["id"])["next_run_at"] == deferred["next_run_at"]
    assert len(calls) == 1


def test_cancelled_task_never_reserves_another_request(collection):
    _, service = collection
    active = True
    budget = service.http_budget("greenhouse", active=lambda: active)
    active = False
    with pytest.raises(DomainError) as error:
        budget.before("GET", "https://example.org")
    assert error.value.code == "task_cancelled"
    assert service.providers.get("greenhouse")["runtime"]["total_requests"] == 0


def test_feed_unknown_location_is_retained_when_location_filters_are_set(monkeypatch):
    monkeypatch.setattr(
        module,
        "fetch_bytes",
        lambda *args, **kwargs: (
            b"<rss><channel><item><guid>1</guid><title>API Engineer</title><link>https://example.org/1</link><description>Build APIs</description></item></channel></rss>"
        ),
    )
    rows = fetch_postings(
        {
            "kind": "rss",
            "name": "Example",
            "config": {
                "url": "https://example.org/feed",
                "filters": Filters(locations=["Zurich"]).model_dump(),
            },
        }
    )
    assert len(rows) == 1 and rows[0]["location"] == ""


def test_narrow_company_clients_bound_details_and_preserve_missing_bodies():
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/careers/list"):
            return json.dumps(
                {
                    "result": [
                        {"id": 1, "jobOpeningName": "API Engineer"},
                        {"id": 2, "jobOpeningName": "Analyst"},
                    ]
                }
            ).encode()
        return json.dumps({"result": {"jobOpening": {"description": "Build APIs"}}}).encode()

    source = {
        "name": "Example",
        "kind": "bamboohr",
        "config": {"board": "example", "max_details": 1},
    }
    rows = company.collect(source, request, module.html_text)
    assert len(calls) == 2
    assert len(rows) == 2 and rows[0]["posting"] == "Build APIs" and not rows[1]["posting"]
    calls.clear()
    source["detail_checked"] = {
        key: module.now() for key in ("bamboohr:example:1", "bamboohr:example:2")
    }
    company.collect(
        source, request, module.html_text, known={"bamboohr:example:1", "bamboohr:example:2"}
    )
    assert len(calls) == 1


def test_collection_lane_progresses_during_a_slow_inference_and_queues_successor(
    tmp_path, monkeypatch
):
    workspace = Workspace(tmp_path / "lanes.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    workspace.set_settings("profile", {"summary": "Python engineer"})
    workspace.set_settings("scoring", {"enabled": True})
    entered, release, collected = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def score(config, state):
        calls.append(state["job"]["posting"])
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return {"score": 80, "model": "synthetic", "elapsed_seconds": 0, "response": {}}

    def fetch(source):
        collected.set()
        return [
            {
                "title": "Engineer",
                "company": "Example",
                "posting": "Build changed Python APIs",
                "url": "https://example.org/role",
            }
        ]

    monkeypatch.setattr(module, "score_call", score)
    monkeypatch.setattr(module, "fetch_postings", fetch)
    job = workspace.ingest_job(
        {
            "title": "Engineer",
            "company": "Example",
            "posting": "Build APIs",
            "url": "https://example.org/role",
        }
    )
    source = service.create_source(
        SourceCreate(name="Example", kind="greenhouse", config={"board": "example"})
    )
    worker = Worker(workspace, service)
    worker.start()
    try:
        assert entered.wait(3)
        service.queue_collection(source["id"])
        assert collected.wait(3)
        deadline = time.monotonic() + 2
        while (
            workspace.get_job(job["id"])["posting"] != "Build changed Python APIs"
            or service.list_tasks(kind="score", state="queued")["total"] != 1
        ) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert workspace.get_job(job["id"])["posting"] == "Build changed Python APIs"
        assert service.list_tasks(kind="score", state="queued")["total"] == 1
        assert len(calls) == 1
        release.set()
        deadline = time.monotonic() + 3
        while len(calls) != 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls == ["Build APIs", "Build changed Python APIs"]
        deadline = time.monotonic() + 2
        while workspace.get_job(job["id"])["score_outdated"] and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not workspace.get_job(job["id"])["score_outdated"]
    finally:
        release.set()
        worker.stop()


def test_google_is_explicitly_unsupported_and_retry_after_is_not_guessed(collection):
    _, service = collection
    google = service.providers.get("google")
    assert not google["capability"]["supported"] and not google["policy"]["enabled"]
    with pytest.raises(DomainError) as caught:
        service.update_provider("google", ProviderPatch(expected_version=1, enabled=True))
    assert caught.value.code == "unsupported_provider"
    assert retry_after("not a date", 1) is None
    assert retry_after("3", 1) == 4


def test_actual_requests_and_curl_transports_bound_bodies_and_record_integer_status(collection):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from openings._vendor.jobspy.util import RequestsRotating, TLSRotating

    _, service = collection
    policy(service, "manual", min_interval_seconds=0)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            content = b'{"ok":true}' if self.path == "/small" else b"x" * (8 * 1024 * 1024 + 1)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        for session_class in (RequestsRotating, TLSRotating):
            budget = service.http_budget("manual")
            session = session_class()
            session.transport = budget
            try:
                response = session.get(base + "/small")
                assert response.json() == {"ok": True}
                assert type(response.status_code) is int and response.status_code == 200
                with pytest.raises(DomainError) as caught:
                    session.get(base + "/large")
                assert caught.value.code == "source_too_large"
                assert budget.requests == 2
                assert [row["status"] for row in budget.responses] == [200, 200]
            finally:
                session.close()
        assert service.providers.get("manual")["runtime"]["total_requests"] == 4
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


def test_company_partial_rows_survive_detail_failure_and_keep_prior_metadata(
    collection, monkeypatch
):
    workspace, service = collection
    policy(service, "bamboohr", min_interval_seconds=0)
    source = service.create_source(
        SourceCreate(name="Example", kind="bamboohr", config={"board": "example"})
    )
    calls = []
    original = httpx.Client

    def send(request):
        calls.append(str(request.url))
        if request.url.path.endswith("/list"):
            return httpx.Response(
                200,
                json={
                    "result": [
                        {"id": 1, "jobOpeningName": "API Engineer"},
                        {"id": 2, "jobOpeningName": "Analyst"},
                    ]
                },
            )
        if "/1/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "jobOpening": {"description": "Build APIs", "datePosted": "2026-10-29"}
                    }
                },
            )
        return httpx.Response(429, headers={"Retry-After": "90"})

    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(send), **kwargs),
    )
    queued = service.queue_collection(source["id"])
    task = service.claim_task("worker", "collect")
    service.run_task(task, "worker")
    assert service.get_task(queued["id"])["state"] == "queued"
    assert service.get_task(queued["id"])["result"]["created"] == 1
    job = workspace.list_jobs()["items"][0]
    assert job["date_posted"] == "2026-10-29"
    assert workspace.get_job(job["id"])["posting"] == "Build APIs"
    # Known-detail omission must not clear the previous date or body on refresh.
    old = {"bamboohr:example:1": workspace.get_job(job["id"])["metadata"]}
    rows = company.collect(
        {
            "name": "Example",
            "kind": "bamboohr",
            "config": {"board": "example", "max_results": 1},
            "detail_checked": {"bamboohr:example:1": module.now()},
        },
        lambda *args, **kwargs: json.dumps(
            {"result": [{"id": 1, "jobOpeningName": "API Engineer"}]}
        ).encode(),
        module.html_text,
        known=old,
    )
    refreshed = module.normalize_posting(rows[0])
    assert refreshed["metadata"]["date_posted"] == "2026-10-29"
    updated = workspace.ingest_job(refreshed)
    assert updated["content_version"] == job["content_version"]


def test_all_sources_use_canonical_filter_metadata_and_reject_invalid_query_counts(collection):
    from pydantic import ValidationError

    from openings.collectors.jobspy import JobSpyConfig

    _, service = collection
    row = module.normalize_posting(
        {
            "metadata": {
                "remote": True,
                "published_at": 1793270300000,
                "job_type": ["full-time", "contract"],
            }
        }
    )
    assert row["metadata"]["is_remote"] is True
    assert row["metadata"]["date_posted"] == "2026-10-29"
    assert row["metadata"]["job_type"] == "fulltime"
    assert row["metadata"]["job_types"] == ["fulltime", "contract"]
    for count in (True, 1.2, "20", 100):
        with pytest.raises(ValidationError):
            JobSpyConfig(query="engineer", results_wanted=count)
    auto = service.create_source(
        SourceCreate(name="Example", url="https://jobs.ashbyhq.com/example")
    )
    assert auto["kind"] == "ashby" and auto["config"]["max_results"] == 100


def test_run_now_promotes_scheduled_work_and_long_provider_pause_keeps_a_valid_next_run(collection):
    workspace, service = collection
    source = service.create_source(
        SourceCreate(name="Example", kind="greenhouse", enabled=True, config={"board": "example"})
    )
    scheduled = service.queue_collection(source["id"], manual=False)
    manual = service.queue_collection(source["id"])
    assert manual["id"] == scheduled["id"] and manual["payload"]["manual"] is True
    service.update_collection(CollectionWrite(expected_version=0, enabled=False))
    assert service.get_task(manual["id"])["state"] == "queued"
    policy(service, "greenhouse", enabled=False)
    workspace.db.execute("UPDATE tasks SET attempts=999 WHERE id=?", (manual["id"],))
    task = service.claim_task("worker", "collect")
    service.run_task(task, "worker")
    paused = service.get_task(manual["id"])
    assert paused["state"] == "queued" and paused["next_run_at"] > module.now()
    assert paused["attempts"] == 1000
    assert service.providers.get("greenhouse")["runtime"]["total_requests"] == 0
    policy(service, "greenhouse", enabled=True)
    assert service.get_task(manual["id"])["next_run_at"] <= module.now()


@pytest.mark.asyncio
async def test_slow_mcp_preview_keeps_health_and_other_tools_responsive(tmp_path, monkeypatch):
    from openings.app import create_app

    app = create_app(tmp_path / "responsive.sqlite", start_worker=False)
    entered, release = threading.Event(), threading.Event()

    def slow_preview(value):
        entered.set()
        assert release.wait(3), "The event loop could not release the blocking preview."
        return {"items": [], "total": 0, "preview_limit": 20, "diagnostics": []}

    monkeypatch.setattr(app.state.discovery, "preview_source", slow_preview)
    task = asyncio.create_task(
        app.state.mcp.call_tool(
            "sources_preview", {"value": {"kind": "rss", "url": "https://example.org/feed"}}
        )
    )
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 1), timeout=2)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await asyncio.wait_for(client.get("/health"), timeout=0.5)
        assert response.status_code == 200
        await asyncio.wait_for(app.state.mcp.call_tool("collection_get", {}), timeout=0.5)
        assert not task.done()
    finally:
        release.set()
        await task


def test_manual_score_checks_share_the_worker_inference_slot(collection, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    workspace, service = collection
    workspace.set_settings("profile", {"summary": "Python engineer"})
    workspace.set_settings("scoring", {"enabled": True})
    entered, release = threading.Event(), threading.Event()
    calls = []

    def score(config, state):
        calls.append(state["job"]["posting"])
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        return {"score": 80, "model": "synthetic", "elapsed_seconds": 0, "response": {}}

    monkeypatch.setattr(module, "score_call", score)
    worker = Worker(workspace, service)
    with ThreadPoolExecutor(max_workers=1) as pool:
        manual = pool.submit(service.test_scoring)
        try:
            assert entered.wait(1)
            job = workspace.ingest_job(
                {"title": "Engineer", "company": "Example", "posting": "Queued job"}
            )
            worker.start()
            time.sleep(0.1)
            assert len(calls) == 1
            release.set()
            assert manual.result(timeout=2)["connected"]
            deadline = time.monotonic() + 3
            while workspace.get_job(job["id"])["score"] is None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert calls == ["Build and maintain Python APIs.", "Queued job"]
            assert workspace.get_job(job["id"])["score"] == 80
        finally:
            release.set()
            worker.stop()
