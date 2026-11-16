"""HN "Who is hiring": one job per top-level comment of the latest thread, through the gate."""

import httpx
import pytest

from discovery_fixtures import mock_http, open_gate
from openings.collectors.hnhiring import first_line
from openings.discovery import SourceCreate, SourceTest
from openings.errors import DomainError

THREADS = {
    "hits": [
        {"objectID": "900", "title": "Ask HN: Who wants to be hired? (November 2026)",
         "created_at_i": 1793000100},
        {"objectID": "800", "title": "Ask HN: Who is hiring? (October 2026)",
         "created_at_i": 1790000000},
        {"objectID": "901", "title": "Ask HN: Who is hiring? (November 2026)",
         "created_at_i": 1793000000},
    ]
}  # fmt: skip
THREAD = {
    "id": 901,
    "type": "story",
    "title": "Ask HN: Who is hiring? (November 2026)",
    "children": [
        {
            "id": 1001,
            "type": "comment",
            "author": "example_a",
            "created_at": "2026-11-02T16:00:00.000Z",
            "text": "Northwind Labs | Senior Backend Engineer | Berlin, Germany | ONSITE | "
            "Full-time | €90k - €110k<p>We build synthetic logistics software in Python.",
            "children": [
                {
                    "id": 1002,
                    "type": "comment",
                    "text": "Is this role open to applicants from abroad?",
                    "children": [],
                }
            ],
        },
        {
            "id": 1003,
            "type": "comment",
            "author": "example_b",
            "created_at": "2026-11-02T17:00:00.000Z",
            "text": "Example Robotics (example.org) | Data Scientist | REMOTE (EU) | "
            "https://example.org/jobs<p>Model fleets of synthetic robots.",
            "children": [],
        },
        {"id": 1004, "type": "comment", "text": None, "children": []},
    ],
}


def send_thread(calls):
    def send(request):
        calls.append(str(request.url))
        if request.url.path.endswith("/search_by_date"):
            return httpx.Response(200, json=THREADS)
        if request.url.path.endswith("/items/901"):
            return httpx.Response(200, json=THREAD)
        return httpx.Response(404)

    return send


def test_a_run_admits_each_top_level_comment_once_through_the_gate(collection, monkeypatch):
    workspace, service = collection
    open_gate(service, "hnhiring")
    calls = []
    mock_http(monkeypatch, send_thread(calls))
    source = service.create_source(SourceCreate(name="HN Who is hiring", kind="hnhiring"))
    assert source["config"]["max_results"] == 1000 and source["url"] == ""

    def run():
        queued = service.queue_collection(source["id"])
        service.run_task(service.claim_task("test", kind="collect"), "test")
        task = service.get_task(queued["task_ids"][0])
        assert task["state"] == "succeeded", task
        return task["result"]

    first = run()
    assert first["created"] == 2 and first["received"] == 2
    jobs = {job["company"]: job for job in workspace.list_jobs()["items"]}
    assert set(jobs) == {"Northwind Labs", "Example Robotics"}
    northwind = workspace.get_job(jobs["Northwind Labs"]["id"])
    assert northwind["title"] == "Senior Backend Engineer"
    assert northwind["location"] == "Berlin, Germany"
    assert northwind["url"] == "https://news.ycombinator.com/item?id=1001"
    assert "synthetic logistics" in northwind["posting"]
    assert northwind["metadata"]["source"] == "hnhiring"
    assert jobs["Example Robotics"]["location"] == "REMOTE (EU)"
    # A second run adds nothing, and every request went through the gate.
    second = run()
    assert second["created"] == 0 and second["existing"] == 2
    assert workspace.list_jobs()["total"] == 2
    assert len(calls) == 4
    assert service.providers.get("hnhiring")["runtime"]["total_requests"] == 4
    assert all(call.startswith("https://hn.algolia.com/api/v1/") for call in calls)


def test_a_test_previews_the_thread_and_a_closed_gate_refuses_it(collection, monkeypatch):
    _, service = collection
    open_gate(service, "hnhiring")
    calls = []
    mock_http(monkeypatch, send_thread(calls))
    preview = service.preview_source(SourceTest(kind="hnhiring"))
    assert preview["total"] == 2 and preview["listed"] == 2
    assert [item["title"] for item in preview["items"]] == [
        "Senior Backend Engineer",
        "Data Scientist",
    ]
    assert preview["request_estimate"]["total"] == 2
    service.providers.closed = True
    with pytest.raises(DomainError) as refused:
        service.preview_source(SourceTest(kind="hnhiring"))
    assert refused.value.code == "providers_closed" and len(calls) == 2


def test_the_first_line_names_company_role_place_and_terms():
    head = first_line(
        "Acme Example | Founding Engineer, Platform | Lisbon, Portugal | Hybrid | "
        "Full-time, Contract | $150k + equity | acme.example\nMore text"
    )
    assert head["company"] == "Acme Example"
    assert head["title"] == "Founding Engineer, Platform"
    assert head["location"] == "Lisbon, Portugal"
    assert head["workplace_type"] == "hybrid"
    assert head["employment_type"] == "Full-time, Contract"
    assert head["salary"] == "$150k + equity"
    assert first_line("Example Co | REMOTE")["location"] == "Remote"
    assert first_line("Example Co")["title"] == "Untitled role"
