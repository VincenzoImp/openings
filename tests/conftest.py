"""Pytest configuration and shared fixtures for Job Search Tool tests.

This module provides centralized fixtures used across all test modules:
- Job and JobDBRecord fixtures
- Config fixtures with various configurations
- Database fixtures with temporary databases
- Mock fixtures for external dependencies (JobSpy, Telegram)
"""

import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

# Ensure scripts directory is in path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Mock jobspy before any imports that might use it
# This prevents ImportError when jobspy is not installed in test environment
sys.modules["jobspy"] = MagicMock()


# =============================================================================
# JOB FIXTURES
# =============================================================================


@pytest.fixture
def sample_job_data() -> dict:
    """Basic job data dictionary for creating Job instances."""
    return {
        "title": "Software Engineer",
        "company": "Test Corp",
        "location": "New York, NY",
        "job_url": "https://example.com/job/123",
        "description": "Build amazing software products",
        "is_remote": True,
        "job_type": "fulltime",
        "date_posted": "2024-01-15",
        "min_amount": 100000.0,
        "max_amount": 150000.0,
        "currency": "USD",
        "relevance_score": 25,
    }


@pytest.fixture
def sample_job(sample_job_data):
    """Create a sample Job instance."""
    from models import Job

    return Job.from_dict(sample_job_data)


@pytest.fixture
def sample_job_db_record(sample_job):
    """Create a sample JobDBRecord from a Job."""
    from models import JobDBRecord

    return JobDBRecord.from_job(
        sample_job,
        site="linkedin",
        job_level="senior",
        company_url="https://example.com/company",
    )


@pytest.fixture
def multiple_jobs() -> list:
    """Create multiple Job instances for batch testing."""
    from models import Job

    jobs_data = [
        {
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "New York, NY",
            "relevance_score": 30,
        },
        {
            "title": "Backend Developer",
            "company": "Startup Inc",
            "location": "San Francisco, CA",
            "relevance_score": 25,
        },
        {
            "title": "Full Stack Developer",
            "company": "Big Tech Co",
            "location": "Remote",
            "is_remote": True,
            "relevance_score": 35,
        },
    ]
    return [Job.from_dict(data) for data in jobs_data]


@pytest.fixture
def sample_dataframe(sample_job_data) -> pd.DataFrame:
    """Create a sample DataFrame with job data."""
    return pd.DataFrame([sample_job_data])


@pytest.fixture
def multiple_jobs_dataframe() -> pd.DataFrame:
    """Create a DataFrame with multiple jobs."""
    jobs_data = [
        {
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "New York, NY",
            "site": "linkedin",
            "is_remote": False,
            "relevance_score": 30,
        },
        {
            "title": "Backend Developer",
            "company": "Startup Inc",
            "location": "San Francisco, CA",
            "site": "indeed",
            "is_remote": False,
            "relevance_score": 25,
        },
        {
            "title": "Full Stack Developer",
            "company": "Big Tech Co",
            "location": "Remote",
            "site": "glassdoor",
            "is_remote": True,
            "relevance_score": 35,
        },
    ]
    return pd.DataFrame(jobs_data)


# =============================================================================
# CONFIG FIXTURES
# =============================================================================


@pytest.fixture
def default_config():
    """Create a default Config instance with all defaults."""
    from config import Config

    return Config()


@pytest.fixture
def scoring_config():
    """Create a ScoringConfig for testing scoring functionality."""
    from config import ScoringConfig

    return ScoringConfig(
        threshold=10,
        weights={
            "primary": 20,
            "secondary": 10,
            "bonus": 5,
        },
        keywords={
            "primary": ["software engineer", "developer"],
            "secondary": ["python", "javascript"],
            "bonus": ["remote"],
        },
    )


@pytest.fixture
def test_config(scoring_config):
    """Create a Config instance optimized for testing."""
    from config import (
        Config,
        DatabaseConfig,
        LoggingConfig,
        NotificationsConfig,
        OutputConfig,
        ParallelConfig,
        PostFilterConfig,
        ProfileConfig,
        RetryConfig,
        SchedulerConfig,
        SearchConfig,
        TelegramConfig,
        ThrottlingConfig,
    )

    return Config(
        search=SearchConfig(
            results_wanted=10,
            hours_old=24,
            sites=["indeed", "linkedin"],
            locations=["Remote"],
        ),
        queries={"test": ["software engineer", "python developer"]},
        scoring=scoring_config,
        parallel=ParallelConfig(max_workers=2),
        retry=RetryConfig(max_attempts=2, base_delay=0.1, backoff_factor=1.5),
        throttling=ThrottlingConfig(enabled=False),  # Disable for faster tests
        post_filter=PostFilterConfig(enabled=True, min_similarity=80),
        logging=LoggingConfig(level="DEBUG"),
        database=DatabaseConfig(cleanup_enabled=False),
        output=OutputConfig(save_csv=False, save_excel=False),  # Skip file I/O in tests
        profile=ProfileConfig(name="Test User"),
        scheduler=SchedulerConfig(enabled=False),
        notifications=NotificationsConfig(enabled=False),
    )


@pytest.fixture
def telegram_config():
    """Create a TelegramConfig for testing notifications."""
    from config import TelegramConfig

    return TelegramConfig(
        enabled=True,
        bot_token="123456:ABC-test-token",
        chat_ids=["12345", "67890"],
        send_summary=True,
        min_score_for_notification=10,
        max_jobs_in_message=5,
    )


@pytest.fixture
def notifications_config(telegram_config):
    """Create a NotificationsConfig for testing."""
    from config import NotificationsConfig

    return NotificationsConfig(
        enabled=True,
        telegram=telegram_config,
    )


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def temp_db(temp_db_path) -> Generator:
    """Create a temporary JobDatabase instance."""
    from database import JobDatabase

    db = JobDatabase(temp_db_path)
    yield db


@pytest.fixture
def populated_db(temp_db, multiple_jobs):
    """Create a database pre-populated with test jobs."""
    for job in multiple_jobs:
        temp_db.save_job(job, site="linkedin")
    return temp_db


# =============================================================================
# MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_jobspy():
    """Mock the jobspy scrape_jobs function."""
    with patch("search_jobs.scrape_jobs") as mock:
        # Return an empty DataFrame by default
        mock.return_value = pd.DataFrame()
        yield mock


@pytest.fixture
def mock_jobspy_with_results(sample_dataframe):
    """Mock jobspy to return sample results."""
    with patch("search_jobs.scrape_jobs") as mock:
        mock.return_value = sample_dataframe.copy()
        yield mock


@pytest.fixture
def mock_telegram_bot():
    """Mock the Telegram Bot for notification testing."""
    with patch("notifier.Bot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())
        mock_bot_class.return_value = mock_bot
        yield mock_bot


@pytest.fixture
def mock_logger():
    """Mock the logger for testing log output."""
    with patch("logger.get_logger") as mock:
        mock_logger = MagicMock()
        mock.return_value = mock_logger
        yield mock_logger


# =============================================================================
# NOTIFICATION DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_notification_data(sample_job_db_record):
    """Create sample NotificationData for testing."""
    from notifier import NotificationData

    return NotificationData(
        run_timestamp=datetime.now(),
        total_jobs_found=10,
        new_jobs_count=3,
        updated_jobs_count=2,
        avg_score=25.5,
        new_jobs=[sample_job_db_record],
    )


@pytest.fixture
def empty_notification_data():
    """Create empty NotificationData for testing edge cases."""
    from notifier import NotificationData

    return NotificationData(
        run_timestamp=datetime.now(),
        total_jobs_found=0,
        new_jobs_count=0,
        updated_jobs_count=0,
        avg_score=0.0,
        new_jobs=[],
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_job_row(
    title: str = "Developer",
    company: str = "Corp",
    location: str = "NYC",
    description: str = "",
    **kwargs,
) -> pd.Series:
    """Helper to create a pandas Series representing a job row."""
    data = {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        **kwargs,
    }
    return pd.Series(data)


# Make helper available as fixture too
@pytest.fixture
def create_job_row_fixture():
    """Fixture that returns the create_job_row helper function."""
    return create_job_row
