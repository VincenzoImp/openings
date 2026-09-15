import json
from types import SimpleNamespace
from xml.etree import ElementTree
from unittest.mock import patch

import pandas as pd
import pytest

from openings.config import CompanySourceConfig, FeedSourceConfig, parse_config
from openings.sources import CANONICAL_COLUMNS, collect_all
from openings.sources.ats import (
    ashby,
    bamboohr,
    breezy,
    greenhouse,
    joincom,
    lever,
    oracle,
    personio,
    recruitee,
    rippling,
    smartrecruiters,
    workable,
    workday,
)
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


def test_fetch_company_isolates_an_unexpected_payload_shape(config):
    """A vendor that changes its payload raises TypeError or AttributeError
    inside the adapter, not SourceError. Catching only SourceError meant one
    such company discarded every other source's rows in the same run."""
    company = CompanySourceConfig(name="X", ats="greenhouse", slug="x")
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=["not", "a", "dict"]):
        result = fetch_company(company, config)
    assert result.stats.failed == 1
    assert result.stats.errors and "AttributeError" in result.stats.errors[0]


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
    # Distinct postings stay distinct here; the database merges cross-board mirrors on upsert.
    assert result.unique_found == 3
    assert [stat.name for stat in result.stats] == ["greenhouse:x", "lever:x"]
    assert result.errors == []
    assert result.every_task_failed is False


def test_collect_all_dedupes_repeated_postings(data_dir):
    data = minimal_settings()
    data["sources"]["companies"] = [{"name": "X", "ats": "greenhouse", "slug": "x"}]
    config = parse_config(data, data_dir=data_dir)
    twice = {"jobs": GREENHOUSE["jobs"] + GREENHOUSE["jobs"][:1]}
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=twice):
        result = collect_all(config)
    assert result.total_found == 3 and result.unique_found == 2


def test_fetch_company_keeps_rows_without_location(config):
    company = CompanySourceConfig(name="X", ats="greenhouse", slug="x", locations=["Remote"])
    payload = {"jobs": [{"id": 3, "title": "Anywhere", "absolute_url": "u3", "location": {}}]}
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=payload):
        result = fetch_company(company, config)
    assert list(result.frame["title"]) == ["Anywhere"]


def test_smartrecruiters_skips_details_for_known_ids():
    listing = {
        "totalFound": 1,
        "content": [
            {"id": "1", "name": "Engineer", "location": {"city": "Geneva"}, "ref": "https://api/1"}
        ],
    }
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return listing

    company = CompanySourceConfig(name="CERN", ats="smartrecruiters", slug="CERN")
    with patch("openings.sources.ats.smartrecruiters.http_get_json", side_effect=fake):
        records = smartrecruiters.fetch(company, None, 5.0, known=lambda ids: {"1"})
    assert records[0]["description"] is None and len(calls) == 1


@pytest.mark.parametrize("value", [None, float("nan"), ""])
def test_frame_from_records_tolerates_missing_values(value):
    from openings.sources.base import frame_from_records

    frame = frame_from_records(
        [{"title": "T", "company": "C", "location": "L", "description": value}]
    )
    assert list(frame.columns) == list(CANONICAL_COLUMNS)


def test_job_types_share_one_vocabulary():
    from openings.sources.base import normalize_job_type

    assert normalize_job_type("Full-time") == "fulltime"
    assert normalize_job_type("FullTime") == "fulltime"
    assert normalize_job_type("fulltime") == "fulltime"
    assert normalize_job_type("Part time") == "parttime"
    assert normalize_job_type("parttime, fulltime") == "parttime"
    assert normalize_job_type("Contract") == "contract"
    assert normalize_job_type("Intern") == "internship"
    assert normalize_job_type("Working Student") == "internship"
    assert normalize_job_type("Fixed-term") == "temporary"
    assert normalize_job_type("Volunteer") == "volunteer"
    assert normalize_job_type("Board member") == "other"
    assert normalize_job_type("Not Applicable") is None
    assert normalize_job_type(None) is None
    assert normalize_job_type("") is None


def test_keep_drops_postings_older_than_the_feed_age():
    from datetime import date

    from openings.sources.collect import _keep

    today = date(2026, 9, 8)
    fresh = {"title": "Engineer", "location": "Zurich", "date_posted": "2026-08-20"}
    old = {"title": "Engineer", "location": "Zurich", "date_posted": "2021-05-12"}
    undated = {"title": "Engineer", "location": "Zurich", "date_posted": None}
    assert _keep(fresh, [], (), 60, today)
    assert not _keep(old, [], (), 60, today)
    assert _keep(undated, [], (), 60, today)
    assert _keep(old, [], (), None, today)


def test_workday_splits_the_board_address_and_fetches_details():
    listing = {
        "total": 2,
        "jobPostings": [
            {
                "title": "Platform Engineer",
                "externalPath": "/job/Zurich/Platform_1",
                "locationsText": "Zurich",
            },
            {"title": "Nurse", "externalPath": "/job/Lyon/Nurse_2", "locationsText": "Lyon"},
        ],
    }
    detail = {
        "jobPostingInfo": {
            "jobDescription": "<p>Run it</p>",
            "location": "Zurich",
            "startDate": "2026-09-01",
            "externalUrl": "https://abb.wd3.myworkdayjobs.com/ext/job/Zurich/Platform_1",
        }
    }
    posts, gets = [], []

    def fake_post(url, **kwargs):
        posts.append(url)
        return listing

    def fake_get(url, **kwargs):
        gets.append(url)
        return detail

    company = CompanySourceConfig(
        name="ABB", ats="workday", slug="abb.wd3.myworkdayjobs.com/ext", locations=["Zurich"]
    )
    with (
        patch("openings.sources.ats.workday.http_post_json", side_effect=fake_post),
        patch("openings.sources.ats.workday.http_get_json", side_effect=fake_get),
    ):
        records = workday.fetch(company, None, 5.0)

    assert [record["title"] for record in records] == ["Platform Engineer"]
    assert records[0]["description"] == "Run it"
    assert posts == ["https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/ext/jobs"]
    # The Lyon row is filtered before any detail fetch, so only one GET happens.
    assert gets == ["https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/ext/job/Zurich/Platform_1"]


def test_workday_rejects_a_slug_without_a_site():
    company = CompanySourceConfig(name="X", ats="workday", slug="abb.wd3.myworkdayjobs.com")
    with pytest.raises(SourceError):
        workday.fetch(company, None, 5.0)


def _join_page(state):
    return (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps({"props": {"pageProps": {"initialState": state}}})
        + "</script></html>"
    )


def test_joincom_reads_the_embedded_state_and_merges_the_job_page():
    listing = {
        "jobs": {
            "items": [
                {
                    "id": 1,
                    "idParam": "1-platform-engineer",
                    "title": "Platform Engineer",
                    "city": {"cityName": "Zug", "countryName": "Switzerland"},
                    "createdAt": "2026-09-01T00:00:00.000Z",
                }
            ]
        }
    }
    detail = {"job": {"intro": "<p>Who we are</p>", "tasks": "<p>Build</p>"}}
    pages = [_join_page(listing), _join_page(detail)]

    def fake_get(url, **kwargs):
        return SimpleNamespace(text=pages.pop(0))

    company = CompanySourceConfig(
        name="Enshift", ats="joincom", slug="enshift", locations=["Switzerland"]
    )
    with patch("openings.sources.ats.joincom.http_get", side_effect=fake_get):
        records = joincom.fetch(company, None, 5.0)

    assert records[0]["title"] == "Platform Engineer"
    assert records[0]["location"] == "Zug, Switzerland"
    assert records[0]["description"] == "Who we are\n\n## Tasks\n\nBuild"
    assert records[0]["job_url"] == "https://join.com/companies/enshift/1-platform-engineer"


def test_joincom_reports_a_changed_page_shape_instead_of_returning_nothing():
    company = CompanySourceConfig(name="X", ats="joincom", slug="x")
    with patch(
        "openings.sources.ats.joincom.http_get",
        return_value=SimpleNamespace(text="<html>no payload</html>"),
    ):
        with pytest.raises(SourceError):
            joincom.fetch(company, None, 5.0)


def test_workable_needs_no_detail_fetch():
    payload = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "shortcode": "ABC",
                "city": "Zurich",
                "country": "Switzerland",
                "telecommuting": True,
                "description": "<p>Ship</p>",
                "published_on": "2026-09-01",
                "url": "https://apply.workable.com/j/ABC",
            }
        ]
    }
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return payload

    company = CompanySourceConfig(name="X", ats="workable", slug="x")
    with patch("openings.sources.ats.workable.http_get_json", side_effect=fake):
        records = workable.fetch(company, None, 5.0)

    assert records[0]["description"] == "Ship"
    assert records[0]["location"] == "Zurich, Switzerland (Remote)"
    assert records[0]["is_remote"] is True
    assert len(calls) == 1


def test_rippling_skips_details_for_known_ids():
    listing = [{"uuid": "u1", "name": "SRE", "workLocation": {"label": "Zurich"}}]
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return listing if url.endswith("/jobs") else {"description": "<p>x</p>"}

    company = CompanySourceConfig(name="X", ats="rippling", slug="x")
    with patch("openings.sources.ats.rippling.http_get_json", side_effect=fake):
        records = rippling.fetch(company, None, 5.0, lambda ids: {"u1"})

    assert records[0]["description"] is None
    assert calls == ["https://api.rippling.com/platform/api/ats/v1/board/x/jobs"]


def test_bamboohr_builds_the_public_url_when_the_detail_has_none():
    listing = {
        "result": [{"id": "7", "jobOpeningName": "Engineer", "location": {"city": "Zurich"}}]
    }

    def fake(url, **kwargs):
        return listing if url.endswith("/careers/list") else {"result": {"jobOpening": {}}}

    company = CompanySourceConfig(name="X", ats="bamboohr", slug="acme")
    with patch("openings.sources.ats.bamboohr.http_get_json", side_effect=fake):
        records = bamboohr.fetch(company, None, 5.0)

    assert records[0]["job_url"] == "https://acme.bamboohr.com/careers/7"


def test_every_known_ats_has_an_adapter():
    from openings.config import KNOWN_ATS
    from openings.sources.ats import FETCHERS

    assert set(FETCHERS) == set(KNOWN_ATS)


def test_oracle_pages_the_nested_listing_and_fetches_details():
    listing = {
        "items": [
            {
                "TotalJobsCount": 2,
                "requisitionList": [
                    {"Id": "1", "Title": "Data Engineer", "PrimaryLocation": "Zurich"},
                    {"Id": "2", "Title": "Nurse", "PrimaryLocation": "Lyon"},
                ],
            }
        ]
    }
    detail = {"items": [{"ExternalDescriptionStr": "<p>Build</p>"}]}
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return listing if "JobRequisitions" in url else detail

    company = CompanySourceConfig(
        name="Acme", ats="oracle", slug="acme.fa.em2.oraclecloud.com/CX_5", locations=["Zurich"]
    )
    with patch("openings.sources.ats.oracle.http_get_json", side_effect=fake):
        records = oracle.fetch(company, None, 5.0)

    assert [record["title"] for record in records] == ["Data Engineer"]
    assert records[0]["description"] == "Build"
    # The Lyon row is filtered before any detail fetch, so only one detail call.
    assert sum("Details" in call for call in calls) == 1


def test_oracle_rejects_a_slug_without_a_site():
    company = CompanySourceConfig(name="X", ats="oracle", slug="acme.oraclecloud.com")
    with pytest.raises(SourceError):
        oracle.fetch(company, None, 5.0)


PERSONIO_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
  <position>
    <id>4103</id>
    <office>Zurich</office>
    <department>Engineering</department>
    <name>Backend Engineer</name>
    <employmentType>permanent</employmentType>
    <seniority>experienced</seniority>
    <schedule>full-time</schedule>
    <createdAt>2026-05-31T12:14:07+0200</createdAt>
    <jobDescriptions>
      <jobDescription><name>Tasks</name><value>&lt;p&gt;Build&lt;/p&gt;</value></jobDescription>
    </jobDescriptions>
  </position>
  <position>
    <id>4104</id>
    <office>Munich</office>
    <name>Sales</name>
  </position>
</workzag-jobs>"""


def test_personio_parses_its_own_schema_and_filters_by_office():
    root = ElementTree.fromstring(PERSONIO_XML)
    company = CompanySourceConfig(name="Acme", ats="personio", slug="acme", locations=["Zurich"])
    with patch("openings.sources.ats.personio.http_get_xml", return_value=root):
        records = personio.fetch(company, None, 5.0)

    assert [record["title"] for record in records] == ["Backend Engineer"]
    assert records[0]["description"] == "## Tasks\n\nBuild"
    assert records[0]["job_url"] == "https://acme.jobs.personio.de/job/4103"
    assert records[0]["job_type"] == "fulltime"
    assert records[0]["job_level"] == "experienced"


def test_recruitee_needs_no_detail_fetch():
    payload = {
        "offers": [
            {
                "id": 1,
                "title": "Platform Engineer",
                "description": "<p>Run it</p>",
                "requirements": "<p>Go</p>",
                "location": "Zurich, Switzerland",
                "careers_url": "https://acme.recruitee.com/o/platform-engineer",
                "published_at": "2026-09-01 10:00:00 UTC",
                "remote": True,
            }
        ]
    }
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return payload

    company = CompanySourceConfig(name="Acme", ats="recruitee", slug="acme")
    with patch("openings.sources.ats.recruitee.http_get_json", side_effect=fake):
        records = recruitee.fetch(company, None, 5.0)

    assert records[0]["description"] == "Run it\n\n## Requirements\n\nGo"
    assert records[0]["is_remote"] is True
    assert len(calls) == 1


def test_breezy_reports_no_description_because_the_feed_carries_none():
    payload = [
        {
            "id": "abc",
            "name": "Engineer",
            "url": "https://acme.breezy.hr/p/abc-engineer",
            "published_date": "2026-09-01T00:00:00Z",
            "location": {"name": "Zurich, CH", "is_remote": True},
            "company": {"name": "Acme"},
        }
    ]
    company = CompanySourceConfig(name="Acme", ats="breezy", slug="acme")
    with patch("openings.sources.ats.breezy.http_get_json", return_value=payload):
        records = breezy.fetch(company, None, 5.0)

    assert records[0]["title"] == "Engineer"
    assert records[0]["location"] == "Zurich, CH (Remote)"
    # Breezy publishes no copy anywhere public; the record is title-only by design.
    assert records[0]["description"] is None


def test_jobcloud_turns_structured_language_skills_into_one_canonical_line():
    from openings.sources.jobcloud import _record

    document = {
        "job_id": "abc",
        "title": "Backend Engineer",
        "company_name": "Acme",
        "place": "Zurich",
        "preview": "short preview",
        "publication_date": "2026-09-07T08:17:05+02:00",
        "language_skills": [{"language": "de", "level": 3}, {"language": "en", "level": 2}],
        "_links": {"detail_de": {"href": "https://www.jobs.ch/de/x/detail/abc/"}},
    }
    record = _record(document, "www.jobs.ch", None)
    assert record["description"].startswith(
        "Required languages: German (level 3), English (level 2)"
    )
    assert record["job_url"] == "https://www.jobs.ch/de/x/detail/abc/"
    assert record["external_id"] == "abc"


def test_jobcloud_without_language_skills_leaves_the_description_alone():
    from openings.sources.jobcloud import _record

    record = _record({"job_id": "a", "title": "T", "preview": "body"}, "www.jobs.ch", None)
    assert record["description"] == "body"


# One real posting URL per adapter, of the shape that adapter actually builds,
# and a second URL for a *different* posting on the same board. Name parity
# alone is not enough: the first version of this guard asserted only that every
# adapter appeared in the table, and passed while the Workday pattern captured
# the city instead of the requisition, collapsing every Zurich job at one
# employer into a single row.
_POSTING_URLS: dict[str, tuple[str, str]] = {
    "greenhouse": (
        "https://job-boards.greenhouse.io/acme/jobs/4717008005",
        "https://job-boards.greenhouse.io/acme/jobs/4717008006",
    ),
    "lever": (
        "https://jobs.lever.co/acme/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "https://jobs.lever.co/acme/ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee",
    ),
    "ashby": (
        "https://jobs.ashbyhq.com/acme/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "https://jobs.ashbyhq.com/acme/ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee",
    ),
    "smartrecruiters": (
        "https://jobs.smartrecruiters.com/Acme/743999",
        "https://jobs.smartrecruiters.com/Acme/744000",
    ),
    "workday": (
        "https://abb.wd3.myworkdayjobs.com/ext/job/Zurich-Switzerland/Software-Engineer_R1",
        "https://abb.wd3.myworkdayjobs.com/ext/job/Zurich-Switzerland/Data-Engineer_R2",
    ),
    "joincom": (
        "https://join.com/companies/acme/16668437-bess-project-engineer",
        "https://join.com/companies/acme/16668438-other-role",
    ),
    "workable": (
        "https://apply.workable.com/acme/j/abcdef1234/",
        "https://apply.workable.com/acme/j/abcdef1235/",
    ),
    "rippling": (
        "https://ats.rippling.com/acme/jobs/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "https://ats.rippling.com/acme/jobs/ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee",
    ),
    "bamboohr": ("https://acme.bamboohr.com/careers/7", "https://acme.bamboohr.com/careers/8"),
    "oracle": (
        "https://eipb.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_5/job/1147",
        "https://eipb.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_5/job/1148",
    ),
    "personio": (
        "https://acme.jobs.personio.de/job/4103",
        "https://acme.jobs.personio.de/job/4104",
    ),
    "recruitee": (
        "https://acme.recruitee.com/o/platform-engineer",
        "https://acme.recruitee.com/o/data-engineer",
    ),
    "breezy": (
        "https://acme.breezy.hr/p/aaaaaaaaaaaa-engineer",
        "https://acme.breezy.hr/p/bbbbbbbbbbbb-engineer",
    ),
}


def test_every_ats_has_a_canonical_url_pattern_that_actually_matches():
    """The 0.3.0 adapters shipped without a pattern at all; 0.4.0 shipped two
    that never matched the URL their adapter builds."""
    from openings.models import canonical_url
    from openings.sources.ats import FETCHERS

    missing = sorted(set(FETCHERS) - set(_POSTING_URLS))
    assert not missing, f"no sample posting URL for {missing}"

    for ats, (first, _second) in _POSTING_URLS.items():
        key = canonical_url(first)
        assert key and key.startswith(f"{ats}:"), f"{ats}: {first} canonicalized to {key}"


def test_two_postings_on_one_board_never_share_a_key():
    """A pattern that captures the wrong path segment passes the name-parity
    check and silently merges unrelated openings."""
    from openings.models import canonical_url

    for ats, (first, second) in _POSTING_URLS.items():
        assert canonical_url(first) != canonical_url(second), f"{ats} collapses two postings"


def test_one_posting_seen_twice_shares_a_key():
    """Adapters build a URL from the payload with a constructed fallback; both
    shapes must reduce to the same key or one opening becomes two postings."""
    from openings.models import canonical_url

    pairs = [
        (
            "https://apply.workable.com/acme/j/abcdef1234/",
            "https://apply.workable.com/j/abcdef1234",
        ),
        (
            "https://acme.bamboohr.com/careers/7",
            "https://acme.bamboohr.com/careers/7?source=indeed",
        ),
        (
            "https://www.jobs.ch/de/stellenangebote/detail/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/",
            "https://www.jobs.ch/en/vacancies/detail/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/?x=1",
        ),
    ]
    for first, second in pairs:
        assert canonical_url(first) == canonical_url(second), first


def test_http_get_xml_refuses_a_document_that_declares_entities():
    """Entity expansion is the reason; this parses XML from arbitrary hosts."""
    from openings.sources.base import http_get_xml

    bomb = SimpleNamespace(
        content=b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]><lolz>&lol;</lolz>'
    )
    with patch("openings.sources.base.http_get", return_value=bomb):
        with pytest.raises(SourceError):
            http_get_xml("https://example.test/xml", user_agent=None, timeout=5.0)


def test_jobcloud_keeps_the_neighbouring_towns_the_board_returned():
    """`locations` is the board's search parameter, not a post-filter. The board
    resolves a city to its commuting region, so filtering its answers again by
    city name would throw away exactly what the operator asked for."""
    from openings.config import JobCloudConfig
    from openings.sources import jobcloud

    config = parse_config(minimal_settings())
    config.sources.jobcloud = JobCloudConfig(
        enabled=True,
        host="www.jobs.ch",
        queries=["x"],
        locations=["Zurich"],
        rows=3,
        max_pages=1,
        max_details=0,
    )
    payload = {
        "documents": [
            {"job_id": "1", "title": "A", "place": "Zürich"},
            {"job_id": "2", "title": "B", "place": "Rüti ZH"},
            {"job_id": "3", "title": "C", "place": "Bülach"},
        ]
    }
    with (
        patch("openings.sources.jobcloud.http_get_json", return_value=payload),
        patch("openings.sources.jobcloud.time.sleep"),
    ):
        result = jobcloud.run_jobcloud(config)

    assert result.stats.rows == 3


def test_jobcloud_clamps_paging_to_the_module_ceiling():
    """A generous max_pages in someone's settings must not become thousands of
    requests against a board with thousands of result pages."""
    from openings.config import JobCloudConfig
    from openings.sources import jobcloud

    calls = []

    def fake(url, **kwargs):
        calls.append(kwargs.get("params", {}).get("page"))
        return {"documents": [{"job_id": f"{len(calls)}", "title": "T", "place": "Zurich"}]}

    config = parse_config(minimal_settings())
    config.sources.jobcloud = JobCloudConfig(
        enabled=True, host="www.jobs.ch", queries=["x"], rows=1, max_pages=9999, max_details=0
    )
    with (
        patch("openings.sources.jobcloud.http_get_json", side_effect=fake),
        patch("openings.sources.jobcloud.time.sleep"),
    ):
        result = jobcloud.run_jobcloud(config)

    assert len(calls) == jobcloud.MAX_PAGES
    assert result.stats.rows == jobcloud.MAX_PAGES
