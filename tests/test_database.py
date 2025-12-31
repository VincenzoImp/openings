"""Tests for database module."""

import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from models import Job
from database import JobDatabase


class TestJobDatabase:
    """Tests for JobDatabase class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = JobDatabase(db_path)
            yield db

    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return Job(
            title="Software Engineer",
            company="Test Corp",
            location="New York, NY",
            job_url="https://example.com/job/123",
            description="Build amazing things",
            is_remote=True,
            relevance_score=25,
        )

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

    def test_get_new_job_ids(self, temp_db, sample_job):
        """Test get_new_job_ids identifies unseen jobs."""
        temp_db.save_job(sample_job)

        new_job = Job(title="New Role", company="Other Corp", location="LA")
        job_ids = [sample_job.job_id, new_job.job_id]

        new_ids = temp_db.get_new_job_ids(job_ids)

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
        df = pd.DataFrame([
            {"title": "Job 1", "company": "Corp A", "location": "NYC", "site": "linkedin"},
            {"title": "Job 2", "company": "Corp B", "location": "LA", "site": "indeed"},
        ])

        new_count, updated_count = temp_db.save_jobs_from_dataframe(df)

        assert new_count == 2
        assert updated_count == 0

        jobs = temp_db.get_all_jobs()
        assert len(jobs) == 2

    def test_relevance_score_only_increases(self, temp_db, sample_job):
        """Test relevance score only updates if higher."""
        sample_job.relevance_score = 30
        temp_db.save_job(sample_job)

        # Save with lower score
        sample_job.relevance_score = 10
        temp_db.save_job(sample_job)

        jobs = temp_db.get_all_jobs()
        assert jobs[0].relevance_score == 30  # Should keep higher score

    def test_filter_new_jobs(self, temp_db):
        """Test filter_new_jobs filters DataFrame correctly."""
        # Save one job
        job1 = Job(title="Existing", company="Corp", location="NYC")
        temp_db.save_job(job1)

        # Create DataFrame with existing and new job
        df = pd.DataFrame([
            {"title": "Existing", "company": "Corp", "location": "NYC"},
            {"title": "New Job", "company": "Corp", "location": "LA"},
        ])

        filtered = temp_db.filter_new_jobs(df)

        assert len(filtered) == 1
        assert filtered.iloc[0]["title"] == "New Job"

    def test_filter_new_jobs_empty(self, temp_db):
        """Test filter_new_jobs with empty DataFrame."""
        df = pd.DataFrame()

        filtered = temp_db.filter_new_jobs(df)

        assert len(filtered) == 0
