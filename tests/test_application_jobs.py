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


def test_list_jobs_supports_console_filters(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService
    from job_search_tool.application.models import JobListQuery

    service = JobApplicationService(seeded_db)

    result = service.list_jobs(
        JobListQuery(
            sites=["indeed"],
            location="san",
            job_types=["fulltime"],
            date_posted_from=date(2026, 5, 1),
            sort="title",
        )
    )

    assert result.total == 1
    assert [job.title for job in result.jobs] == ["Data Scientist"]


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


def test_set_bookmarked_updates_multiple_jobs(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    jobs = service.list_jobs().jobs[:2]
    job_ids = [jobs[0].job_id, jobs[1].job_id, jobs[0].job_id]

    result = service.set_bookmarked(job_ids, True)

    assert result.success is True
    assert result.affected_count == 2
    assert result.job_ids == [jobs[0].job_id, jobs[1].job_id]
    assert result.bookmarked is True
    assert all(seeded_db.get_job_by_id(job.job_id).bookmarked for job in jobs)  # type: ignore[union-attr]


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


def test_set_applied_updates_multiple_jobs(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    jobs = service.list_jobs().jobs[:2]

    result = service.set_applied([job.job_id for job in jobs], True)

    assert result.success is True
    assert result.affected_count == 2
    assert result.job_ids == [job.job_id for job in jobs]
    assert result.applied is True
    assert all(seeded_db.get_job_by_id(job.job_id).applied for job in jobs)  # type: ignore[union-attr]


def test_blacklist_jobs_reports_removed_count(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    job = service.list_jobs().jobs[0]

    result = service.blacklist_jobs([job.job_id, job.job_id])

    assert result.success is True
    assert result.affected_count == 1
    assert seeded_db.get_job_by_id(job.job_id) is None
    assert seeded_db.is_job_blacklisted(job.job_id) is True


def test_blacklist_unblacklist_and_delete_use_command_envelopes(
    seeded_db: JobDatabase,
) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    jobs = service.list_jobs().jobs
    blacklist_id = jobs[0].job_id
    delete_id = jobs[1].job_id

    blacklisted = service.blacklist_jobs([blacklist_id, blacklist_id])
    unblacklisted = service.unblacklist_jobs([blacklist_id])
    deleted = service.delete_jobs([delete_id])

    assert blacklisted.success is True
    assert blacklisted.affected_count == 1
    assert blacklisted.job_ids == [blacklist_id]
    assert unblacklisted.success is True
    assert unblacklisted.affected_count == 1
    assert unblacklisted.job_ids == [blacklist_id]
    assert deleted.success is True
    assert deleted.affected_count == 1
    assert deleted.job_ids == [delete_id]
    assert seeded_db.is_job_blacklisted(blacklist_id) is False
    assert seeded_db.get_job_by_id(blacklist_id) is None
    assert seeded_db.is_job_blacklisted(delete_id) is False
    assert seeded_db.get_job_by_id(delete_id) is None


def test_delete_and_blacklist_remove_vector_embeddings(
    seeded_db: JobDatabase,
) -> None:
    from unittest.mock import MagicMock

    from job_search_tool.application.jobs import JobApplicationService

    vector_store = MagicMock()
    service = JobApplicationService(
        seeded_db, vector_store_factory=lambda: vector_store
    )
    jobs = service.list_jobs().jobs
    delete_id = jobs[0].job_id
    blacklist_id = jobs[1].job_id

    service.delete_jobs([delete_id])
    service.blacklist_jobs([blacklist_id])

    vector_store.delete_jobs.assert_any_call([delete_id])
    vector_store.delete_jobs.assert_any_call([blacklist_id])


def test_cleanup_deletions_remove_stale_vector_embeddings(
    seeded_db: JobDatabase,
) -> None:
    from unittest.mock import MagicMock

    from job_search_tool.application.jobs import JobApplicationService

    vector_store = MagicMock()
    vector_store.get_embedded_ids.return_value = {
        job.job_id for job in seeded_db.get_all_jobs()
    }
    stale_vector_id = next(
        job.job_id
        for job in seeded_db.get_all_jobs()
        if job.title == "Frontend Developer"
    )
    service = JobApplicationService(
        seeded_db, vector_store_factory=lambda: vector_store
    )

    result = service.delete_stale_jobs(30)

    assert result.affected_count == 1
    vector_store.delete_jobs.assert_called_once_with([stale_vector_id])


def test_search_similar_filters_stale_vector_rows_and_uses_db_metadata(
    seeded_db: JobDatabase,
) -> None:
    from unittest.mock import MagicMock

    from job_search_tool.application.jobs import JobApplicationService
    from job_search_tool.vector_store import SemanticSearchResult

    active_job = seeded_db.get_all_jobs()[0]
    stale_id = "deleted-job"
    vector_store = MagicMock()
    vector_store.search.return_value = [
        SemanticSearchResult(
            job_id=stale_id,
            distance=0.1,
            similarity=0.9,
            metadata={"title": "Deleted"},
        ),
        SemanticSearchResult(
            job_id=active_job.job_id,
            distance=0.2,
            similarity=0.8,
            metadata={},
        ),
    ]

    service = JobApplicationService(
        seeded_db, vector_store_factory=lambda: vector_store
    )
    results = service.search_similar("python", n_results=2)

    assert [result.job_id for result in results] == [active_job.job_id]
    assert results[0].title == active_job.title
    assert results[0].company == active_job.company
    assert results[0].similarity == 0.8
    vector_store.delete_jobs.assert_called_once_with([stale_id])


def test_blacklist_query_and_facets(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService
    from job_search_tool.application.models import BlacklistListQuery

    service = JobApplicationService(seeded_db)
    job = next(job for job in service.list_jobs().jobs if job.title == "Data Scientist")
    service.blacklist_jobs([job.job_id])

    blacklist = service.list_blacklisted_jobs(BlacklistListQuery(text="data"))
    facets = service.get_facets()

    assert blacklist.total == 1
    assert blacklist.items[0].job_id == job.job_id
    assert blacklist.limit == 100
    assert facets["sites"] == [
        {"value": "indeed", "count": 1},
        {"value": "linkedin", "count": 1},
    ]
    assert facets["remote"] == [
        {"value": False, "count": 1},
        {"value": True, "count": 1},
    ]


def test_manual_cleanup_commands(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    stale = service.delete_stale_jobs(30)
    below_score = service.delete_jobs_below_score(35)

    assert stale.success is True
    assert stale.affected_count == 1
    assert below_score.success is False
    assert below_score.affected_count == 0


def test_export_jobs_selected_as_json(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    selected = service.list_jobs().jobs[:2]

    exported = service.export_jobs(job_ids=[job.job_id for job in selected], fmt="json")

    assert exported.media_type == "application/json"
    assert exported.filename == "jobs.json"
    assert exported.row_count == 2
    assert b"Backend Engineer" in exported.content
    assert b"Data Scientist" in exported.content


def test_cleanup_preview_matches_cleanup_execution(seeded_db: JobDatabase) -> None:
    from job_search_tool.application.jobs import JobApplicationService

    service = JobApplicationService(seeded_db)
    config = _cleanup_config()

    preview = service.preview_cleanup(config)
    result = service.run_cleanup(config)

    assert preview.deleted_below_score == 1
    assert preview.deleted_stale == 0
    assert replace(preview, protected_applied=result.protected_applied) == result
