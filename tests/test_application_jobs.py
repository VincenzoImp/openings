"""Tests for the shared job application layer."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from job_search_tool.config import (
    Config,
    DatabaseConfig,
    RetentionConfig,
    ScoringConfig,
)
from job_search_tool.database import JobDatabase
from job_search_tool.models import Job


@pytest.fixture()
def seeded_db(tmp_path: Path) -> JobDatabase:
    """Create a database with varied jobs for query/command tests."""
    db = JobDatabase(tmp_path / "jobs.db")
    jobs = [
        Job(
            title="Backend Engineer",
            company="Acme Corp",
            location="Remote",
            relevance_score=40,
            job_url="https://example.com/backend",
            job_type="fulltime",
            is_remote=True,
            date_posted=date(2026, 5, 1),
        ),
        Job(
            title="Frontend Developer",
            company="Widget Inc",
            location="New York",
            relevance_score=20,
            job_url="https://example.com/frontend",
            job_type="contract",
            is_remote=False,
            date_posted=date(2026, 5, 3),
        ),
        Job(
            title="Data Scientist",
            company="DataCo",
            location="San Francisco",
            relevance_score=30,
            job_url="https://example.com/data",
            job_type="fulltime",
            is_remote=False,
            date_posted=date(2026, 5, 5),
        ),
    ]
    db.save_job(jobs[0], site="linkedin")
    db.save_job(jobs[1], site="indeed")
    db.save_job(jobs[2], site="indeed")

    backend_id = jobs[0].job_id
    data_id = jobs[2].job_id
    db.toggle_bookmark(backend_id)
    db.toggle_applied(data_id)

    with db._get_connection() as conn:
        old_date = (date.today() - timedelta(days=45)).isoformat()
        conn.execute(
            "UPDATE jobs SET last_seen = ? WHERE job_id = ?",
            (old_date, jobs[1].job_id),
        )
        conn.commit()

    yield db
    db.close()


def _cleanup_config() -> Config:
    return Config(
        scoring=ScoringConfig(save_threshold=25, notify_threshold=35),
        database=DatabaseConfig(
            retention=RetentionConfig(
                max_age_days=30,
                purge_blacklist_after_days=90,
            ),
        ),
    )


def test_list_jobs_filters_by_score_site_company_and_status(
    seeded_db: JobDatabase,
) -> None:
    from job_search_tool.application.jobs import JobApplicationService
    from job_search_tool.application.models import JobListQuery

    service = JobApplicationService(seeded_db)

    score_site = service.list_jobs(
        JobListQuery(min_score=25, max_score=35, site="indeed")
    )
    company = service.list_jobs(JobListQuery(company="acme"))
    bookmarked = service.list_jobs(JobListQuery(bookmarked=True))
    applied = service.list_jobs(JobListQuery(applied=True))

    assert [job.title for job in score_site.jobs] == ["Data Scientist"]
    assert [job.title for job in company.jobs] == ["Backend Engineer"]
    assert [job.title for job in bookmarked.jobs] == ["Backend Engineer"]
    assert [job.title for job in applied.jobs] == ["Data Scientist"]


def test_list_jobs_paginates_and_reports_total(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService
    from job_search_tool.application.models import JobListQuery

    service = JobApplicationService(seeded_db)

    result = service.list_jobs(JobListQuery(limit=2, offset=1, sort="score"))

    assert result.total == 3
    assert result.limit == 2
    assert result.offset == 1
    assert [job.title for job in result.jobs] == [
        "Data Scientist",
        "Frontend Developer",
    ]


def test_list_jobs_sorts_by_date(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService
    from job_search_tool.application.models import JobListQuery

    service = JobApplicationService(seeded_db)

    result = service.list_jobs(JobListQuery(sort="date"))

    assert [job.title for job in result.jobs] == [
        "Data Scientist",
        "Frontend Developer",
        "Backend Engineer",
    ]


def test_set_bookmarked_is_idempotent(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    job = service.list_jobs().jobs[-1]

    first = service.set_bookmarked(job.job_id, True)
    second = service.set_bookmarked(job.job_id, True)

    assert first.success is True
    assert second.success is True
    assert first.bookmarked is True
    assert second.bookmarked is True
    assert seeded_db.get_job_by_id(job.job_id).bookmarked is True  # type: ignore[union-attr]


def test_set_applied_is_idempotent(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    job = service.list_jobs().jobs[0]

    first = service.set_applied(job.job_id, True)
    second = service.set_applied(job.job_id, True)

    assert first.success is True
    assert second.success is True
    assert first.applied is True
    assert second.applied is True
    assert seeded_db.get_job_by_id(job.job_id).applied is True  # type: ignore[union-attr]


def test_blacklist_jobs_reports_removed_count(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    job = service.list_jobs().jobs[0]

    result = service.blacklist_jobs([job.job_id, job.job_id])

    assert result.success is True
    assert result.affected_count == 1
    assert seeded_db.get_job_by_id(job.job_id) is None
    assert seeded_db.is_job_blacklisted(job.job_id) is True


def test_cleanup_preview_matches_cleanup_execution(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    config = _cleanup_config()

    preview = service.preview_cleanup(config)
    result = service.run_cleanup(config)

    assert preview.deleted_below_score == 1
    assert preview.deleted_stale == 0
    assert replace(preview, protected_applied=result.protected_applied) == result
