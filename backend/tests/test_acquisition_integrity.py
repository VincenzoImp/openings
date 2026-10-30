"""Exact identities, concurrent review, persisted freshness and safe format upgrades."""

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from openings import discovery as module
from openings.collectors import company
from openings.collectors.policy import ProviderPatch
from openings.discovery import DiscoveryService, SourceCreate
from openings.errors import DomainError
from openings.workspace import Workspace


def test_cross_provider_redirect_is_rejected_before_destination_request(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "gate.sqlite")
    discovery = DiscoveryService(workspace)
    discovery.update_provider("manual", ProviderPatch(expected_version=1, min_interval_seconds=0))
    discovery.update_provider("linkedin", ProviderPatch(expected_version=1, enabled=False))
    monkeypatch.setattr(module, "public_url", lambda url: url)
    calls = []
    target = "https://www.linkedin.com/jobs/view/123"

    def send(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": target})

    original = httpx.Client
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(send), **kwargs),
    )
    with pytest.raises(DomainError) as error:
        discovery.fetch_bytes("https://example.org/alias")
    assert error.value.code == "provider_redirect" and target in error.value.message
    assert calls == ["https://example.org/alias"]
    assert discovery.providers.get("linkedin")["runtime"]["total_requests"] == 0
    # The requests/curl transport uses the identical per-attempt check.
    with pytest.raises(DomainError):
        discovery.http_budget("manual").request(
            lambda *args, **kwargs: pytest.fail("must not send"), "GET", target
        )


def test_detail_refresh_rotates_across_pages_and_sources_without_material_timestamp(
    tmp_path, monkeypatch
):
    workspace = Workspace(tmp_path / "fresh.sqlite")
    discovery = DiscoveryService(workspace)
    workspace.discovery = discovery
    source = discovery.create_source(
        SourceCreate(
            name="Example",
            kind="smartrecruiters",
            config={"board": "example", "max_results": 101, "max_details": 1},
        )
    )
    clock = ["2026-01-01T00:00:00.000000+00:00"]
    monkeypatch.setattr(company, "now", lambda: clock[0])
    calls = []
    body = ["Build APIs"]

    def fetch(url, **kwargs):
        parts = urlsplit(url)
        if parts.query:
            offset = int(parse_qs(parts.query)["offset"][0])
            return json.dumps(
                {
                    "content": [
                        {"id": str(i), "name": "Engineer"}
                        for i in range(offset, min(offset + 100, 101))
                    ]
                }
            ).encode()
        calls.append(parts.path.rsplit("/", 1)[-1])
        return json.dumps({"jobAd": {"sections": {"jobDescription": {"text": body[0]}}}}).encode()

    monkeypatch.setattr(module, "fetch_bytes", fetch)

    def run(selected=source):
        discovery.queue_collection(selected["id"])
        task = discovery.claim_task("owner", "collect")
        discovery.run_task(task, "owner")
        assert discovery.get_task(task["id"])["state"] == "succeeded"

    # Seed successful freshness for the first page. The next run must reach page 2.
    for i in range(100):
        item = workspace.ingest_job(
            {
                "source_key": f"smartrecruiters:example:{i}",
                "url": f"https://jobs.smartrecruiters.com/example/{i}",
                "title": "Engineer",
                "company": "Example",
                "posting": body[0],
                "metadata": module.normalize_posting(
                    {
                        "metadata": {
                            "source": "smartrecruiters",
                            "ats": "smartrecruiters",
                            "board": "example",
                            "external_id": str(i),
                        }
                    }
                )["metadata"],
            }
        )
        workspace.db.execute(
            "INSERT INTO posting_details VALUES(?,?,?)",
            (f"smartrecruiters:example:{i}", item["id"], clock[0]),
        )
    run()
    assert calls == ["100"]
    # Overlapping saved sources reuse the same provider/board cache.
    second = discovery.create_source(
        SourceCreate(
            name="Example",
            kind="smartrecruiters",
            config={"board": "example", "max_results": 101, "max_details": 1},
        )
    )
    run(second)
    assert calls == ["100"]
    job = workspace.get_job(
        workspace.db.one(
            "SELECT job_id FROM job_identities WHERE identity='smartrecruiters:example:0'"
        )["job_id"]
    )
    version = job["content_version"]
    clock[0] = "2026-01-03T00:00:00.000000+00:00"
    workspace.db.execute(
        "UPDATE posting_details SET checked_at=? WHERE identity<>?",
        (clock[0], "smartrecruiters:example:0"),
    )
    run()
    assert calls == ["100", "0"]
    assert workspace.get_job(job["id"])["content_version"] == version
    body[0] = "Build a different system"
    clock[0] = "2026-01-05T00:00:00.000000+00:00"
    workspace.db.execute(
        "UPDATE posting_details SET checked_at=? WHERE identity<>?",
        (clock[0], "smartrecruiters:example:1"),
    )
    run()
    assert calls[-1] == "1"  # oldest check, not the first listing row again
    updated = workspace.get_job(
        workspace.db.one(
            "SELECT job_id FROM job_identities WHERE identity='smartrecruiters:example:1'"
        )["job_id"]
    )
    assert updated["posting"] == body[0]


def test_greenhouse_filters_metadata_before_bounded_detail_requests(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "greenhouse.sqlite")
    discovery = DiscoveryService(workspace)
    source = discovery.create_source(
        SourceCreate(
            name="Example",
            kind="greenhouse",
            config={"board": "example", "max_details": 1},
            filters=module.Filters(titles=["Engineer"]),
        )
    )
    calls = []

    def fetch(url, **kwargs):
        calls.append(url)
        assert "content=true" not in url
        if url.endswith("/jobs"):
            return json.dumps(
                {
                    "jobs": [
                        {"id": i, "title": "Analyst", "absolute_url": f"https://example.org/{i}"}
                        for i in range(500)
                    ]
                    + [{"id": 501, "title": "Engineer", "absolute_url": "https://example.org/501"}]
                }
            ).encode()
        return json.dumps({"content": "Build APIs"}).encode()

    monkeypatch.setattr(module, "fetch_bytes", fetch)
    discovery.queue_collection(source["id"])
    task = discovery.claim_task("owner", "collect")
    discovery.run_task(task, "owner")
    assert calls == [
        "https://boards-api.greenhouse.io/v1/boards/example/jobs",
        "https://boards-api.greenhouse.io/v1/boards/example/jobs/501",
    ]
    assert workspace.list_jobs()["total"] == 1
    assert workspace.get_job(workspace.list_jobs()["items"][0]["id"])["posting"] == "Build APIs"


def test_collection_retains_other_results_and_bounds_identity_conflict_report(
    tmp_path, monkeypatch
):
    workspace = Workspace(tmp_path / "conflicts.sqlite")
    discovery = DiscoveryService(workspace)
    source = discovery.create_source(
        SourceCreate(name="Example", kind="bamboohr", config={"board": "example"})
    )
    first = workspace.ingest_job({"source_key": "bamboohr:example:1", "posting": "Build APIs"})
    second = workspace.ingest_job({"url": "https://example.org/duplicate"})
    workspace.db.execute(
        "INSERT INTO job_identities VALUES(?,?)", ("bamboohr:example:1", second["id"])
    )
    rows = [{"source_key": "bamboohr:example:1", "posting": "Ambiguous posting"} for _ in range(25)]
    rows.insert(10, {"source_key": "bamboohr:example:new", "posting": "A new complete job"})
    monkeypatch.setattr(module, "fetch_postings", lambda source: rows)
    queued = discovery.queue_collection(source["id"])
    task = discovery.claim_task("owner", "collect")
    discovery.run_task(task, "owner")
    result = discovery.get_task(queued["id"])
    assert result["state"] == "failed" and "Other results were retained" in result["error"]
    assert result["result"]["created"] == 1 and result["result"]["conflict_count"] == 25
    assert len(result["result"]["identity_conflicts"]) == 20
    assert set(result["result"]["identity_conflicts"][0]["job_ids"]) == {first["id"], second["id"]}
    assert workspace.list_jobs()["total"] == 3


def test_later_listing_page_failure_preserves_earlier_metadata(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "partial-pages.sqlite")
    discovery = DiscoveryService(workspace)
    source = discovery.create_source(
        SourceCreate(
            name="Example",
            kind="smartrecruiters",
            config={"board": "example", "max_results": 101, "max_details": 1},
        )
    )

    def fetch(url, **kwargs):
        offset = int(parse_qs(urlsplit(url).query)["offset"][0])
        if offset:
            raise DomainError(502, "source_http", "Later listing page failed")
        return json.dumps(
            {"content": [{"id": str(i), "name": "Engineer"} for i in range(100)]}
        ).encode()

    monkeypatch.setattr(module, "fetch_bytes", fetch)
    discovery.queue_collection(source["id"])
    task = discovery.claim_task("owner", "collect")
    discovery.run_task(task, "owner")
    result = discovery.get_task(task["id"])
    assert result["state"] == "queued" and result["result"]["created"] == 100
    assert workspace.list_jobs()["total"] == 100


def test_bounded_description_is_explicitly_incomplete():
    source = {
        "kind": "bamboohr",
        "name": "Example",
        "config": {"board": "example", "max_details": 1},
    }

    def request(url, **kwargs):
        payload = (
            {"result": [{"id": 1, "jobOpeningName": "Engineer"}]}
            if url.endswith("/list")
            else {"result": {"jobOpening": {"description": "A" * 200001}}}
        )
        return json.dumps(payload).encode()

    item = company.collect(source, request, module.html_text)[0]
    assert len(item["posting"]) == 200000 and item["metadata"]["description_complete"] is False


def test_bamboohr_filters_before_result_and_detail_caps():
    source = {
        "kind": "bamboohr",
        "name": "Example",
        "config": {
            "board": "example",
            "max_results": 1,
            "max_details": 1,
            "filters": {"titles": ["Engineer"], "locations": ["Zurich"]},
        },
    }
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        payload = (
            {
                "result": [
                    {"id": i, "jobOpeningName": "Analyst", "location": {"city": "New York"}}
                    for i in range(400)
                ]
                + [{"id": 400, "jobOpeningName": "Engineer", "location": {"city": "Zurich"}}]
            }
            if url.endswith("/list")
            else {"result": {"jobOpening": {"description": "Build APIs"}}}
        )
        return json.dumps(payload).encode()

    rows = company.collect(source, request, module.html_text)
    assert len(rows) == 1 and rows[0]["title"] == "Engineer"
    assert calls == [
        "https://example.bamboohr.com/careers/list",
        "https://example.bamboohr.com/careers/400/detail",
    ]


def test_workday_filters_later_metadata_pages_and_reports_candidate_cap():
    source = {
        "kind": "workday",
        "name": "Example",
        "config": {
            "board": "example.wd5.myworkdayjobs.com/Careers",
            "max_results": 1,
            "max_candidates": 200,
            "max_details": 1,
            "filters": {"titles": ["Engineer"]},
        },
    }
    listing_calls = []
    details = []

    def request(url, *, body=None, **kwargs):
        if body is not None:
            offset = body["offset"]
            listing_calls.append(offset)
            return json.dumps(
                {
                    "jobPostings": [
                        {
                            "externalPath": f"/job/{i}",
                            "title": "Engineer" if i == 150 else "Analyst",
                        }
                        for i in range(offset, offset + 20)
                    ]
                }
            ).encode()
        details.append(url)
        return json.dumps({"jobPostingInfo": {"jobDescription": "Build APIs"}}).encode()

    rows = company.collect(source, request, module.html_text)
    assert listing_calls == list(range(0, 200, 20)) and len(details) == 1
    assert rows[0]["source_key"].endswith("/job/150")
    assert source["candidate_capped"] is True


@pytest.mark.asyncio
async def test_manual_import_reports_cross_provider_destination_url(tmp_path, monkeypatch):
    from openings.fetching import read_posting

    discovery = DiscoveryService(Workspace(tmp_path / "manual-redirect.sqlite"))
    target = "https://www.linkedin.com/jobs/view/123"

    def blocked(*args, **kwargs):
        raise DomainError(422, "provider_redirect", f"Import the destination directly: {target}")

    monkeypatch.setattr(discovery, "fetch_bytes", blocked)
    result = await read_posting("https://example.org/job", discovery)
    assert result["metadata"]["extraction"] == "needs_text"
    assert target in result["metadata"]["extraction_error"]
