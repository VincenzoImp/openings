"""Tests for database module."""

import hashlib
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import Config, DatabaseConfig, RetentionConfig, ScoringConfig
from database import ReconciliationReport
from models import Job


class TestJobDatabase:
    """Tests for JobDatabase class."""

    def test_database_creation(self, temp_db):
        """Test database and tables are created."""
        assert temp_db.db_path.exists()

    def test_save_new_job(self, temp_db, sample_job):
        """Test saving a new job returns True."""
        is_new = temp_db.save_job(sample_job)

        assert is_new is True

    def test_save_existing_job(self, temp_db, sample_job):
        """Test saving existing job returns False."""
        temp_db.save_job(sample_job)
        is_new = temp_db.save_job(sample_job)

        assert is_new is False

    def test_job_exists(self, temp_db, sample_job):
        """Test job_exists correctly identifies saved jobs."""
        assert temp_db.job_exists(sample_job.job_id) is False

        temp_db.save_job(sample_job)

        assert temp_db.job_exists(sample_job.job_id) is True

    def test_blacklist_job_removes_active_job(self, temp_db, sample_job):
        """Test blacklisting removes a job and persists its identifier."""
        temp_db.save_job(sample_job)

        result = temp_db.blacklist_job(sample_job.job_id)

        assert result is True
        assert temp_db.job_exists(sample_job.job_id) is False
        assert temp_db.is_job_blacklisted(sample_job.job_id) is True
        assert temp_db.get_all_jobs() == []

        stats = temp_db.get_statistics()
        assert stats["blacklisted"] == 1

    def test_save_job_skips_blacklisted(self, temp_db, sample_job):
        """Test blacklisted jobs are not re-saved into the active table."""
        temp_db.save_job(sample_job)
        temp_db.blacklist_job(sample_job.job_id)

        is_new = temp_db.save_job(sample_job)

        assert is_new is False
        assert temp_db.get_all_jobs() == []

    def test_get_new_job_ids(self, temp_db, sample_job):
        """Test get_new_job_ids identifies unseen jobs."""
        temp_db.save_job(sample_job)

        new_job = Job(title="New Role", company="Other Corp", location="LA")
        job_ids = [sample_job.job_id, new_job.job_id]

        new_ids = temp_db.get_new_job_ids(job_ids)

        assert sample_job.job_id not in new_ids
        assert new_job.job_id in new_ids

    def test_get_new_job_ids_excludes_blacklisted(self, temp_db, sample_job):
        """Test blacklisted jobs are never considered new again."""
        temp_db.save_job(sample_job)
        temp_db.blacklist_job(sample_job.job_id)

        new_job = Job(title="New Role", company="Other Corp", location="LA")
        new_ids = temp_db.get_new_job_ids([sample_job.job_id, new_job.job_id])

        assert sample_job.job_id not in new_ids
        assert new_job.job_id in new_ids

    def test_get_new_job_ids_empty(self, temp_db):
        """Test get_new_job_ids with empty list."""
        new_ids = temp_db.get_new_job_ids([])

        assert new_ids == set()

    def test_save_jobs_counts(self, temp_db):
        """Test save_jobs returns correct counts."""
        jobs = [
            Job(title="Job 1", company="Corp", location="NYC"),
            Job(title="Job 2", company="Corp", location="NYC"),
        ]

        new_count, updated_count = temp_db.save_jobs(jobs)

        assert new_count == 2
        assert updated_count == 0

        # Save same jobs again
        new_count, updated_count = temp_db.save_jobs(jobs)

        assert new_count == 0
        assert updated_count == 2

    def test_get_all_jobs(self, temp_db, sample_job):
        """Test get_all_jobs retrieves saved jobs."""
        temp_db.save_job(sample_job)

        jobs = temp_db.get_all_jobs()

        assert len(jobs) == 1
        assert jobs[0].title == sample_job.title
        assert jobs[0].company == sample_job.company

    def test_get_jobs_first_seen_today(self, temp_db, sample_job):
        """Test get_jobs_first_seen_today."""
        temp_db.save_job(sample_job)

        jobs = temp_db.get_jobs_first_seen_today()

        assert len(jobs) == 1
        assert jobs[0].first_seen == date.today()

    def test_get_jobs_by_ids_preserves_requested_order(self, temp_db):
        """Test batched retrieval returns rows in the caller's requested order."""
        first_job = Job(title="First", company="Corp", location="Remote")
        second_job = Job(title="Second", company="Corp", location="Remote")
        temp_db.save_job(first_job)
        temp_db.save_job(second_job)

        jobs = temp_db.get_jobs_by_ids([second_job.job_id, first_job.job_id])

        assert [job.title for job in jobs] == ["Second", "First"]

    def test_mark_as_applied(self, temp_db, sample_job):
        """Test mark_as_applied updates job status."""
        temp_db.save_job(sample_job)

        result = temp_db.mark_as_applied(sample_job.job_id)

        assert result is True

        jobs = temp_db.get_all_jobs()
        assert jobs[0].applied is True

    def test_mark_as_applied_nonexistent(self, temp_db):
        """Test mark_as_applied with nonexistent job."""
        result = temp_db.mark_as_applied("nonexistent_id")

        assert result is False

    def test_get_statistics(self, temp_db, sample_job):
        """Test get_statistics returns expected data."""
        temp_db.save_job(sample_job)

        stats = temp_db.get_statistics()

        assert stats["total_jobs"] == 1
        assert stats["new_today"] == 1
        assert stats["seen_today"] == 1
        assert stats["applied"] == 0
        assert stats["blacklisted"] == 0

    def test_export_to_dataframe(self, temp_db, sample_job):
        """Test export_to_dataframe creates valid DataFrame."""
        temp_db.save_job(sample_job)

        df = temp_db.export_to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "title" in df.columns
        assert "company" in df.columns
        assert df.iloc[0]["title"] == sample_job.title

    def test_export_to_dataframe_empty(self, temp_db):
        """Test export_to_dataframe with empty database."""
        df = temp_db.export_to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_save_jobs_from_dataframe(self, temp_db):
        """Test save_jobs_from_dataframe."""
        df = pd.DataFrame(
            [
                {
                    "title": "Job 1",
                    "company": "Corp A",
                    "location": "NYC",
                    "site": "linkedin",
                },
                {
                    "title": "Job 2",
                    "company": "Corp B",
                    "location": "LA",
                    "site": "indeed",
                },
            ]
        )

        new_count, updated_count = temp_db.save_jobs_from_dataframe(df)

        assert new_count == 2
        assert updated_count == 0

        jobs = temp_db.get_all_jobs()
        assert len(jobs) == 2

    def test_save_jobs_from_dataframe_skips_blacklisted(self, temp_db):
        """Test save_jobs_from_dataframe ignores blacklisted identifiers."""
        blacklisted_job = Job(title="Job 1", company="Corp A", location="NYC")
        temp_db.save_job(blacklisted_job)
        temp_db.blacklist_job(blacklisted_job.job_id)

        df = pd.DataFrame(
            [
                {
                    "title": "Job 1",
                    "company": "Corp A",
                    "location": "NYC",
                    "site": "linkedin",
                },
                {
                    "title": "Job 2",
                    "company": "Corp B",
                    "location": "LA",
                    "site": "indeed",
                },
            ]
        )

        new_count, updated_count = temp_db.save_jobs_from_dataframe(df)

        assert new_count == 1
        assert updated_count == 0

        jobs = temp_db.get_all_jobs()
        assert len(jobs) == 1
        assert jobs[0].title == "Job 2"

    def test_relevance_score_only_increases(self, temp_db, sample_job):
        """Test relevance score only updates if higher."""
        from dataclasses import replace

        high_score_job = replace(sample_job, relevance_score=30)
        temp_db.save_job(high_score_job)

        # Save with lower score
        low_score_job = replace(sample_job, relevance_score=10)
        temp_db.save_job(low_score_job)

        jobs = temp_db.get_all_jobs()
        assert jobs[0].relevance_score == 30  # Should keep higher score

    def test_filter_new_jobs(self, temp_db):
        """Test filter_new_jobs filters DataFrame correctly."""
        # Save one job
        job1 = Job(title="Existing", company="Corp", location="NYC")
        temp_db.save_job(job1)

        # Create DataFrame with existing and new job
        df = pd.DataFrame(
            [
                {"title": "Existing", "company": "Corp", "location": "NYC"},
                {"title": "New Job", "company": "Corp", "location": "LA"},
            ]
        )

        filtered = temp_db.filter_new_jobs(df)

        assert len(filtered) == 1
        assert filtered.iloc[0]["title"] == "New Job"

    def test_filter_new_jobs_excludes_blacklisted(self, temp_db):
        """Test filter_new_jobs excludes jobs that were manually blacklisted."""
        blacklisted_job = Job(title="Do Not Keep", company="Corp", location="NYC")
        temp_db.save_job(blacklisted_job)
        temp_db.blacklist_job(blacklisted_job.job_id)

        df = pd.DataFrame(
            [
                {"title": "Do Not Keep", "company": "Corp", "location": "NYC"},
                {"title": "New Job", "company": "Corp", "location": "LA"},
            ]
        )

        filtered = temp_db.filter_new_jobs(df)

        assert len(filtered) == 1
        assert filtered.iloc[0]["title"] == "New Job"

    def test_filter_new_jobs_empty(self, temp_db):
        """Test filter_new_jobs with empty DataFrame."""
        df = pd.DataFrame()

        filtered = temp_db.filter_new_jobs(df)

        assert len(filtered) == 0

    def test_get_top_jobs(self, temp_db):
        """Test get_top_jobs returns jobs sorted by score."""
        from models import Job

        # Create jobs with different scores
        jobs = [
            Job.from_dict(
                {
                    "title": "Low",
                    "company": "Corp",
                    "location": "NYC",
                    "relevance_score": 10,
                }
            ),
            Job.from_dict(
                {
                    "title": "High",
                    "company": "Corp",
                    "location": "NYC",
                    "relevance_score": 50,
                }
            ),
            Job.from_dict(
                {
                    "title": "Medium",
                    "company": "Corp",
                    "location": "NYC",
                    "relevance_score": 30,
                }
            ),
        ]

        for job in jobs:
            temp_db.save_job(job)

        # Get top 2 jobs
        top_jobs = temp_db.get_top_jobs(limit=2)

        assert len(top_jobs) == 2
        assert top_jobs[0].relevance_score == 50  # Highest first
        assert top_jobs[1].relevance_score == 30  # Second highest

    def test_get_top_jobs_with_min_score(self, temp_db):
        """Test get_top_jobs respects min_score filter."""
        from models import Job

        # Create jobs with different scores
        jobs = [
            Job.from_dict(
                {
                    "title": "Low",
                    "company": "Corp",
                    "location": "NYC",
                    "relevance_score": 10,
                }
            ),
            Job.from_dict(
                {
                    "title": "High",
                    "company": "Corp",
                    "location": "NYC",
                    "relevance_score": 50,
                }
            ),
            Job.from_dict(
                {
                    "title": "Medium",
                    "company": "Corp",
                    "location": "NYC",
                    "relevance_score": 30,
                }
            ),
        ]

        for job in jobs:
            temp_db.save_job(job)

        # Get jobs with min score 25
        top_jobs = temp_db.get_top_jobs(limit=10, min_score=25)

        assert len(top_jobs) == 2
        assert all(job.relevance_score >= 25 for job in top_jobs)

    def test_get_job_count(self, temp_db):
        """Test get_job_count returns correct count."""
        from models import Job

        # Empty database
        assert temp_db.get_job_count() == 0

        # Add some jobs
        jobs = [
            Job.from_dict({"title": f"Job {i}", "company": "Corp", "location": "NYC"})
            for i in range(5)
        ]

        for job in jobs:
            temp_db.save_job(job)

        assert temp_db.get_job_count() == 5

    def test_database_migrates_legacy_job_ids(self, temp_db_path):
        """Test old hash IDs are normalized on first open without losing records."""
        from database import JobDatabase
        from models import generate_job_id

        def legacy_job_id(title: str, company: str, location: str) -> str:
            raw = f"{title}|{company}|{location}".lower()
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        active_title = "  Senior   Engineer  "
        active_company = "Acme"
        active_location = "Remote"
        blacklisted_title = "Legacy\u00a0Role"

        with sqlite3.connect(temp_db_path) as conn:
            conn.execute(JobDatabase.CREATE_TABLE)
            conn.execute(JobDatabase.CREATE_DELETED_TABLE)
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, title, company, location, job_url,
                    site, job_type, is_remote, job_level, description,
                    date_posted, min_amount, max_amount, currency, company_url,
                    first_seen, last_seen, relevance_score, applied, bookmarked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    legacy_job_id(active_title, active_company, active_location),
                    active_title,
                    active_company,
                    active_location,
                    None,
                    "linkedin",
                    "fulltime",
                    True,
                    "senior",
                    "desc",
                    "2024-01-15",
                    None,
                    None,
                    "USD",
                    None,
                    "2024-01-15",
                    "2024-01-16",
                    25,
                    False,
                    True,
                ),
            )
            conn.execute(
                """
                INSERT INTO deleted_jobs (
                    job_id, title, company, location, blacklisted_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    legacy_job_id(blacklisted_title, active_company, active_location),
                    blacklisted_title,
                    active_company,
                    active_location,
                    "2024-01-17T12:00:00",
                ),
            )
            conn.commit()

        db = JobDatabase(temp_db_path)
        active_job_id = generate_job_id(
            "Senior Engineer",
            active_company,
            active_location,
        )
        blacklisted_job_id = generate_job_id(
            "Legacy Role",
            active_company,
            active_location,
        )

        jobs = db.get_all_jobs()

        assert len(jobs) == 1
        assert jobs[0].job_id == active_job_id
        assert db.job_exists(active_job_id) is True
        assert db.is_job_blacklisted(blacklisted_job_id) is True
        db.close()


def _make_config(
    save_threshold: int = 10,
    max_age_days: int = 30,
    purge_blacklist_after_days: int = 90,
) -> Config:
    return Config(
        scoring=ScoringConfig(
            save_threshold=save_threshold,
            notify_threshold=save_threshold + 10,
        ),
        database=DatabaseConfig(
            retention=RetentionConfig(
                max_age_days=max_age_days,
                purge_blacklist_after_days=purge_blacklist_after_days,
            ),
        ),
    )


class TestRetentionMethods:
    """Tests for the retention / reconciliation API."""

    def test_delete_jobs_below_score(self, temp_db):
        from dataclasses import replace

        low = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 5}
        )
        high = Job.from_dict(
            {"title": "High", "company": "C", "location": "NYC", "relevance_score": 40}
        )
        temp_db.save_job(low)
        temp_db.save_job(high)

        deleted = temp_db.delete_jobs_below_score(10)

        assert deleted == 1
        remaining = [j.title for j in temp_db.get_all_jobs()]
        assert remaining == ["High"]
        _ = replace  # keep import used

    def test_delete_jobs_below_score_protects_bookmarked(self, temp_db):
        low_bm = Job.from_dict(
            {"title": "LowBM", "company": "C", "location": "NYC", "relevance_score": 2}
        )
        temp_db.save_job(low_bm)
        temp_db.toggle_bookmark(low_bm.job_id)

        deleted = temp_db.delete_jobs_below_score(10)

        assert deleted == 0
        assert temp_db.job_exists(low_bm.job_id)

    def test_delete_jobs_below_score_protects_applied(self, temp_db):
        job = Job.from_dict(
            {
                "title": "Applied",
                "company": "C",
                "location": "NYC",
                "relevance_score": 1,
            }
        )
        temp_db.save_job(job)
        temp_db.mark_as_applied(job.job_id)

        assert temp_db.delete_jobs_below_score(10) == 0
        assert temp_db.job_exists(job.job_id)

    def test_delete_stale_jobs_protects_bookmarks(self, temp_db, temp_db_path):
        # Insert a job with an old last_seen directly via SQL.
        old_job = Job.from_dict(
            {"title": "Old", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(old_job)
        temp_db.toggle_bookmark(old_job.job_id)

        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen = date('now', '-120 days') WHERE job_id = ?",
                (old_job.job_id,),
            )
            conn.commit()

        assert temp_db.delete_stale_jobs(30) == 0
        assert temp_db.job_exists(old_job.job_id)

    def test_delete_stale_jobs_removes_old(self, temp_db):
        old_job = Job.from_dict(
            {"title": "Old", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(old_job)
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen = date('now', '-120 days') WHERE job_id = ?",
                (old_job.job_id,),
            )
            conn.commit()

        assert temp_db.delete_stale_jobs(30) == 1
        assert not temp_db.job_exists(old_job.job_id)

    def test_purge_blacklist_all(self, temp_db):
        job = Job.from_dict({"title": "Bad", "company": "C", "location": "NYC"})
        temp_db.save_job(job)
        temp_db.blacklist_job(job.job_id)

        assert temp_db.purge_blacklist() == 1
        assert temp_db.get_blacklisted_job_ids() == set()

    def test_purge_blacklist_only_older_than(self, temp_db):
        old_job = Job.from_dict({"title": "Old", "company": "C", "location": "NYC"})
        fresh_job = Job.from_dict({"title": "Fresh", "company": "C", "location": "NYC"})
        temp_db.save_job(old_job)
        temp_db.save_job(fresh_job)
        temp_db.blacklist_job(old_job.job_id)
        temp_db.blacklist_job(fresh_job.job_id)

        # Age the old blacklist row.
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE deleted_jobs SET blacklisted_at = datetime('now', '-200 days') "
                "WHERE job_id = ?",
                (old_job.job_id,),
            )
            conn.commit()

        deleted = temp_db.purge_blacklist(older_than_days=90)

        assert deleted == 1
        remaining = temp_db.get_blacklisted_job_ids()
        assert fresh_job.job_id in remaining
        assert old_job.job_id not in remaining

    def test_get_score_distribution(self, temp_db):
        for title, score in [("A", 3), ("B", 7), ("C", 12), ("D", 14), ("E", 20)]:
            temp_db.save_job(
                Job.from_dict(
                    {
                        "title": title,
                        "company": "C",
                        "location": "NYC",
                        "relevance_score": score,
                    }
                )
            )

        bins = dict(temp_db.get_score_distribution(bin_size=5))

        assert bins[0] == 1  # score 3
        assert bins[5] == 1  # score 7
        assert bins[10] == 2  # scores 12, 14
        assert bins[20] == 1  # score 20

    def test_get_score_distribution_empty(self, temp_db):
        assert temp_db.get_score_distribution() == []

    def test_count_helpers(self, temp_db):
        below = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 5}
        )
        above = Job.from_dict(
            {"title": "High", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(below)
        temp_db.save_job(above)

        assert temp_db.count_jobs_below_score(10) == 1
        assert temp_db.count_jobs_below_score(100) == 2
        assert temp_db.count_stale_jobs(30) == 0

    def test_reconcile_with_config(self, temp_db):
        low = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 2}
        )
        high = Job.from_dict(
            {"title": "High", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(low)
        temp_db.save_job(high)

        cfg = _make_config(save_threshold=10)
        report = temp_db.reconcile_with_config(cfg)

        assert isinstance(report, ReconciliationReport)
        assert report.deleted_below_score == 1
        assert report.total_deleted == 1
        assert temp_db.job_exists(high.job_id)
        assert not temp_db.job_exists(low.job_id)

    def test_reconcile_is_idempotent(self, temp_db):
        low = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        temp_db.save_job(low)

        cfg = _make_config(save_threshold=10)
        first = temp_db.reconcile_with_config(cfg)
        second = temp_db.reconcile_with_config(cfg)

        assert first.total_deleted == 1
        assert second.total_deleted == 0

    def test_reconcile_protects_bookmarked_and_applied(self, temp_db):
        bm = Job.from_dict(
            {"title": "BM", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        applied = Job.from_dict(
            {"title": "AP", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        temp_db.save_job(bm)
        temp_db.save_job(applied)
        temp_db.toggle_bookmark(bm.job_id)
        temp_db.mark_as_applied(applied.job_id)

        cfg = _make_config(save_threshold=10)
        report = temp_db.reconcile_with_config(cfg)

        assert report.total_deleted == 0
        assert report.protected_bookmarked == 1
        assert report.protected_applied == 1
        assert temp_db.job_exists(bm.job_id)
        assert temp_db.job_exists(applied.job_id)

    def test_reset_all_wipes_everything(self, temp_db):
        keep = Job.from_dict(
            {"title": "Keep", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(keep)
        temp_db.toggle_bookmark(keep.job_id)  # Protected — but reset ignores that.
        gone = Job.from_dict({"title": "Gone", "company": "C", "location": "NYC"})
        temp_db.save_job(gone)
        temp_db.blacklist_job(gone.job_id)

        jobs_count, blacklist_count = temp_db.reset_all()

        assert jobs_count == 1
        assert blacklist_count == 1
        assert temp_db.get_all_jobs() == []
        assert temp_db.get_blacklisted_job_ids() == set()

    def test_reset_all_deletes_applied_and_bookmarked(self, temp_db):
        """reset_all is the ONLY path that bypasses bookmark/applied protection."""
        bm = Job.from_dict(
            {"title": "BM", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        ap = Job.from_dict(
            {"title": "AP", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        temp_db.save_job(bm)
        temp_db.save_job(ap)
        temp_db.toggle_bookmark(bm.job_id)
        temp_db.mark_as_applied(ap.job_id)

        jobs_count, blacklist_count = temp_db.reset_all()

        assert jobs_count == 2
        assert blacklist_count == 0
        assert temp_db.get_all_jobs() == []
        assert not temp_db.job_exists(bm.job_id)
        assert not temp_db.job_exists(ap.job_id)

    def test_reset_all_empty_db(self, temp_db):
        """reset_all on empty DB returns zeros."""
        jobs_count, blacklist_count = temp_db.reset_all()
        assert jobs_count == 0
        assert blacklist_count == 0

    def test_reconcile_only_score_threshold(self, temp_db):
        """Reconcile with only save_threshold active (very old age, no blacklist)."""
        low = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 2}
        )
        high = Job.from_dict(
            {"title": "High", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(low)
        temp_db.save_job(high)

        cfg = _make_config(
            save_threshold=10,
            max_age_days=9999,
            purge_blacklist_after_days=9999,
        )
        report = temp_db.reconcile_with_config(cfg)

        assert report.deleted_below_score == 1
        assert report.deleted_stale == 0
        assert report.purged_blacklist == 0
        assert report.total_deleted == 1

    def test_reconcile_only_age(self, temp_db):
        """Reconcile with only stale-age active (score threshold=0)."""
        old_job = Job.from_dict(
            {"title": "Old", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        fresh_job = Job.from_dict(
            {"title": "Fresh", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        temp_db.save_job(old_job)
        temp_db.save_job(fresh_job)

        # Make one job old
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen = date('now', '-120 days') WHERE job_id = ?",
                (old_job.job_id,),
            )
            conn.commit()

        cfg = _make_config(
            save_threshold=0,
            max_age_days=30,
            purge_blacklist_after_days=9999,
        )
        report = temp_db.reconcile_with_config(cfg)

        assert report.deleted_below_score == 0
        assert report.deleted_stale == 1
        assert report.purged_blacklist == 0
        assert temp_db.job_exists(fresh_job.job_id)
        assert not temp_db.job_exists(old_job.job_id)

    def test_reconcile_all_three_active(self, temp_db):
        """Reconcile with all three cleanup passes active."""
        low = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        stale = Job.from_dict(
            {"title": "Stale", "company": "C", "location": "NYC", "relevance_score": 50}
        )
        bl_job = Job.from_dict(
            {"title": "Bl", "company": "C", "location": "NYC", "relevance_score": 30}
        )
        keeper = Job.from_dict(
            {
                "title": "Keeper",
                "company": "C",
                "location": "NYC",
                "relevance_score": 50,
            }
        )
        temp_db.save_job(low)
        temp_db.save_job(stale)
        temp_db.save_job(bl_job)
        temp_db.save_job(keeper)

        # Age one job
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen = date('now', '-120 days') WHERE job_id = ?",
                (stale.job_id,),
            )
            conn.commit()

        # Blacklist one with old timestamp
        temp_db.blacklist_job(bl_job.job_id)
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE deleted_jobs SET blacklisted_at = datetime('now', '-200 days') "
                "WHERE job_id = ?",
                (bl_job.job_id,),
            )
            conn.commit()

        cfg = _make_config(
            save_threshold=10,
            max_age_days=30,
            purge_blacklist_after_days=90,
        )
        report = temp_db.reconcile_with_config(cfg)

        assert report.deleted_below_score == 1  # low
        assert report.deleted_stale == 1  # stale
        assert report.purged_blacklist == 1  # bl_job
        assert report.total_deleted == 3
        assert temp_db.job_exists(keeper.job_id)

    def test_get_score_distribution_bin_size_10(self, temp_db):
        """Test distribution with non-default bin size."""
        for title, score in [("A", 5), ("B", 15), ("C", 25)]:
            temp_db.save_job(
                Job.from_dict(
                    {
                        "title": title,
                        "company": "C",
                        "location": "NYC",
                        "relevance_score": score,
                    }
                )
            )

        bins = dict(temp_db.get_score_distribution(bin_size=10))

        assert bins[0] == 1  # score 5
        assert bins[10] == 1  # score 15
        assert bins[20] == 1  # score 25

    def test_get_score_distribution_invalid_bin_size(self, temp_db):
        """bin_size <= 0 raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="bin_size must be positive"):
            temp_db.get_score_distribution(bin_size=0)

        with pytest.raises(ValueError, match="bin_size must be positive"):
            temp_db.get_score_distribution(bin_size=-5)

    def test_get_score_distribution_single_score(self, temp_db):
        """All jobs at the same score produce a single bin."""
        for i in range(3):
            temp_db.save_job(
                Job.from_dict(
                    {
                        "title": f"Job{i}",
                        "company": "C",
                        "location": "NYC",
                        "relevance_score": 10,
                    }
                )
            )

        bins = temp_db.get_score_distribution(bin_size=5)
        assert len(bins) == 1
        assert bins[0] == (10, 3)

    def test_count_jobs_below_score_accuracy(self, temp_db):
        """Preview count must match actual delete."""
        for title, score in [("A", 5), ("B", 15), ("C", 25)]:
            temp_db.save_job(
                Job.from_dict(
                    {
                        "title": title,
                        "company": "C",
                        "location": "NYC",
                        "relevance_score": score,
                    }
                )
            )

        preview = temp_db.count_jobs_below_score(20)
        actual = temp_db.delete_jobs_below_score(20)
        assert preview == actual == 2

    def test_count_stale_jobs_accuracy(self, temp_db):
        """Preview count matches actual stale delete."""
        j = Job.from_dict(
            {"title": "Old", "company": "C", "location": "NYC", "relevance_score": 10}
        )
        temp_db.save_job(j)
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen = date('now', '-60 days') WHERE job_id = ?",
                (j.job_id,),
            )
            conn.commit()

        preview = temp_db.count_stale_jobs(30)
        actual = temp_db.delete_stale_jobs(30)
        assert preview == actual == 1

    def test_count_blacklist_older_than_accuracy(self, temp_db):
        """Preview count matches actual blacklist purge."""
        j = Job.from_dict({"title": "Bl", "company": "C", "location": "NYC"})
        temp_db.save_job(j)
        temp_db.blacklist_job(j.job_id)
        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE deleted_jobs SET blacklisted_at = datetime('now', '-200 days') "
                "WHERE job_id = ?",
                (j.job_id,),
            )
            conn.commit()

        preview = temp_db.count_blacklist_older_than(90)
        actual = temp_db.purge_blacklist(older_than_days=90)
        assert preview == actual == 1

    def test_blacklist_jobs_large_batch(self, temp_db):
        """Blacklist more than SQLITE_VAR_LIMIT (500) job IDs."""
        job_ids = []
        for i in range(600):
            j = Job.from_dict({"title": f"J{i}", "company": "C", "location": "NYC"})
            temp_db.save_job(j)
            job_ids.append(j.job_id)

        count = temp_db.blacklist_jobs(job_ids)

        assert count == 600
        assert temp_db.get_all_jobs() == []
        assert len(temp_db.get_blacklisted_job_ids()) == 600

    def test_delete_jobs_large_batch(self, temp_db):
        """delete_jobs with more than SQLITE_VAR_LIMIT IDs."""
        job_ids = []
        for i in range(600):
            j = Job.from_dict({"title": f"J{i}", "company": "C", "location": "NYC"})
            temp_db.save_job(j)
            job_ids.append(j.job_id)

        count = temp_db.delete_jobs(job_ids)

        assert count == 600
        assert temp_db.get_all_jobs() == []

    def test_delete_jobs_empty_list(self, temp_db):
        """delete_jobs with empty list returns 0."""
        assert temp_db.delete_jobs([]) == 0

    def test_blacklist_jobs_empty_list(self, temp_db):
        """blacklist_jobs with empty list returns 0."""
        assert temp_db.blacklist_jobs([]) == 0

    def test_get_top_jobs_empty_db(self, temp_db):
        """get_top_jobs on empty DB returns empty list."""
        assert temp_db.get_top_jobs() == []

    def test_get_top_jobs_min_score_filters_all(self, temp_db):
        """When min_score is above all scores, returns empty."""
        j = Job.from_dict(
            {"title": "Low", "company": "C", "location": "NYC", "relevance_score": 5}
        )
        temp_db.save_job(j)
        assert temp_db.get_top_jobs(min_score=100) == []

    def test_count_jobs_below_score_excludes_bookmarked(self, temp_db):
        """count_jobs_below_score skips bookmarked jobs (matches delete behavior)."""
        j = Job.from_dict(
            {"title": "BM", "company": "C", "location": "NYC", "relevance_score": 1}
        )
        temp_db.save_job(j)
        temp_db.toggle_bookmark(j.job_id)

        assert temp_db.count_jobs_below_score(10) == 0

    def test_count_stale_jobs_excludes_applied(self, temp_db):
        """count_stale_jobs skips applied jobs."""
        j = Job.from_dict(
            {"title": "AP", "company": "C", "location": "NYC", "relevance_score": 10}
        )
        temp_db.save_job(j)
        temp_db.mark_as_applied(j.job_id)

        with temp_db._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen = date('now', '-120 days') WHERE job_id = ?",
                (j.job_id,),
            )
            conn.commit()

        assert temp_db.count_stale_jobs(30) == 0
