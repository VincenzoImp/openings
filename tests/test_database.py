"""Tests for database module."""

import hashlib
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

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
