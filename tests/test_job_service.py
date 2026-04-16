"""Tests for the job_service shared service layer."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from models import JobDBRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(**overrides: object) -> JobDBRecord:
    defaults: dict[str, object] = {
        "job_id": "test123",
        "title": "Engineer",
        "company": "Corp",
        "location": "Remote",
        "relevance_score": 25,
        "first_seen": date(2026, 4, 1),
        "last_seen": date(2026, 4, 15),
        "bookmarked": False,
        "applied": False,
    }
    defaults.update(overrides)
    return JobDBRecord(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DB singleton
# ---------------------------------------------------------------------------


def test_get_db_creates_instance():
    import job_service

    job_service.reset_singletons()
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(job_service, "DB_PATH", Path(tmpdir) / "test.db"):
            db = job_service.get_db()
            assert db is not None
            from database import JobDatabase

            assert isinstance(db, JobDatabase)
            job_service.reset_singletons()


def test_get_db_returns_same_instance():
    import job_service

    job_service.reset_singletons()
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(job_service, "DB_PATH", Path(tmpdir) / "test.db"):
            db1 = job_service.get_db()
            db2 = job_service.get_db()
            assert db1 is db2
            job_service.reset_singletons()


def test_close_db_closes_and_resets():
    import job_service

    job_service.reset_singletons()
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(job_service, "DB_PATH", Path(tmpdir) / "test.db"):
            job_service.get_db()
            assert job_service._db is not None
            job_service.close_db()
            assert job_service._db is None


def test_reset_singletons_clears_all():
    import job_service

    job_service._db = object()  # type: ignore[assignment]
    job_service._vs = object()  # type: ignore[assignment]
    job_service._vs_attempted = True
    job_service.reset_singletons()
    assert job_service._db is None
    assert job_service._vs is None
    assert job_service._vs_attempted is False


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------


def test_get_vs_returns_none_when_unavailable(caplog):
    import job_service

    job_service.reset_singletons()
    with patch.object(
        job_service,
        "get_vs",
        wraps=job_service.get_vs,
    ):
        with patch.dict("sys.modules", {"vector_store": None}):
            # Force re-import failure by resetting and patching the import
            job_service._vs = None
            job_service._vs_attempted = False
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *a, **kw: (
                    (_ for _ in ()).throw(ImportError("no chromadb"))
                    if name == "vector_store"
                    else __import__(name, *a, **kw)
                ),
            ):
                result = job_service.get_vs()
            assert result is None
    job_service.reset_singletons()


def test_get_vs_attempts_only_once():
    import job_service

    job_service.reset_singletons()
    call_count = 0
    original_import = (
        __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
    )  # type: ignore[union-attr]

    def counting_import(name, *args, **kwargs):
        nonlocal call_count
        if name == "vector_store":
            call_count += 1
            raise ImportError("no chromadb")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=counting_import):
        job_service.get_vs()
        job_service.get_vs()

    assert call_count == 1
    assert job_service._vs_attempted is True
    job_service.reset_singletons()


# ---------------------------------------------------------------------------
# Record serialization
# ---------------------------------------------------------------------------


def test_record_to_dict_all_fields():
    from job_service import record_to_dict

    r = _make_record(
        job_url="https://example.com",
        site="linkedin",
        job_type="fulltime",
        is_remote=True,
        job_level="senior",
        description="Great job",
        date_posted=date(2026, 3, 20),
        min_amount=80000.0,
        max_amount=120000.0,
        currency="USD",
        company_url="https://corp.com",
    )
    d = record_to_dict(r)
    assert d["job_id"] == "test123"
    assert d["title"] == "Engineer"
    assert d["company"] == "Corp"
    assert d["relevance_score"] == 25
    assert d["bookmarked"] is False
    assert d["applied"] is False
    assert d["site"] == "linkedin"
    assert d["min_amount"] == 80000.0


def test_record_to_dict_serializes_dates():
    from job_service import record_to_dict

    r = _make_record(date_posted=date(2026, 3, 15))
    d = record_to_dict(r)
    assert d["first_seen"] == "2026-04-01"
    assert d["last_seen"] == "2026-04-15"
    assert d["date_posted"] == "2026-03-15"


def test_record_to_dict_handles_none_dates():
    from job_service import record_to_dict

    r = _make_record(date_posted=None)
    d = record_to_dict(r)
    assert d["date_posted"] is None


def test_record_to_summary_excludes_description():
    from job_service import record_to_summary

    r = _make_record(description="A long description here")
    s = record_to_summary(r)
    assert "description" not in s


def test_record_to_summary_includes_core_fields():
    from job_service import record_to_summary

    r = _make_record(site="indeed", job_url="https://example.com/job")
    s = record_to_summary(r)
    assert s["job_id"] == "test123"
    assert s["title"] == "Engineer"
    assert s["company"] == "Corp"
    assert s["location"] == "Remote"
    assert s["relevance_score"] == 25
    assert s["site"] == "indeed"
    assert s["bookmarked"] is False
    assert s["applied"] is False
    assert s["job_url"] == "https://example.com/job"


def test_record_to_summary_serializes_first_seen():
    from job_service import record_to_summary

    r = _make_record()
    s = record_to_summary(r)
    assert s["first_seen"] == "2026-04-01"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _make_job_list() -> list[JobDBRecord]:
    return [
        _make_record(
            job_id="a",
            title="Backend Dev",
            company="Big Tech Co",
            site="linkedin",
            relevance_score=40,
            bookmarked=True,
            applied=False,
        ),
        _make_record(
            job_id="b",
            title="Frontend Dev",
            company="Startup",
            site="indeed",
            relevance_score=20,
            bookmarked=False,
            applied=True,
        ),
        _make_record(
            job_id="c",
            title="Data Scientist",
            company="DataCo",
            site="LinkedIn",
            relevance_score=30,
            bookmarked=False,
            applied=False,
        ),
        _make_record(
            job_id="d",
            title="DevOps",
            company="Ops Inc",
            site="glassdoor",
            relevance_score=10,
            bookmarked=False,
            applied=False,
        ),
    ]


def test_filter_jobs_no_filters_returns_all():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs)
    assert len(result) == 4


def test_filter_jobs_by_min_score():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, min_score=25)
    assert all(j.relevance_score >= 25 for j in result)
    assert len(result) == 2


def test_filter_jobs_by_max_score():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, max_score=25)
    assert all(j.relevance_score <= 25 for j in result)
    assert len(result) == 2


def test_filter_jobs_by_site_case_insensitive():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, site="LinkedIn")
    # Both "linkedin" and "LinkedIn" should match
    assert len(result) == 2


def test_filter_jobs_by_company_substring():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, company="Tech")
    assert len(result) == 1
    assert result[0].company == "Big Tech Co"


def test_filter_jobs_by_bookmarked():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, bookmarked=True)
    assert len(result) == 1
    assert result[0].bookmarked is True


def test_filter_jobs_by_applied():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, applied=True)
    assert len(result) == 1
    assert result[0].applied is True


def test_filter_jobs_combined():
    from job_service import filter_jobs

    jobs = _make_job_list()
    result = filter_jobs(jobs, min_score=15, site="linkedin")
    assert len(result) == 2
    assert all(j.relevance_score >= 15 for j in result)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_sort_jobs_by_score_descending():
    from job_service import sort_jobs_by_score

    jobs = _make_job_list()
    sorted_jobs = sort_jobs_by_score(jobs)
    scores = [j.relevance_score for j in sorted_jobs]
    assert scores == sorted(scores, reverse=True)


def test_sort_jobs_by_date_descending():
    from job_service import sort_jobs_by_date

    jobs = [
        _make_record(
            job_id="x", first_seen=date(2026, 1, 1), date_posted=date(2026, 1, 5)
        ),
        _make_record(
            job_id="y", first_seen=date(2026, 3, 1), date_posted=date(2026, 3, 10)
        ),
        _make_record(
            job_id="z", first_seen=date(2026, 2, 1), date_posted=date(2026, 2, 15)
        ),
    ]
    sorted_jobs = sort_jobs_by_date(jobs)
    dates = [j.date_posted for j in sorted_jobs]
    assert dates == [date(2026, 3, 10), date(2026, 2, 15), date(2026, 1, 5)]


def test_sort_jobs_by_date_handles_none():
    from job_service import sort_jobs_by_date

    jobs = [
        _make_record(job_id="a", date_posted=None, first_seen=date(2026, 2, 1)),
        _make_record(job_id="b", date_posted=date(2026, 3, 1)),
        _make_record(job_id="c", date_posted=None, first_seen=date(2026, 1, 1)),
    ]
    # Should not crash
    sorted_jobs = sort_jobs_by_date(jobs)
    assert len(sorted_jobs) == 3
    # Job with explicit date should come first (2026-03-01 > 2026-02-01 > 2026-01-01)
    assert sorted_jobs[0].job_id == "b"
