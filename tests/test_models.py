from datetime import date

import pandas as pd

from openings.models import (
    PROTECTED_STATUSES,
    Job,
    JobStatus,
    RunSummary,
    SourceRunStats,
    generate_job_id,
    parse_date,
)


def test_job_id_is_normalized():
    a = generate_job_id("Backend  Engineer", "Acme", "Zürich, Switzerland")
    b = generate_job_id("backend engineer", "ACME", "Zürich, Switzerland")
    assert a == b
    assert len(a) == 64


def test_job_id_changes_with_location():
    assert generate_job_id("Engineer", "Acme", "Zurich") != generate_job_id(
        "Engineer", "Acme", "Geneva"
    )


def test_from_row_computes_id_and_cleans_nan():
    job = Job.from_row(
        {
            "title": "Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": float("nan"),
            "min_amount": pd.NA if hasattr(pd, "NA") else None,
            "is_remote": "true",
            "date_posted": "2026-09-01",
        }
    )
    assert job.job_id == generate_job_id("Engineer", "Acme", "Remote")
    assert job.description is None
    assert job.is_remote is True
    assert job.date_posted == date(2026, 9, 1)
    assert job.status is JobStatus.NEW
    assert job.source == "manual"


def test_to_dict_and_summary_are_json_safe():
    job = Job.from_row({"title": "E", "company": "C", "location": "L", "source": "rss"})
    data = job.to_dict()
    assert data["status"] == "new"
    assert isinstance(data["first_seen"], str)
    summary = job.to_summary()
    assert "description" not in summary
    assert summary["source"] == "rss"


def test_new_is_the_only_unprotected_status():
    assert JobStatus.NEW not in PROTECTED_STATUSES
    assert set(PROTECTED_STATUSES) == set(JobStatus) - {JobStatus.NEW}


def test_parse_date_accepts_datetime_strings():
    assert parse_date("2026-09-07T10:00:00") == date(2026, 9, 7)
    assert parse_date("nonsense") is None
    assert parse_date(None) is None


def test_run_summary_duration_and_dict():
    from datetime import datetime, timedelta

    summary = RunSummary(started_at=datetime(2026, 9, 8, 10, 0, 0))
    summary.finished_at = summary.started_at + timedelta(minutes=2, seconds=5)
    summary.sources.append(SourceRunStats(name="rss:x", tasks=1, succeeded=1, rows=3))
    assert summary.duration_formatted == "2m 5s"
    data = summary.to_dict()
    assert data["sources"][0]["rows"] == 3
    assert data["duration_seconds"] == 125.0
