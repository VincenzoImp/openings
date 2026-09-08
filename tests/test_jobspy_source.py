from unittest.mock import patch

import pandas as pd

from openings.config import JobSpyConfig, ThrottlingConfig, parse_config
from openings.sources.base import CANONICAL_COLUMNS
from openings.sources.jobspy import _Throttle, run_jobspy, search_single_query, to_canonical
from tests.conftest import minimal_settings

JOBSPY_COLUMNS = [
    "site",
    "id",
    "title",
    "company",
    "location",
    "job_url",
    "description",
    "date_posted",
    "job_type",
    "is_remote",
    "job_level",
    "min_amount",
    "max_amount",
    "currency",
    "interval",
    "company_url",
]


def jobspy_frame(*rows: dict) -> pd.DataFrame:
    base = {
        "site": "linkedin",
        "id": "li-1",
        "title": "Software Engineer",
        "company": "Acme",
        "location": "Remote",
        "job_url": "https://example.com/1",
        "description": "Software engineer building Python services.",
        "date_posted": "2026-09-07",
        "job_type": "fulltime",
        "is_remote": True,
        "job_level": None,
        "min_amount": 100000.0,
        "max_amount": 120000.0,
        "currency": "USD",
        "interval": "yearly",
        "company_url": "https://example.com",
    }
    return pd.DataFrame([{**base, **row} for row in rows] or [base], columns=JOBSPY_COLUMNS)


def jobspy_config(data_dir, **overrides):
    data = minimal_settings()
    data["sources"]["jobspy"] = {
        "enabled": True,
        "sites": ["linkedin"],
        "locations": ["Remote"],
        "queries": {"core": ["software engineer"]},
        "job_types": ["fulltime"],
        "throttling": {"enabled": False},
        "retry": {"max_attempts": 1},
        "parallel": {"max_workers": 1},
        **overrides,
    }
    return parse_config(data, data_dir=data_dir)


def test_to_canonical_maps_columns_and_keeps_raw_row():
    frame = to_canonical(jobspy_frame())
    assert list(frame.columns) == list(CANONICAL_COLUMNS)
    row = frame.iloc[0]
    assert row["source"] == "linkedin"
    assert row["external_id"] == "li-1"
    assert row["salary_interval"] == "yearly"
    assert '"title": "Software Engineer"' in row["raw_json"]
    assert to_canonical(pd.DataFrame()).empty


def test_throttle_uses_the_slowest_site_and_respects_disable():
    settings = JobSpyConfig(
        sites=["linkedin", "indeed"],
        throttling=ThrottlingConfig(default_delay=1.0, site_delays={"indeed": 4.0}),
    )
    assert _Throttle(settings).delay == 4.0
    disabled = _Throttle(JobSpyConfig(throttling=ThrottlingConfig(enabled=False)))
    with patch("openings.sources.jobspy.time.sleep") as sleep:
        disabled.wait()
    sleep.assert_not_called()


def test_search_single_query_dedupes_across_job_types_and_post_filters(data_dir):
    config = jobspy_config(data_dir, job_types=["fulltime", "internship"])
    duplicate = jobspy_frame()
    unrelated = jobspy_frame({"id": "li-2", "title": "Sales Manager", "description": "Quota."})
    with patch(
        "openings.sources.jobspy._scrape",
        side_effect=[duplicate, pd.concat([duplicate, unrelated])],
    ):
        frame, error = search_single_query(config, "software engineer", "Remote")
    assert error is None
    assert list(frame["title"]) == ["Software Engineer"]


def test_search_single_query_reports_failures(data_dir):
    config = jobspy_config(data_dir, job_types=["fulltime", "internship"])
    with patch(
        "openings.sources.jobspy._scrape", side_effect=[RuntimeError("boom"), jobspy_frame()]
    ):
        frame, error = search_single_query(config, "software engineer", "Remote")
    assert error is None and len(frame) == 1
    with patch("openings.sources.jobspy._scrape", side_effect=RuntimeError("boom")):
        frame, error = search_single_query(config, "software engineer", "Remote")
    assert frame is None and error == "RuntimeError: boom"


def test_run_jobspy_collects_and_counts(data_dir):
    config = jobspy_config(data_dir, queries={"core": ["software engineer", "backend engineer"]})
    with patch("openings.sources.jobspy._scrape", return_value=jobspy_frame()):
        result = run_jobspy(config)
    assert result.stats.tasks == 2
    assert result.stats.succeeded == 2
    assert result.stats.failed == 0
    # the same posting came back for both queries and is kept once
    assert result.stats.rows == 1 and len(result.frame) == 1
    assert list(result.frame.columns) == list(CANONICAL_COLUMNS)


def test_run_jobspy_without_queries_and_with_failures(data_dir):
    empty = jobspy_config(data_dir, queries={})
    assert run_jobspy(empty).stats.tasks == 0
    config = jobspy_config(data_dir)
    with patch("openings.sources.jobspy._scrape", side_effect=RuntimeError("blocked")):
        result = run_jobspy(config)
    assert result.stats.failed == 1
    assert result.stats.errors == ["software engineer @ Remote: RuntimeError: blocked"]
    assert result.frame.empty
