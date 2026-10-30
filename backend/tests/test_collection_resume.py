"""Acquisition resumes after bounded batches without refetching listing pages."""

import json

from openings.collectors import company, jobspy
from openings.collectors.policy import ProviderBudget, ProviderPatch, ProviderStore
from openings.discovery import html_text
from openings.posting import matches_filters
from openings.workspace import Workspace


def test_company_details_continue_without_relisting_or_refetching_completed_bodies():
    checkpoint, requests = {}, []
    source = {
        "name": "Example",
        "kind": "greenhouse",
        "config": {"board": "example", "max_details": 1},
        "checkpoint": checkpoint,
    }

    def request(url):
        requests.append(url)
        if url.endswith("/jobs"):
            return json.dumps(
                {
                    "jobs": [
                        {"id": i, "title": "Engineer", "absolute_url": f"https://example.com/{i}"}
                        for i in range(1, 4)
                    ]
                }
            ).encode()
        return json.dumps({"content": "<p>Build reliable applications.</p>"}).encode()

    first = company.collect(source, request, html_text)
    assert sum(bool(row["posting"]) for row in first) == 1
    assert checkpoint["pending_details"] == 2 and not checkpoint["complete"]
    second = company.collect(source, request, html_text)
    assert sum(bool(row["posting"]) for row in second) == 2
    final = company.collect(source, request, html_text)
    assert all(row["posting"] for row in final) and checkpoint["complete"]
    assert len(requests) == 4 and len(set(requests)) == 4
    assert "responses" not in checkpoint


def test_zero_detail_budget_finishes_metadata_only_without_continuation():
    checkpoint = {}
    rows = company.collect(
        {
            "name": "Example",
            "kind": "greenhouse",
            "config": {"board": "example", "max_details": 0},
            "checkpoint": checkpoint,
        },
        lambda url: b'{"jobs":[{"id":1,"title":"Engineer"}]}',
        html_text,
    )
    assert checkpoint["complete"] and checkpoint["pending_details"] == 0
    assert rows[0]["metadata"]["description_complete"] is False


def test_empty_description_retries_are_finite_and_keep_a_partial_result():
    checkpoint, calls = {}, []

    def request(url):
        calls.append(url)
        return b'{"jobs":[{"id":1,"title":"Engineer"}]}' if url.endswith("/jobs") else b"{}"

    source = {
        "name": "Example",
        "kind": "greenhouse",
        "config": {"board": "example"},
        "checkpoint": checkpoint,
    }
    for _ in range(3):
        rows = company.collect(source, request, html_text)
    assert checkpoint["complete"] and checkpoint["unavailable_descriptions"] == 1
    assert len(calls) == 4 and rows[0]["metadata"]["description_status"] == "unavailable"


def test_linkedin_description_budget_resumes_metadata_checkpoint(tmp_path, monkeypatch):
    import openings._vendor.jobspy.linkedin as provider

    store = ProviderStore(Workspace(tmp_path / "resume.sqlite").db)
    store.update(
        "linkedin",
        ProviderPatch(expected_version=1, min_interval_seconds=0, max_requests_per_run=3),
    )
    calls = []
    cards = "".join(
        f'<div class="base-search-card" data-entity-urn="urn:li:jobPosting:{i}"><h3 class="base-search-card__title">Engineer</h3><h4 class="base-search-card__subtitle">Example</h4><span class="job-search-card__location">New York, NY</span></div>'
        for i in range(15)
    )

    class Response:
        status_code = 200

        def __init__(self, url, text):
            self.url, self.text = url, text

    class Session:
        def __init__(self, budget):
            self.budget = budget

        def get(self, url, **kwargs):
            self.budget.before("GET", url)
            calls.append(url)
            return Response(
                url,
                "".join(
                    cards.split("</div>")[
                        int(kwargs.get("params", {}).get("start", 0)) : int(
                            kwargs.get("params", {}).get("start", 0)
                        )
                        + 10
                    ]
                )
                if "seeMore" in url
                else '<div class="show-more-less-html__markup">Build reliable software and APIs.</div>',
            )

        def close(self):
            pass

    monkeypatch.setattr(
        provider, "create_session", lambda *args, transport=None, **kwargs: Session(transport)
    )
    source = {"checkpoint": {}}
    config = {"query": "engineer", "providers": ["linkedin"], "results_wanted": 15}
    for batch in range(6):
        rows, _ = jobspy.collect(
            config, "linkedin", ProviderBudget(store, "linkedin", f"batch-{batch}"), source=source
        )
    assert source["checkpoint"]["complete"]
    assert len(rows) == 15 and all(row["posting"] for row in rows)
    assert sum("seeMore" in url for url in calls) == 2 and len(calls) == 17


def test_remote_location_filter_does_not_expand_specific_geography():
    filters = {"locations": ["Canada", "Remote"]}
    for place in ("Remote - USA", "Remote EMEA", "Remote"):
        assert not matches_filters({"title": "Engineer", "location": place}, filters)
    for place in ("Toronto, Canada", "Remote Worldwide"):
        assert matches_filters({"title": "Engineer", "location": place}, filters)
    assert matches_filters(
        {"title": "Engineer", "location": "Remote", "metadata": {"eligible_countries": ["Canada"]}},
        filters,
    )


def test_workday_page_resume_reuses_prior_pages_after_provider_deferral():
    from openings.collectors.policy import ProviderDeferred

    calls, checkpoint = [], {}
    blocked = True

    def request(url, *, body=None, **kwargs):
        nonlocal blocked
        offset = body["offset"]
        calls.append(offset)
        if offset == 20 and blocked:
            blocked = False
            raise ProviderDeferred("workday", "provider_hour_budget")
        rows = [
            {"title": "Engineer", "externalPath": f"/job/{i}", "locationsText": "Canada"}
            for i in range(offset, min(offset + 20, 21))
        ]
        return json.dumps({"jobPostings": rows}).encode()

    source = {
        "name": "Example",
        "kind": "workday",
        "config": {
            "board": "example.wd1.myworkdayjobs.com/careers",
            "max_candidates": 40,
            "max_details": 0,
        },
        "checkpoint": checkpoint,
    }
    first = company.collect(source, request, html_text)
    assert len(first) == 20 and not checkpoint["complete"]
    final = company.collect(source, request, html_text)
    assert len(final) == 21 and checkpoint["complete"]
    assert calls == [0, 20, 20]
