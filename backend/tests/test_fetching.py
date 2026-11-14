"""URL imports through the shared gate: redirects, size limits, encodings and timeouts."""

import gzip
import json

import httpx
import pytest

from discovery_fixtures import mock_http, open_gate
from openings.discovery import network
from openings.errors import DomainError
from openings.fetching import (
    ats_endpoint,
    ats_posting,
    complete_input,
    read_posting,
    structured_posting,
)
from openings.models import JobInput

PAGE = "https://careers.example.test/jobs/1"


def page(node, head=""):
    return f'<html><head>{head}<script type="application/ld+json">{json.dumps(node)}</script></head></html>'


def job(**changes):
    return {
        "@type": "JobPosting",
        "title": "Platform Engineer",
        "description": "<p>Build reliable APIs.</p>",
        "hiringOrganization": {"name": "Synthetic Works"},
        **changes,
    }


@pytest.fixture
def web(collection, monkeypatch):
    """A synthetic web behind the real provider gate; `routes` maps URL to a response."""
    _, service = collection
    open_gate(service, "manual", "greenhouse", "lever", "ashby")
    service.routes, service.calls = {}, []

    def send(request):
        service.calls.append(str(request.url))
        answer = service.routes[str(request.url)]
        if isinstance(answer, Exception):
            raise answer
        return answer

    mock_http(monkeypatch, send)
    return service


def runtime(service, provider="manual"):
    return service.providers.get(provider)["runtime"]


async def test_redirects_are_gated_per_hop_and_stop_at_another_provider_or_a_loop(web):
    web.routes = {
        PAGE: httpx.Response(302, headers={"location": "/jobs/1/view"}),
        PAGE + "/view": httpx.Response(303, headers={"location": "https://jobs.example.test/1"}),
        "https://jobs.example.test/1": httpx.Response(200, text=page(job())),
    }
    result = await read_posting(PAGE, web)
    assert result["posting"] == "Build reliable APIs."
    assert result["company"] == "Synthetic Works"
    assert result["metadata"]["extraction"] == "jobposting-jsonld"
    assert web.calls == [PAGE, PAGE + "/view", "https://jobs.example.test/1"]
    assert runtime(web)["total_requests"] == 3

    # A redirect into another provider stops before that provider's request.
    target = "https://www.linkedin.com/jobs/view/7"
    web.calls.clear()
    web.routes = {PAGE: httpx.Response(301, headers={"location": target})}
    result = await read_posting(PAGE, web)
    assert result["metadata"]["extraction"] == "needs_text"
    assert target in result["metadata"]["extraction_error"]
    assert web.calls == [PAGE]
    assert runtime(web, "linkedin")["total_requests"] == 0
    # The requests/curl transport refuses the same address before sending.
    with pytest.raises(DomainError):
        web.http_budget("manual").request(lambda *_, **__: pytest.fail("Sent."), "GET", target)

    # Loops and redirects without a location stay incomplete.
    web.calls.clear()
    web.routes = {
        PAGE: httpx.Response(302, headers={"location": PAGE}),
        PAGE + "/blank": httpx.Response(302),
    }
    looped = await read_posting(PAGE, web)
    assert looped["metadata"]["extraction"] == "needs_text" and "posting" not in looped
    assert web.calls == [PAGE] * 5 and runtime(web)["total_requests"] == 3 + 1 + 5
    blank = await read_posting(PAGE + "/blank", web)
    assert blank["metadata"]["extraction"] == "needs_text"
    assert web.calls[5:] == [PAGE + "/blank"]


async def test_pages_are_bounded_and_decoded_before_extraction(web):
    padding = "<!-- " + "x" * 2_000_000 + " -->"
    web.routes = {
        PAGE: httpx.Response(200, text=page(job()) + padding),
        # A small compressed body is still bounded by its decoded size.
        PAGE + "/packed": httpx.Response(
            200,
            content=gzip.compress((page(job()) + padding).encode()),
            headers={"content-encoding": "gzip"},
        ),
        PAGE + "/long": httpx.Response(
            200,
            text=page(
                job(
                    title="T" * 500,
                    description="word " * 50_000,
                    hiringOrganization={"name": "C" * 400},
                    jobLocation={"address": "L" * 600},
                )
            ),
        ),
    }
    for url in (PAGE, PAGE + "/packed"):
        refused = await read_posting(url, web)
        assert refused["metadata"]["extraction"] == "needs_text" and "posting" not in refused
    assert len(web.routes[PAGE + "/packed"].headers["content-length"]) <= 5
    bounded = await read_posting(PAGE + "/long", web)
    assert [len(bounded[key]) for key in ("title", "company", "location", "posting")] == [
        400,
        300,
        500,
        200_000,
    ]

    # Escaped, UTF-8, BOM, Latin-1 and UTF-16 pages read alike.
    node = job(
        title="Ingénieur·e plateforme",
        description="&lt;p&gt;Zürich &amp;amp; Genève&lt;/p&gt;&lt;p&gt;Größe: 12 Personen&lt;/p&gt;",
        jobLocation={"address": {"addressLocality": "Zürich", "addressCountry": "CH"}},
    )
    literal = f'<script type="application/ld+json">{json.dumps(node, ensure_ascii=False)}</script>'
    web.routes = {
        PAGE + "/escaped": httpx.Response(200, content=page(node).encode("ascii")),
        PAGE + "/utf8": httpx.Response(200, content=literal.encode()),
        PAGE + "/bom": httpx.Response(200, content=b"\xef\xbb\xbf" + literal.encode()),
        PAGE + "/latin": httpx.Response(
            200, content=('<meta charset="iso-8859-1">' + literal).encode("iso-8859-1")
        ),
        PAGE + "/utf16": httpx.Response(200, content=literal.encode("utf-16")),
    }
    for url in web.routes:
        result = await read_posting(url, web)
        assert result["title"] == "Ingénieur·e plateforme", url
        assert result["posting"] == "Zürich & Genève\nGröße: 12 Personen", url
        assert result["location"] == "Zürich, CH", url


async def test_timeouts_are_recorded_by_the_gate_and_an_ats_timeout_falls_back(web):
    web.routes = {
        PAGE: httpx.ReadTimeout("The read timed out."),
        PAGE + "/connect": httpx.ConnectTimeout("The connection timed out."),
    }
    for url, error in ((PAGE, "ReadTimeout"), (PAGE + "/connect", "ConnectTimeout")):
        result = await read_posting(url, web)
        assert result["metadata"]["extraction"] == "needs_text" and "posting" not in result
        assert runtime(web)["last_error"] == error and runtime(web)["last_status"] is None
    assert runtime(web)["total_requests"] == 2

    # An ATS API timeout falls back to the page under the same provider gate.
    url = "https://boards.greenhouse.io/example/jobs/42"
    api = "https://boards-api.greenhouse.io/v1/boards/example/jobs/42"
    web.calls.clear()
    web.routes = {api: httpx.ReadTimeout("slow"), url: httpx.Response(200, text=page(job()))}
    result = await read_posting(url, web)
    assert result["metadata"]["extraction"] == "jobposting-jsonld"
    assert web.calls == [api, url]
    assert runtime(web, "greenhouse")["total_requests"] == 2
    assert runtime(web)["total_requests"] == 2

    web.routes[api] = httpx.Response(200, content=b"<html>maintenance</html>")
    assert (await read_posting(url, web))["metadata"]["extraction"] == "jobposting-jsonld"


async def test_throttled_import_is_deferred_with_a_durable_cooldown(web):
    url = "https://jobs.lever.co/example/abc"
    api = "https://api.lever.co/v0/postings/example/abc?mode=json"
    web.routes = {api: httpx.Response(429, headers={"retry-after": "300"})}
    value = JobInput(url=url, title="Kept title", metadata={"note": "kept"})
    result = await complete_input(value, web)
    # The page is not requested while the provider asks to wait; manual input is preserved.
    assert web.calls == [api]
    assert result.title == "Kept title" and not result.posting
    assert result.metadata == {
        "extraction": "deferred",
        "extraction_error": "Lever: provider cooldown.",
        "note": "kept",
    }
    assert runtime(web, "lever")["cooldown_until"]
    again = await complete_input(value, web)
    assert again.metadata["extraction"] == "deferred" and web.calls == [api]


async def test_complete_input_fills_only_missing_fields(web):
    web.routes = {PAGE: httpx.Response(200, text=page(job(jobLocation="Remote, Europe")))}
    filled = await complete_input(JobInput(url=PAGE, company="Entered Company"), web)
    assert filled.company == "Entered Company" and filled.title == "Platform Engineer"
    assert filled.location == "Remote, Europe" and filled.posting == "Build reliable APIs."
    pasted = JobInput(url=PAGE, posting="Pasted text.")
    assert await complete_input(pasted, web) is pasted
    assert await complete_input(JobInput(title="No link"), web) == JobInput(title="No link")
    assert web.calls == [PAGE]


def test_ats_urls_map_to_public_api_endpoints_and_payloads_to_postings():
    assert ats_endpoint("https://job-boards.greenhouse.io/acme co/jobs/12/apply") == (
        "greenhouse",
        "https://boards-api.greenhouse.io/v1/boards/acme%20co/jobs/12",
        "12",
    )
    assert ats_endpoint("https://jobs.eu.lever.co/acme/a-b") == (
        "lever",
        "https://api.eu.lever.co/v0/postings/acme/a-b?mode=json",
        "a-b",
    )
    assert ats_endpoint("https://jobs.ashbyhq.com/acme/id-1") == (
        "ashby",
        "https://api.ashbyhq.com/posting-api/job-board/acme?includeCompensation=true",
        "id-1",
    )
    for url in (
        "https://boards.greenhouse.io/acme",
        "https://jobs.lever.co/acme",
        "https://jobs.ashbyhq.com/acme",
        "https://example.test/acme/jobs/12",
        "not a url",
    ):
        assert ats_endpoint(url) is None

    # Their payloads become plain postings.
    greenhouse = ats_posting(
        "greenhouse",
        json.dumps(
            {
                "title": "Engineer",
                "location": {"name": "Zürich"},
                "content": "&lt;p&gt;Build &amp;amp; run.&lt;/p&gt;",
            }
        ).encode("utf-16"),
        "1",
    )
    assert greenhouse["posting"] == "Build & run." and greenhouse["location"] == "Zürich"
    assert ats_posting("greenhouse", b'{"title":"Engineer","location":null}', "1")["posting"] == ""

    lever = ats_posting(
        "lever",
        json.dumps(
            {
                "text": "Engineer",
                "description": "<p>Intro</p>",
                "lists": [{"text": "Requirements", "content": "<li>Python</li>"}, "ignored"],
                "additionalPlain": "Benefits",
                "categories": {"location": "Remote", "commitment": "Full-time"},
                "workplaceType": "remote",
            }
        ),
        "abc",
    )
    assert lever["posting"] == "Intro\n\nRequirements\nPython\n\nBenefits"
    assert lever["location"] == "Remote" and lever["metadata"]["job_type"] == "Full-time"

    board = json.dumps(
        {
            "jobs": [
                {"id": "other", "title": "Other", "descriptionPlain": "No"},
                {
                    "id": "id-1",
                    "title": "Engineer",
                    "location": "Berlin",
                    "descriptionHtml": "<p>Build APIs.</p>",
                    "isRemote": True,
                },
            ]
        }
    )
    ashby = ats_posting("ashby", board, "id-1")
    assert ashby["title"] == "Engineer" and ashby["posting"] == "Build APIs."
    assert ashby["metadata"]["is_remote"] is True
    assert ats_posting("ashby", board, "missing") == {}
    assert ats_posting("lever", "[]", "abc") == {}


def test_structured_data_is_found_in_nested_graphs_and_bad_blocks_are_skipped():
    body = (
        '<script type="application/ld+json">{not json</script>'
        '<script type="application/ld+json">'
        + json.dumps([{"@type": "WebSite"}, {"@type": "JobPosting", "description": " "}])
        + "</script>"
        + page(
            {
                "@graph": [
                    {"@type": "Organization", "name": "Ignored"},
                    {
                        "mainEntity": job(
                            **{"@type": ["Thing", "JobPosting"]},
                            hiringOrganization="Synthetic Works",
                            jobLocationType="TELECOMMUTE",
                            jobLocation=[
                                {"address": {"addressLocality": "Bern", "addressRegion": "BE"}},
                                {"address": "Remote, Switzerland"},
                                {"name": "No address"},
                                "Lausanne",
                                {"address": {"postalCode": "8000"}},
                            ],
                        )
                    },
                ]
            }
        )
    )
    result = structured_posting(body)
    assert result["title"] == "Platform Engineer" and result["company"] == ""
    # Places without a usable address add nothing; plain-text places are kept.
    assert result["location"] == "Bern, BE; Remote, Switzerland; Lausanne"
    assert result["metadata"]["is_remote"] is True
    assert structured_posting(page(job(jobLocation="Geneva")))["location"] == "Geneva"
    assert structured_posting(page(job(jobLocation={"name": "Head office"})))["location"] == ""
    assert structured_posting("<html><p>Verify you are human</p></html>") == {}


def test_a_public_fetch_without_a_provider_budget_fails_closed(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("No connection may be attempted without a budget.")

    monkeypatch.setattr(network.httpx, "Client", unexpected)
    assert network.HTTP_BUDGET.get() is None
    with pytest.raises(RuntimeError, match="no provider budget"):
        network.fetch_bytes("https://example.org/jobs")
