"""Synthetic join.com public page layouts expose complete job descriptions."""

import json

import pytest

from openings.collectors import company
from openings.discovery import html_text
from openings.errors import DomainError


@pytest.mark.parametrize("state_key", ["pageData", "initialState"])
def test_joincom_embedded_pages_preserve_jobs_and_bound_detail_requests(state_key):
    base = "https://join.com/companies/example"
    calls = []
    listing = {
        "job": None,
        "jobs": {
            "items": [
                {
                    "id": 11,
                    "idParam": "11-api-engineer",
                    "title": "API Engineer",
                    "city": {"cityName": "Example City", "countryName": "Example Country"},
                    "workplaceType": "REMOTE",
                },
                {"id": 12, "idParam": "12-analyst", "title": "Analyst"},
            ]
        },
    }
    detail = {
        "job": {
            "title": "Senior API Engineer",
            "description": "<p>Build APIs.</p><p>Test APIs.</p>",
        }
    }

    def request(url):
        calls.append(url)
        payload = listing if url == base else detail
        embedded = json.dumps({"props": {"pageProps": {state_key: payload}}})
        return f'<script id="__NEXT_DATA__" type="application/json">{embedded}</script>'.encode()

    source = {
        "name": "Example",
        "kind": "joincom",
        "config": {"board": "example"},
    }
    rows = company.collect(source, request, html_text)
    assert calls == [base, base + "/11-api-engineer", base + "/12-analyst"]
    assert [row["source_key"] for row in rows] == ["joincom:example:11", "joincom:example:12"]
    assert rows[0]["title"] == "Senior API Engineer"
    assert rows[0]["posting"] == "Build APIs.\nTest APIs."
    assert rows[0]["location"] == "Example City, Example Country"
    assert rows[0]["metadata"]["remote"] is True
    assert (
        rows[1]["title"] == "Senior API Engineer"
        and rows[1]["posting"] == "Build APIs.\nTest APIs."
    )

    calls.clear()
    source["detail_checked"] = {row["source_key"]: company.now() for row in rows}
    company.collect(source, request, html_text, known={row["source_key"] for row in rows})
    assert calls == [base]

    listing["jobs"]["items"] = []
    assert company.collect(source, request, html_text) == []
    listing["jobs"]["items"] = {}
    with pytest.raises(DomainError) as failure:
        company.collect(source, request, html_text)
    assert failure.value.code == "source_format"
