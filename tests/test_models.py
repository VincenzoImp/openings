"""Tests for models module."""

import hashlib
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from models import Job, JobDBRecord, SearchSummary


class TestJob:
    """Tests for Job dataclass."""

    def test_job_id_generation(self):
        """Test that job_id is generated correctly."""
        job = Job(
            title="Software Engineer",
            company="Test Corp",
            location="New York, NY",
        )

        # Verify it's a full SHA256 hash (64 characters)
        assert len(job.job_id) == 64
        assert all(c in "0123456789abcdef" for c in job.job_id)

    def test_job_id_deterministic(self):
        """Test that same inputs produce same job_id."""
        job1 = Job(title="Dev", company="Corp", location="NYC")
        job2 = Job(title="Dev", company="Corp", location="NYC")

        assert job1.job_id == job2.job_id

    def test_job_id_case_insensitive(self):
        """Test that job_id is case-insensitive."""
        job1 = Job(title="Software Engineer", company="Test Corp", location="NYC")
        job2 = Job(title="SOFTWARE ENGINEER", company="TEST CORP", location="nyc")

        assert job1.job_id == job2.job_id

    def test_job_id_different_for_different_jobs(self):
        """Test that different jobs have different IDs."""
        job1 = Job(title="Dev", company="Corp", location="NYC")
        job2 = Job(title="Engineer", company="Corp", location="NYC")

        assert job1.job_id != job2.job_id

    def test_job_from_dict(self):
        """Test Job.from_dict() conversion."""
        data = {
            "title": "Engineer",
            "company": "Test",
            "location": "Remote",
            "job_url": "https://example.com",
            "is_remote": True,
            "relevance_score": 25,
        }

        job = Job.from_dict(data)

        assert job.title == "Engineer"
        assert job.company == "Test"
        assert job.location == "Remote"
        assert job.job_url == "https://example.com"
        assert job.is_remote is True
        assert job.relevance_score == 25

    def test_job_from_dict_with_date_string(self):
        """Test Job.from_dict() handles date strings."""
        data = {
            "title": "Dev",
            "company": "Corp",
            "location": "NYC",
            "date_posted": "2024-01-15",
        }

        job = Job.from_dict(data)

        assert job.date_posted == date(2024, 1, 15)

    def test_job_from_dict_with_missing_fields(self):
        """Test Job.from_dict() handles missing optional fields."""
        data = {
            "title": "Dev",
            "company": "Corp",
            "location": "NYC",
        }

        job = Job.from_dict(data)

        assert job.job_url is None
        assert job.description is None
        assert job.is_remote is None
        assert job.relevance_score == 0

    def test_job_to_dict(self):
        """Test Job.to_dict() conversion."""
        job = Job(
            title="Engineer",
            company="Test",
            location="Remote",
            is_remote=True,
            relevance_score=30,
        )

        data = job.to_dict()

        assert data["title"] == "Engineer"
        assert data["company"] == "Test"
        assert data["location"] == "Remote"
        assert data["is_remote"] is True
        assert data["relevance_score"] == 30
        assert "job_id" in data


class TestSearchSummary:
    """Tests for SearchSummary dataclass."""

    def test_initial_values(self):
        """Test default values."""
        summary = SearchSummary()

        assert summary.total_queries == 0
        assert summary.successful_queries == 0
        assert summary.failed_queries == 0
        assert summary.unique_jobs == 0

    def test_duration_before_finish(self):
        """Test duration is 0 before finish() is called."""
        summary = SearchSummary()

        assert summary.duration_seconds == 0.0
        assert summary.duration_formatted == "0m 0s"

    def test_duration_after_finish(self):
        """Test duration after finish() is called."""
        import time

        summary = SearchSummary()
        time.sleep(0.1)  # Wait a bit
        summary.finish()

        assert summary.duration_seconds > 0
        assert summary.end_time is not None

    def test_duration_formatted(self):
        """Test duration formatting."""
        summary = SearchSummary()
        summary.end_time = summary.start_time  # 0 duration

        assert summary.duration_formatted == "0m 0s"


class TestJobDBRecord:
    """Tests for JobDBRecord dataclass."""

    def test_from_job(self):
        """Test JobDBRecord.from_job() conversion."""
        job = Job(
            title="Engineer",
            company="Test",
            location="Remote",
            is_remote=True,
            relevance_score=25,
        )

        record = JobDBRecord.from_job(job, site="linkedin", job_level="senior")

        assert record.job_id == job.job_id
        assert record.title == "Engineer"
        assert record.company == "Test"
        assert record.site == "linkedin"
        assert record.job_level == "senior"
        assert record.relevance_score == 25
        assert record.applied is False
