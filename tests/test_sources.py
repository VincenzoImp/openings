from unittest.mock import patch

import pandas as pd
import pytest

from openings.config import CompanySourceConfig, FeedSourceConfig, parse_config
from openings.sources import CANONICAL_COLUMNS, collect_all
from openings.sources.ats import ashby, greenhouse, lever, smartrecruiters
from openings.sources.base import SourceError, html_to_markdown, location_allowed, to_date
from openings.sources.collect import fetch_company, fetch_feed
from openings.sources.jobspy import to_canonical
from openings.sources.manual import record_from_fields
from tests.conftest import minimal_settings


def test_location_allowed_is_substring_and_accent_insensitive():
    assert location_allowed("Zürich, Switzerland", ["zurich"])
    assert location_allowed("Anything", [])
    assert not location_allowed("Berlin", ["Zurich", "Remote"])


def test_html_to_markdown_unescapes_and_converts():
    assert html_to_markdown("&lt;p&gt;Hi &lt;b&gt;there&lt;/b&gt;&lt;/p&gt;") == "Hi **there**"
    assert html_to_markdown("plain text") == "plain text"
    assert html_to_markdown("") is None


def test_to_date_handles_iso_and_epoch():
    assert str(to_date("2026-09-07T10:00:00Z")) == "2026-09-07"
    assert str(to_date(1788739200000)) == "2026-09-07"
    assert to_date("nope") is None


def test_jobspy_frame_maps_columns_and_keeps_raw():
    frame = pd.DataFrame(
        [
            {
                "site": "linkedin",
                "id": "li-1",
                "title": "T",
                "company": "C",
                "location": "L",
                "interval": "yearly",
            }
        ]
    )
    canonical = to_canonical(frame)
    assert list(canonical.columns) == list(CANONICAL_COLUMNS)
    row = canonical.iloc[0]
    assert row["source"] == "linkedin"
    assert row["external_id"] == "li-1"
    assert row["salary_interval"] == "yearly"
    assert '"site": "linkedin"' in row["raw_json"]


def test_manual_record_defaults_to_manual_source():
    record = record_from_fields(title=" T ", company="C", location="L")
    assert record["source"] == "manual"
    assert record["title"] == "T"
    assert record["raw_json"]


GREENHOUSE = {
    "jobs": [
        {
            "id": 1,
            "title": "Data Engineer",
            "absolute_url": "https://boards.greenhouse.io/x/jobs/1",
            "location": {"name": "Remote - Europe"},
            "content": "&lt;p&gt;Pipelines&lt;/p&gt;",
            "updated_at": "2026-09-01T00:00:00Z",
        },
        {
            "id": 2,
            "title": "Sales",
            "absolute_url": "u",
            "location": {"name": "Berlin"},
            "content": "x",
        },
    ]
}


def test_greenhouse_maps_fields():
    company = CompanySourceConfig(name="X", ats="greenhouse", slug="x")
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE):
        records = greenhouse.fetch(company, None, 5.0)
    assert records[0]["title"] == "Data Engineer"
    assert records[0]["description"] == "Pipelines"
    assert records[0]["source"] == "greenhouse"
    assert str(records[0]["date_posted"]) == "2026-09-01"


def test_lever_builds_description_from_lists():
    payload = [
        {
            "id": "a",
            "text": "Engineer",
            "hostedUrl": "https://jobs.lever.co/x/a",
            "categories": {"location": "Zurich", "commitment": "Full-time"},
            "description": "<p>Intro</p>",
            "lists": [{"text": "Requirements", "content": "<li>Python</li>"}],
            "createdAt": 1757232000000,
            "workplaceType": "remote",
        }
    ]
    company = CompanySourceConfig(name="X", ats="lever", slug="x")
    with patch("openings.sources.ats.lever.http_get_json", return_value=payload):
        records = lever.fetch(company, None, 5.0)
    assert "## Requirements" in records[0]["description"]
    assert records[0]["is_remote"] is True
    assert records[0]["job_type"] == "Full-time"


def test_ashby_prepends_compensation():
    payload = {
        "jobs": [
            {
                "id": "1",
                "title": "SRE",
                "location": "Berlin",
                "secondaryLocations": [{"location": "Remote"}],
                "jobUrl": "https://jobs.ashbyhq.com/x/1",
                "descriptionHtml": "<p>Body</p>",
                "compensation": {"compensationTierSummary": "€80K – €100K"},
                "isRemote": True,
                "publishedAt": "2026-09-02T00:00:00Z",
            }
        ]
    }
    company = CompanySourceConfig(name="X", ats="ashby", slug="x")
    with patch("openings.sources.ats.ashby.http_get_json", return_value=payload):
        records = ashby.fetch(company, None, 5.0)
    assert records[0]["location"] == "Berlin, Remote"
    assert records[0]["description"].startswith("**Compensation:** €80K")


def test_smartrecruiters_pages_and_fetches_details_only_for_kept_rows():
    listing = {
        "totalFound": 2,
        "content": [
            {
                "id": "1",
                "name": "Engineer",
                "location": {"city": "Geneva", "country": "ch"},
                "ref": "https://api/1",
            },
            {
                "id": "2",
                "name": "Nurse",
                "location": {"city": "Lyon", "country": "fr"},
                "ref": "https://api/2",
            },
        ],
    }
    detail = {"jobAd": {"sections": {"jobDescription": {"title": "Role", "text": "<p>Build</p>"}}}}
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return listing if "postings" in url else detail

    company = CompanySourceConfig(
        name="CERN", ats="smartrecruiters", slug="CERN", locations=["Geneva"]
    )
    with patch("openings.sources.ats.smartrecruiters.http_get_json", side_effect=fake):
        records = smartrecruiters.fetch(company, None, 5.0)
    assert [record["title"] for record in records] == ["Engineer"]
    assert records[0]["description"] == "## Role\n\nBuild"
    assert calls == ["https://api.smartrecruiters.com/v1/companies/CERN/postings", "https://api/1"]


def test_fetch_company_isolates_errors(config):
    company = CompanySourceConfig(name="X", ats="greenhouse", slug="x")
    with patch("openings.sources.ats.greenhouse.http_get_json", side_effect=SourceError("boom")):
        result = fetch_company(company, config)
    assert result.stats.failed == 1
    assert result.stats.errors == ["boom"]
    assert result.frame.empty


def test_fetch_company_applies_location_filter(config):
    company = CompanySourceConfig(name="X", ats="greenhouse", slug="x", locations=["Remote"])
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE):
        result = fetch_company(company, config)
    assert list(result.frame["title"]) == ["Data Engineer"]


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Example Jobs</title><link>https://example.com</link>
<item><title>Platform Engineer</title><link>https://example.com/1</link>
<description>&lt;p&gt;Go and Postgres&lt;/p&gt;</description><pubDate>Mon, 07 Sep 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_fetch_feed_parses_rss(config):
    feed = FeedSourceConfig(name="Example", url="https://example.com/jobs.rss")

    class Response:
        content = RSS

    with patch("openings.sources.rss.http_get", return_value=Response()):
        result = fetch_feed(feed, config)
    row = result.frame.iloc[0]
    assert row["title"] == "Platform Engineer"
    assert row["company"] == "Example Jobs"
    assert row["description"] == "Go and Postgres"
    assert row["source"] == "rss"
    assert str(row["date_posted"]) == "2026-09-07"


def test_collect_all_merges_and_dedupes(data_dir):
    data = minimal_settings()
    data["sources"]["companies"] = [
        {"name": "X", "ats": "greenhouse", "slug": "x"},
        {"name": "X", "ats": "lever", "slug": "x"},
    ]
    config = parse_config(data, data_dir=data_dir)
    lever_payload = [
        {
            "id": "a",
            "text": "Data Engineer",
            "categories": {"location": "Remote - Europe"},
            "hostedUrl": "u",
        }
    ]
    with (
        patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE),
        patch("openings.sources.ats.lever.http_get_json", return_value=lever_payload),
    ):
        result = collect_all(config)
    assert result.total_found == 3
    assert result.unique_found == 2  # the Lever row is the same opening as the Greenhouse one
    assert [stat.name for stat in result.stats] == ["greenhouse:x", "lever:x"]
    assert result.errors == []


@pytest.mark.parametrize("value", [None, float("nan"), ""])
def test_frame_from_records_tolerates_missing_values(value):
    from openings.sources.base import frame_from_records

    frame = frame_from_records(
        [{"title": "T", "company": "C", "location": "L", "description": value}]
    )
    assert list(frame.columns) == list(CANONICAL_COLUMNS)
