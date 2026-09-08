from datetime import date, datetime, timezone

from openings.models import (
    ACTIVE_STATUSES,
    PROTECTED_STATUSES,
    Job,
    JobStatus,
    RunSummary,
    canonical_url,
    clean_value,
    generate_job_id,
    job_id_for,
    parse_datetime,
    posting_key,
    utcnow,
)


def test_statuses_split_into_protected_and_active():
    assert JobStatus.NEW not in PROTECTED_STATUSES
    assert JobStatus.BLACKLISTED in PROTECTED_STATUSES
    assert JobStatus.BLACKLISTED not in ACTIVE_STATUSES
    assert JobStatus.NEW in ACTIVE_STATUSES


def test_identity_normalizes_case_and_whitespace():
    assert generate_job_id("Data  Engineer", "ACME", "Zürich") == generate_job_id(
        "data engineer", "acme", "zürich"
    )
    assert generate_job_id("a", "b", "c") != generate_job_id("a", "b", "d")


def test_canonical_url_reduces_known_boards_to_ids():
    assert canonical_url("https://www.linkedin.com/jobs/view/4463727169") == "linkedin:4463727169"
    assert (
        canonical_url("https://ch.linkedin.com/jobs/view/senior-engineer-at-x-4463727169?refId=abc")
        == "linkedin:4463727169"
    )
    assert canonical_url("https://ch.indeed.com/viewjob?jk=e1f9df0a0344c073&from=x") == (
        "url:ch.indeed.com/viewjob?jk=e1f9df0a0344c073"
    )
    assert (
        canonical_url("https://boards.greenhouse.io/proton/jobs/4567?gh_src=x") == "greenhouse:4567"
    )
    assert (
        canonical_url("https://jobs.lever.co/acme/0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b/apply")
        == "lever:0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"
    )
    assert canonical_url("https://jobs.smartrecruiters.com/CERN/744000012345-engineer") == (
        "smartrecruiters:744000012345"
    )
    assert canonical_url("https://careers.google.com/jobs/results/123456/") == "google:123456"


def test_canonical_url_keeps_identifying_query_only():
    assert canonical_url("https://Example.com/careers/123/?utm_source=x&id=9") == (
        "url:example.com/careers/123?id=9"
    )
    assert canonical_url("not a url") is None
    assert canonical_url(None) is None


def test_posting_key_prefers_url_then_external_id():
    assert posting_key("linkedin", "1", "https://linkedin.com/jobs/view/1") == "linkedin:1"
    assert posting_key("greenhouse", "42", None) == "greenhouse:42"
    assert posting_key("manual", None, None) is None
    identity = generate_job_id("t", "c", "l")
    assert job_id_for(None, identity) == identity
    assert job_id_for("linkedin:1", identity) != identity


def test_job_from_row_derives_id_from_posting_key():
    with_url = Job.from_row(
        {
            "title": "T",
            "company": "C",
            "location": "L",
            "job_url": "https://linkedin.com/jobs/view/5",
        }
    )
    without = Job.from_row({"title": "T", "company": "C", "location": "L"})
    assert with_url.job_id == job_id_for("linkedin:5", with_url.identity)
    assert without.job_id == without.identity
    assert with_url.posting_key == "linkedin:5"
    assert without.posting_key is None


def test_from_row_cleans_pandas_values():
    job = Job.from_row(
        {
            "title": "Engineer",
            "company": "Acme",
            "location": float("nan"),
            "source": None,
            "is_remote": "true",
            "min_amount": "100000",
            "relevance_score": None,
            "date_posted": "2026-09-01",
            "status": "applied",
            "status_changed_at": "2026-09-01T10:00:00",
        }
    )
    assert job.location == ""
    assert job.source == "manual"
    assert job.is_remote is True
    assert job.min_amount == 100000.0
    assert job.relevance_score == 0
    assert job.date_posted == date(2026, 9, 1)
    assert job.status is JobStatus.APPLIED
    assert job.status_changed_at == datetime(2026, 9, 1, 10, tzinfo=timezone.utc)


def test_parse_datetime_assumes_utc_for_naive_values():
    assert parse_datetime("2026-09-08T13:00:00") == datetime(2026, 9, 8, 13, tzinfo=timezone.utc)
    assert parse_datetime("2026-09-08T15:00:00+02:00") == datetime(
        2026, 9, 8, 13, tzinfo=timezone.utc
    )
    assert parse_datetime("nope") is None
    assert utcnow().tzinfo is timezone.utc


def test_clean_value():
    assert clean_value("NaN") is None
    assert clean_value(float("nan")) is None
    assert clean_value("x") == "x"


def test_to_dict_and_summary_are_json_safe():
    job = Job.from_row({"title": "T", "company": "C", "location": "L", "description": "d"})
    data = job.to_dict()
    assert data["status"] == "new"
    assert data["first_seen"] == date.today().isoformat()
    summary = job.to_summary()
    assert "description" not in summary and "raw_json" not in summary
    assert summary["postings_count"] == 0


def test_run_summary_duration_and_running():
    summary = RunSummary(started_at=utcnow())
    assert summary.running is True
    summary.finish()
    assert summary.running is False
    assert summary.duration_formatted.endswith("s")
    assert summary.to_dict()["started_at"].endswith("+00:00")
