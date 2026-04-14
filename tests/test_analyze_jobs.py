"""Tests for analyze_jobs module."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from analyze_jobs import (
    analyze_companies,
    analyze_keywords,
    analyze_locations,
    analyze_remote,
    analyze_salary,
    generate_report,
    load_latest_results,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample DataFrame for analysis."""
    return pd.DataFrame(
        [
            {
                "title": "Software Engineer",
                "company": "Google",
                "location": "Mountain View, CA",
                "description": "Python developer role",
                "job_type": "fulltime",
                "is_remote": True,
                "min_amount": 120000,
                "max_amount": 180000,
                "relevance_score": 85,
            },
            {
                "title": "Data Scientist",
                "company": "Google",
                "location": "New York, NY",
                "description": "Machine learning engineer",
                "job_type": "fulltime",
                "is_remote": False,
                "min_amount": 130000,
                "max_amount": 200000,
                "relevance_score": 70,
            },
            {
                "title": "Backend Developer",
                "company": "Meta",
                "location": "Mountain View, CA",
                "description": "Java and Python backend",
                "job_type": "contract",
                "is_remote": True,
                "min_amount": None,
                "max_amount": None,
                "relevance_score": 60,
            },
        ]
    )


class TestAnalyzeCompanies:
    """Tests for analyze_companies function."""

    def test_returns_series(self, sample_df: pd.DataFrame) -> None:
        result = analyze_companies(sample_df)
        assert isinstance(result, pd.Series)

    def test_counts_companies(self, sample_df: pd.DataFrame) -> None:
        result = analyze_companies(sample_df)
        assert result["Google"] == 2
        assert result["Meta"] == 1

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["company"])
        result = analyze_companies(df)
        assert len(result) == 0


class TestAnalyzeLocations:
    """Tests for analyze_locations function."""

    def test_returns_series(self, sample_df: pd.DataFrame) -> None:
        result = analyze_locations(sample_df)
        assert isinstance(result, pd.Series)

    def test_counts_locations(self, sample_df: pd.DataFrame) -> None:
        result = analyze_locations(sample_df)
        assert result["Mountain View, CA"] == 2


class TestAnalyzeKeywords:
    """Tests for analyze_keywords function."""

    def test_returns_list_of_tuples(self, sample_df: pd.DataFrame) -> None:
        result = analyze_keywords(sample_df)
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)

    def test_finds_common_words(self, sample_df: pd.DataFrame) -> None:
        result = analyze_keywords(sample_df)
        words = [word for word, _ in result]
        # "engineer" or "developer" should appear
        assert any(w in words for w in ["engineer", "developer", "software"])

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["title"])
        result = analyze_keywords(df)
        assert result == []


class TestAnalyzeSalary:
    """Tests for analyze_salary function."""

    def test_returns_dict(self, sample_df: pd.DataFrame) -> None:
        result = analyze_salary(sample_df)
        assert result is not None
        assert isinstance(result, dict)

    def test_salary_stats(self, sample_df: pd.DataFrame) -> None:
        result = analyze_salary(sample_df)
        assert result is not None
        assert "min_salary_avg" in result or "avg_min" in result or len(result) > 0

    def test_no_salary_data(self) -> None:
        df = pd.DataFrame({"min_amount": [None, None], "max_amount": [None, None]})
        result = analyze_salary(df)
        # Should return None or empty dict when no salary data
        assert result is None or len(result) == 0


class TestAnalyzeRemote:
    """Tests for analyze_remote function."""

    def test_returns_series(self, sample_df: pd.DataFrame) -> None:
        result = analyze_remote(sample_df)
        assert result is not None
        assert isinstance(result, pd.Series)

    def test_counts_remote(self, sample_df: pd.DataFrame) -> None:
        result = analyze_remote(sample_df)
        assert result is not None
        assert result[True] == 2
        assert result[False] == 1

    def test_missing_column(self) -> None:
        df = pd.DataFrame({"title": ["test"]})
        result = analyze_remote(df)
        assert result is None


class TestGenerateReport:
    """Tests for generate_report function."""

    def test_returns_dict(self, sample_df: pd.DataFrame) -> None:
        from config import Config

        config = Config()
        result = generate_report(sample_df, config)
        assert isinstance(result, dict)

    def test_report_has_keys(self, sample_df: pd.DataFrame) -> None:
        from config import Config

        config = Config()
        result = generate_report(sample_df, config)
        assert "total_jobs" in result
        assert result["total_jobs"] == 3


class TestLoadLatestResults:
    """Tests for loading the newest CSV export."""

    def test_prefers_latest_mtime(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        older = results_dir / "relevant_jobs_old.csv"
        newer = results_dir / "relevant_jobs_new.csv"
        older.write_text("title,company,location\nOld,Corp,Remote\n", encoding="utf-8")
        newer.write_text("title,company,location\nNew,Corp,Remote\n", encoding="utf-8")

        older_mtime = 1_700_000_000
        newer_mtime = older_mtime + 60
        older.touch()
        newer.touch()
        older.chmod(0o644)
        newer.chmod(0o644)
        import os

        os.utime(older, (older_mtime, older_mtime))
        os.utime(newer, (newer_mtime, newer_mtime))

        config = MagicMock()
        config.results_path = results_dir

        df = load_latest_results(config)

        assert df is not None
        assert df.iloc[0]["title"] == "New"
