"""Tests for report_generator module."""

from __future__ import annotations

import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from models import JobDBRecord
from report_generator import (
    SearchReport,
    _sanitize_dataframe_for_excel,
    _sanitize_excel_value,
    generate_excel_report,
    generate_markdown_summary,
    generate_text_summary,
    jobs_to_dataframe,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_job_records():
    """Create sample JobDBRecord instances."""
    return [
        JobDBRecord(
            job_id="abc123",
            title="Software Engineer",
            company="Tech Corp",
            location="NYC",
            job_url="https://example.com/1",
            site="linkedin",
            relevance_score=35,
            is_remote=True,
        ),
        JobDBRecord(
            job_id="def456",
            title="Data Scientist",
            company="Data Inc",
            location="SF",
            job_url="https://example.com/2",
            site="indeed",
            relevance_score=25,
            is_remote=False,
        ),
    ]


@pytest.fixture
def sample_report(sample_job_records):
    """Create a sample SearchReport."""
    return SearchReport(
        timestamp=datetime(2026, 1, 15, 10, 30, 0),
        total_jobs=50,
        new_jobs=5,
        updated_jobs=10,
        avg_score=22.5,
        top_jobs=sample_job_records,
        all_new_jobs=sample_job_records,
    )


@pytest.fixture
def empty_report():
    """Create an empty SearchReport."""
    return SearchReport(
        timestamp=datetime(2026, 1, 15, 10, 30, 0),
        total_jobs=0,
        new_jobs=0,
        updated_jobs=0,
        avg_score=0.0,
        top_jobs=[],
        all_new_jobs=[],
    )


# =============================================================================
# TEST _sanitize_excel_value (report_generator version)
# =============================================================================


class TestSanitizeExcelValueReportGen:
    """Tests for _sanitize_excel_value in report_generator."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("=SUM(A1)", "'=SUM(A1)"),
            ("+1cmd", "'+1cmd"),
            ("-1evil", "'-1evil"),
            ("-safe text", "-safe text"),
            ("@mention", "'@mention"),
            ("safe", "safe"),
            ("", ""),
            (42, 42),
            (None, None),
        ],
    )
    def test_sanitization(self, value, expected):
        """Test formula injection prevention."""
        assert _sanitize_excel_value(value) == expected


# =============================================================================
# TEST _sanitize_dataframe_for_excel (report_generator version)
# =============================================================================


class TestSanitizeDataframeReportGen:
    """Tests for _sanitize_dataframe_for_excel in report_generator."""

    def test_sanitizes_text_columns(self):
        """Test that text columns are sanitized."""
        df = pd.DataFrame(
            {
                "title": ["=EVIL()", "Safe"],
                "score": [10, 20],
            }
        )

        result = _sanitize_dataframe_for_excel(df)

        assert result.iloc[0]["title"] == "'=EVIL()"
        assert result.iloc[1]["title"] == "Safe"
        assert result.iloc[0]["score"] == 10


# =============================================================================
# TEST generate_text_summary
# =============================================================================


class TestGenerateTextSummary:
    """Tests for generate_text_summary function."""

    def test_basic_output(self, sample_report):
        """Test text summary contains key information."""
        result = generate_text_summary(sample_report)

        assert "JOB SEARCH TOOL" in result
        assert "2026-01-15" in result
        assert "Total jobs found:    50" in result
        assert "New jobs:            5" in result
        assert "Updated jobs:        10" in result
        assert "22.5" in result

    def test_includes_top_jobs(self, sample_report):
        """Test text summary includes top jobs."""
        result = generate_text_summary(sample_report)

        assert "Software Engineer" in result
        assert "Tech Corp" in result
        assert "https://example.com/1" in result

    def test_empty_report(self, empty_report):
        """Test text summary with no jobs."""
        result = generate_text_summary(empty_report)

        assert "Total jobs found:    0" in result
        assert "New jobs:            0" in result
        # Should not include TOP NEW JOBS section
        assert "TOP NEW JOBS" not in result


# =============================================================================
# TEST generate_markdown_summary
# =============================================================================


class TestGenerateMarkdownSummary:
    """Tests for generate_markdown_summary function."""

    def test_basic_output(self, sample_report):
        """Test markdown summary contains key information."""
        result = generate_markdown_summary(sample_report)

        assert "# Job Search Tool" in result
        assert "2026-01-15" in result
        assert "50" in result
        assert "22.5" in result

    def test_includes_top_jobs(self, sample_report):
        """Test markdown summary includes top jobs."""
        result = generate_markdown_summary(sample_report)

        assert "Software Engineer" in result
        assert "Tech Corp" in result
        assert "[View Job]" in result

    def test_remote_flag(self, sample_report):
        """Test markdown summary shows remote flag."""
        result = generate_markdown_summary(sample_report)

        assert "Remote:** Yes" in result

    def test_empty_report(self, empty_report):
        """Test markdown summary with no jobs."""
        result = generate_markdown_summary(empty_report)

        assert "Total jobs found | 0" in result
        assert "## Top New Jobs" not in result

    def test_max_jobs_limit(self, sample_report):
        """Test markdown summary respects max_jobs limit."""
        result = generate_markdown_summary(sample_report, max_jobs=1)

        # Should show only first job
        assert "Software Engineer" in result
        # Should show "and N more jobs" message
        assert "1 more jobs" in result


# =============================================================================
# TEST jobs_to_dataframe
# =============================================================================


class TestJobsToDataframe:
    """Tests for jobs_to_dataframe function."""

    def test_converts_jobs(self, sample_job_records):
        """Test conversion of job records to DataFrame."""
        df = jobs_to_dataframe(sample_job_records)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "title" in df.columns
        assert "company" in df.columns
        assert "relevance_score" in df.columns
        assert df.iloc[0]["title"] == "Software Engineer"

    def test_empty_list(self):
        """Test conversion of empty list."""
        df = jobs_to_dataframe([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


# =============================================================================
# TEST generate_excel_report
# =============================================================================


class TestGenerateExcelReport:
    """Tests for generate_excel_report function."""

    def test_generates_buffer(self, sample_job_records):
        """Test Excel report returns a BytesIO buffer."""
        result = generate_excel_report(sample_job_records)

        assert isinstance(result, BytesIO)
        # Verify it's a valid Excel file by reading it
        df = pd.read_excel(result)
        assert len(df) == 2
        assert "title" in df.columns

    def test_empty_jobs(self):
        """Test Excel report with empty job list."""
        result = generate_excel_report([])

        assert isinstance(result, BytesIO)
        df = pd.read_excel(result)
        assert len(df) == 0
        # Should still have column headers
        assert "title" in df.columns

    def test_sanitizes_formulas(self):
        """Test Excel report sanitizes formula injection."""
        jobs = [
            JobDBRecord(
                job_id="evil1",
                title="=CMD()",
                company="Corp",
                location="NYC",
                relevance_score=10,
            ),
        ]

        result = generate_excel_report(jobs)
        df = pd.read_excel(result)

        assert df.iloc[0]["title"] == "'=CMD()"
