"""Practical acquisition invariants: real transport seams, shared gates and queue fairness."""

import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from discovery_fixtures import mock_http, patch_discovery
from openings.collectors import company
from openings.collectors.jobspy import JobSpyConfig
from openings.collectors.policy import (
    MAX_RETRY_AFTER,
    ProviderDeferred,
    ProviderPatch,
    retry_after,
)
from openings.common import now
from openings.discovery import (
    CollectionWrite,
    DiscoveryService,
    Filters,
    SourceBulk,
    SourceCreate,
    SourcePreview,
    SourceVersion,
    feeds,
)
from openings.discovery.feeds import fetch_postings
from openings.errors import DomainError
from openings.posting import matches_filters
from openings.workspace import Workspace


@pytest.fixture
def collection(collection, monkeypatch):
    # Provider sessions connect only to checked addresses; every host is the local test server.
    patch_discovery(monkeypatch, "public_addresses", lambda host, port: ["127.0.0.1"])
    return collection


def policy(service, provider, **changes):
    return service.update_provider(
        provider,
        ProviderPatch(expected_version=service.providers.get(provider)["version"], **changes),
    )


def test_only_complete_postings_supply_preserved_body_metadata(collection, monkeypatch):
    workspace, service = collection
    source = service.create_source(
        SourceCreate(name="Example board", kind="greenhouse", config={"board": "example"})
    )
    for key, text, metadata in (
        ("full", "Build APIs.", {}),
        ("partial", "Python, SQL", {"description_complete": False}),
        ("placeholder", "-", {}),
    ):
        workspace.ingest_job(
            {
                "source_id": source["id"],
                "source_key": "greenhouse:example:" + key,
                "posting": text,
                "metadata": metadata,
            }
        )
    observed = {}
    patch_discovery(
        monkeypatch, "fetch_postings", lambda value: observed.update(value["known"]) or []
    )
    service.queue_collection(source["id"])
    task = service.claim_task("test-collector", kind="collect")
    service.run_task(task, "test-collector")
    assert set(observed) == {"greenhouse:example:full"}


def test_every_http_attempt_obeys_persisted_cooldown(collection, monkeypatch):
    workspace, service = collection
    policy(service, "manual", min_interval_seconds=0)
    calls = []
    # An HTTP-date Retry-After is parsed by retry_after (tested below).
    retry = "120"

    def send(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(302, headers={"location": "https://example.org/final"})
        return httpx.Response(429, headers={"Retry-After": retry})

    mock_http(monkeypatch, send)
    with pytest.raises(ProviderDeferred):
        service.fetch_bytes("https://example.org/start")
    assert len(calls) == 2
    runtime = service.providers.get("manual")["runtime"]
    assert runtime["requests_hour"] == 2 and runtime["last_status"] == 429
    assert runtime["cooldown_until"] > now()
    restarted = DiscoveryService(Workspace(workspace.db.path))
    with pytest.raises(ProviderDeferred) as caught:
        restarted.fetch_bytes("https://example.org/next")
    assert caught.value.next_run_at > now()
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
        headers = {"Retry-After": "90"}  # noqa: RUF012 - read-only test double

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
    assert all(service.get_task(task)["state"] == "queued" for task in scheduled["task_ids"])
    service.cancel_run(scheduled["run_id"])
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
    policy(service, "greenhouse", min_interval_seconds=0)
    calls = []

    def send(request):
        calls.append(str(request.url))
        return httpx.Response(429, headers={"Retry-After": "120"})

    mock_http(monkeypatch, send)
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
    assert deferred["state"] == "queued" and deferred["next_run_at"] > now()
    assert deferred["result"]["diagnostics"][0]["state"] == "deferred"
    assert service.get_source(source["id"])["next_run_at"] == deferred["next_run_at"]
    assert len(calls) == 1


def test_feed_unknown_location_is_retained_when_location_filters_are_set(monkeypatch):
    patch_discovery(
        monkeypatch,
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


def test_location_and_title_filters_match_whole_terms():
    # Remote does not widen a specific geography.
    filters = {"locations": ["Canada", "Remote"]}
    for place in ("Remote - USA", "Remote EMEA", "Remote"):
        assert not matches_filters({"title": "Engineer", "location": place}, filters)
    for place in ("Toronto, Canada", "Remote Worldwide"):
        assert matches_filters({"title": "Engineer", "location": place}, filters)
    assert matches_filters(
        {"title": "Engineer", "location": "Remote", "metadata": {"eligible_countries": ["Canada"]}},
        filters,
    )
    # Excluded title terms match whole words before the role filters.
    filters = {"titles": ["engineer", "analyst"], "exclude_titles": ["sales", "SAP"]}
    assert not matches_filters({"title": "Senior Sales Engineer"}, filters)
    assert not matches_filters({"title": "SAP CRM Analyst"}, filters)
    assert matches_filters({"title": "Wholesales Data Engineer"}, filters)
    assert matches_filters({"title": "Sapling Research Engineer"}, filters)
    assert not matches_filters({"title": "Sales Director"}, {"exclude_titles": ["sales"]})
    assert matches_filters({"title": "Backend Engineer"}, {"exclude_titles": []})


def test_company_clients_fetch_all_details_and_reuse_complete_cached_bodies():
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
        "config": {"board": "example"},
    }
    rows = company.collect(source, request, feeds.html_text)
    assert len(calls) == 3
    assert len(rows) == 2 and all(row["posting"] == "Build APIs" for row in rows)
    calls.clear()
    source["detail_checked"] = {key: now() for key in ("bamboohr:example:1", "bamboohr:example:2")}
    company.collect(
        source, request, feeds.html_text, known={"bamboohr:example:1", "bamboohr:example:2"}
    )
    assert len(calls) == 1


def test_the_gate_refuses_cancelled_work_unknown_providers_and_guessed_retry_after(collection):
    _, service = collection
    active = True
    budget = service.http_budget("greenhouse", active=lambda: active)
    active = False
    with pytest.raises(DomainError) as error:
        budget.before("GET", "https://example.org")
    assert error.value.code == "task_cancelled"
    assert service.providers.get("greenhouse")["runtime"]["total_requests"] == 0

    assert "google" not in {row["id"] for row in service.providers.list()["items"]}
    with pytest.raises(DomainError) as caught:
        service.update_provider("google", ProviderPatch(expected_version=1, enabled=True))
    assert caught.value.code == "not_found"
    assert retry_after("not a date", 1) is None
    assert retry_after("3", 1) == 4
    later = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=120)
    moment = later.timestamp() - 120
    assert retry_after(format_datetime(later, usegmt=True), moment) == later.timestamp()


def test_a_server_pause_is_at_most_a_day_and_the_owner_can_lift_it(collection):
    _, service = collection
    day = MAX_RETRY_AFTER
    assert retry_after("99999999999", 1) == retry_after("1e300", 1) == 1 + day
    assert retry_after("nan", 1) is retry_after("-5", 1) is None
    assert retry_after("Fri, 31 Dec 9999 23:59:59 GMT", 1) == 1 + day
    budget = service.http_budget("greenhouse")
    budget.after(429, {"Retry-After": "1e300"})
    paused = service.providers.get("greenhouse")
    until = datetime.fromisoformat(paused["runtime"]["cooldown_until"])
    assert until <= datetime.now(UTC) + timedelta(seconds=day)
    lifted = service.update_provider(
        "greenhouse", ProviderPatch(expected_version=paused["version"]), clear_cooldown=True
    )
    assert lifted["runtime"]["cooldown_until"] is None
    service.http_budget("greenhouse").before("GET", "https://boards.greenhouse.io/example")


def test_actual_requests_and_curl_transports_bound_bodies_and_record_integer_status(
    collection, local_server
):
    from openings._vendor.jobspy.util import RequestsRotating, TLSRotating

    _, service = collection
    policy(service, "manual", min_interval_seconds=0)
    local_server.bodies = {"/small": b'{"ok":true}', "/large": b"x" * (8 * 1024 * 1024 + 1)}
    base = f"http://127.0.0.1:{local_server.server_address[1]}"
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


def test_company_partial_rows_survive_detail_failure_and_keep_prior_metadata(
    collection, monkeypatch
):
    workspace, service = collection
    policy(service, "bamboohr", min_interval_seconds=0)
    source = service.create_source(
        SourceCreate(name="Example", kind="bamboohr", config={"board": "example"})
    )
    calls = []

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

    mock_http(monkeypatch, send)
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
            "detail_checked": {"bamboohr:example:1": now()},
        },
        lambda *args, **kwargs: json.dumps(
            {"result": [{"id": 1, "jobOpeningName": "API Engineer"}]}
        ).encode(),
        feeds.html_text,
        known=old,
    )
    refreshed = feeds.normalize_posting(rows[0])
    assert refreshed["metadata"]["date_posted"] == "2026-10-29"
    updated = workspace.ingest_job(refreshed)
    assert updated["content_version"] == job["content_version"]


def test_all_sources_use_canonical_filter_metadata_and_reject_invalid_query_counts(collection):
    from pydantic import ValidationError

    from openings.collectors.jobspy import JobSpyConfig

    _, service = collection
    row = feeds.normalize_posting(
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
    assert paused["state"] == "queued" and paused["next_run_at"] > now()
    assert paused["attempts"] == 1000
    assert service.providers.get("greenhouse")["runtime"]["total_requests"] == 0
    policy(service, "greenhouse", enabled=True)
    assert service.get_task(manual["id"])["next_run_at"] <= now()


@pytest.mark.asyncio
async def test_slow_mcp_preview_keeps_health_and_other_tools_responsive(app, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def slow_preview(value):
        entered.set()
        assert release.wait(3), "The event loop could not release the blocking preview."
        return {"items": [], "total": 0, "preview_limit": 20, "diagnostics": []}

    monkeypatch.setattr(app.state.discovery, "preview_source", slow_preview)
    task = asyncio.create_task(
        app.state.mcp.call_tool(
            "sources_run", {"preview": True, "kind": "rss", "url": "https://example.org/feed"}
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


def test_a_search_has_no_country_unless_one_is_chosen():
    linkedin = JobSpyConfig.model_validate({"query": "engineer", "providers": ["linkedin"]})
    assert linkedin.country == ""
    chosen = JobSpyConfig.model_validate(
        {"query": "engineer", "country": "switzerland", "providers": ["indeed"]}
    )
    assert chosen.country == "switzerland"
    for providers in (["indeed"], ["linkedin", "glassdoor"]):
        with pytest.raises(ValueError, match="search one country's site"):
            JobSpyConfig.model_validate({"query": "engineer", "providers": providers})
