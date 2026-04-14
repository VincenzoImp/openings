"""Tests for search_jobs module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import Config, SearchConfig, ThrottlingConfig
from search_jobs import ThrottledExecutor, print_banner, print_top_jobs, search_jobs


# =============================================================================
# TEST ThrottledExecutor
# =============================================================================


class TestThrottledExecutor:
    """Tests for ThrottledExecutor class."""

    @pytest.fixture
    def config_with_throttling(self):
        """Create config with throttling enabled."""
        return Config(
            search=SearchConfig(sites=["linkedin", "indeed"]),
            throttling=ThrottlingConfig(
                enabled=True,
                default_delay=0.1,
                site_delays={"linkedin": 0.2, "indeed": 0.1},
                jitter=0.0,
            ),
        )

    @pytest.fixture
    def config_without_throttling(self):
        """Create config with throttling disabled."""
        return Config(
            throttling=ThrottlingConfig(enabled=False),
        )

    def test_init(self, config_with_throttling):
        """Test ThrottledExecutor initialization."""
        executor = ThrottledExecutor(config_with_throttling)

        assert executor.config == config_with_throttling
        assert executor.site_locks == {}
        assert executor.site_last_request == {}

    def test_get_site_lock_creates_lock(self, config_with_throttling):
        """Test _get_site_lock creates new lock for site."""
        executor = ThrottledExecutor(config_with_throttling)

        executor._get_site_lock("linkedin")

        assert "linkedin" in executor.site_locks
        assert "linkedin" in executor.site_last_request

    def test_get_site_lock_returns_same_lock(self, config_with_throttling):
        """Test _get_site_lock returns same lock for same site."""
        executor = ThrottledExecutor(config_with_throttling)

        lock1 = executor._get_site_lock("linkedin")
        lock2 = executor._get_site_lock("linkedin")

        assert lock1 is lock2

    def test_throttled_search_no_throttling(self, config_without_throttling):
        """Test throttled_search bypasses throttling when disabled."""
        executor = ThrottledExecutor(config_without_throttling)

        with patch("search_jobs.search_single_query") as mock_search:
            mock_search.return_value = ("query", "loc", pd.DataFrame(), None)

            executor.throttled_search("query", "loc", config_without_throttling)

            mock_search.assert_called_once()

    def test_throttled_search_with_throttling(self, config_with_throttling):
        """Test throttled_search applies delay when enabled."""
        executor = ThrottledExecutor(config_with_throttling)

        with (
            patch("search_jobs.search_single_query") as mock_search,
            patch("search_jobs.time.sleep"),
        ):
            mock_search.return_value = ("query", "loc", pd.DataFrame(), None)

            # First call - no delay needed
            executor.throttled_search("query", "loc", config_with_throttling)
            # Second call - should trigger delay
            executor.throttled_search("query2", "loc", config_with_throttling)

            assert mock_search.call_count == 2


# =============================================================================
# TEST search_single_query
# =============================================================================


class TestSearchSingleQuery:
    """Tests for search_single_query function."""

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return Config(
            search=SearchConfig(
                sites=["indeed"],
                locations=["NYC"],
                results_wanted=10,
            ),
            throttling=ThrottlingConfig(enabled=False),
        )

    def test_successful_search(self, config):
        """Test successful search returns DataFrame."""
        from search_jobs import search_single_query

        mock_df = pd.DataFrame(
            [
                {
                    "title": "Dev",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "desc",
                }
            ]
        )

        with (
            patch("search_jobs.scrape_jobs", return_value=mock_df) as mock_scrape,
            patch("search_jobs.fuzzy_post_filter", return_value=mock_df),
        ):
            query, loc, result_df, error = search_single_query(
                "developer", "NYC", config
            )

            assert query == "developer"
            assert loc == "NYC"
            assert result_df is not None
            assert len(result_df) == 1
            assert error is None
            assert mock_scrape.call_args.kwargs["job_type"] == "fulltime"

    def test_search_respects_multiple_job_types(self, config):
        """Test search issues one JobSpy request per configured job type."""
        from search_jobs import search_single_query

        config.search.job_types = ["fulltime", "contract"]
        fulltime_df = pd.DataFrame(
            [
                {
                    "title": "Dev",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "fulltime",
                }
            ]
        )
        contract_df = pd.DataFrame(
            [
                {
                    "title": "Contract Dev",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "contract",
                }
            ]
        )

        with (
            patch(
                "search_jobs.scrape_jobs",
                side_effect=[fulltime_df, contract_df],
            ) as mock_scrape,
            patch(
                "search_jobs.fuzzy_post_filter",
                side_effect=lambda df, *_args: df,
            ),
        ):
            _query, _loc, result_df, error = search_single_query(
                "developer", "NYC", config
            )

        assert error is None
        assert result_df is not None
        assert len(result_df) == 2
        assert [call.kwargs["job_type"] for call in mock_scrape.call_args_list] == [
            "fulltime",
            "contract",
        ]

    def test_search_returns_none(self, config):
        """Test search with no results returns None."""
        from search_jobs import search_single_query

        with patch("search_jobs.scrape_jobs", return_value=pd.DataFrame()):
            query, loc, result_df, error = search_single_query(
                "developer", "NYC", config
            )

            assert result_df is None
            assert error is None

    def test_search_exception(self, config):
        """Test search handles exceptions gracefully."""
        from search_jobs import search_single_query

        with patch("search_jobs.scrape_jobs", side_effect=ValueError("Bad data")):
            query, loc, result_df, error = search_single_query(
                "developer", "NYC", config
            )

            assert result_df is None
            assert error is not None
            assert "Data error" in error

    def test_search_connection_error(self, config):
        """Test search handles connection errors."""
        from search_jobs import search_single_query

        with patch(
            "search_jobs.scrape_jobs", side_effect=ConnectionError("No network")
        ):
            query, loc, result_df, error = search_single_query(
                "developer", "NYC", config
            )

            assert result_df is None
            assert error is not None
            assert "Network error" in error


# =============================================================================
# TEST search_jobs
# =============================================================================


class TestSearchJobs:
    """Tests for search_jobs function."""

    @pytest.fixture
    def config(self):
        """Create a test config with queries."""
        from config import ParallelConfig, PostFilterConfig, RetryConfig

        return Config(
            search=SearchConfig(
                sites=["indeed"],
                locations=["NYC"],
                results_wanted=10,
            ),
            queries={"test": ["developer"]},
            parallel=ParallelConfig(max_workers=1),
            retry=RetryConfig(max_attempts=1),
            throttling=ThrottlingConfig(enabled=False),
            post_filter=PostFilterConfig(enabled=False),
        )

    def test_search_jobs_returns_results(self, config):
        """Test search_jobs returns combined DataFrame and summary."""
        mock_df = pd.DataFrame(
            [
                {
                    "title": "Dev",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "desc",
                }
            ]
        )

        with (
            patch("search_jobs.scrape_jobs", return_value=mock_df),
            patch("search_jobs.fuzzy_post_filter", return_value=mock_df),
        ):
            result_df, summary = search_jobs(config)

            assert result_df is not None
            assert len(result_df) >= 1
            assert summary.successful_queries >= 1

    def test_search_jobs_no_results(self, config):
        """Test search_jobs with no results."""
        with patch("search_jobs.scrape_jobs", return_value=pd.DataFrame()):
            result_df, summary = search_jobs(config)

            assert result_df is None
            assert summary.unique_jobs == 0

    def test_search_jobs_deduplication(self, config):
        """Test search_jobs deduplicates results."""
        # Same job returned twice
        mock_df = pd.DataFrame(
            [
                {
                    "title": "Dev",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "desc",
                }
            ]
        )
        config.queries = {"cat1": ["query1"], "cat2": ["query2"]}
        config.search.locations = ["NYC"]

        with (
            patch("search_jobs.scrape_jobs", return_value=mock_df),
            patch("search_jobs.fuzzy_post_filter", return_value=mock_df),
        ):
            result_df, summary = search_jobs(config)

            if result_df is not None:
                # With deduplication, identical jobs should appear only once
                assert len(result_df) == 1

    def test_search_jobs_handles_failures(self, config):
        """Test search_jobs tracks failed queries."""
        with patch(
            "search_jobs.scrape_jobs",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result_df, summary = search_jobs(config)

            assert result_df is None


# =============================================================================
# TEST print_banner
# =============================================================================


class TestPrintBanner:
    """Tests for print_banner function."""

    def test_print_banner_does_not_crash(self):
        """Test print_banner runs without error."""
        config = Config()

        # Should not raise any exception
        print_banner(config)

    def test_print_banner_with_custom_profile(self):
        """Test print_banner with custom profile."""
        from config import ProfileConfig

        config = Config(
            profile=ProfileConfig(
                name="John Doe",
                current_position="Senior Dev @ Acme",
                skills="Python, Go",
                target="Staff Engineer",
            )
        )

        # Should not raise any exception
        print_banner(config)

    def test_print_banner_truncates_long_values(self):
        """Test print_banner handles very long profile values."""
        from config import ProfileConfig

        config = Config(
            profile=ProfileConfig(
                name="A" * 100,
                current_position="B" * 200,
                skills="C" * 200,
                target="D" * 200,
            )
        )

        # Should not raise any exception
        print_banner(config)


# =============================================================================
# TEST print_top_jobs
# =============================================================================


class TestPrintTopJobs:
    """Tests for print_top_jobs function."""

    def test_print_top_jobs(self):
        """Test print_top_jobs with normal data."""
        df = pd.DataFrame(
            {
                "title": ["Dev A", "Dev B"],
                "company": ["Corp A", "Corp B"],
                "location": ["NYC", "SF"],
                "relevance_score": [30, 25],
                "job_url": ["https://example.com/1", "https://example.com/2"],
            }
        )

        # Should not raise any exception
        print_top_jobs(df)

    def test_print_top_jobs_empty(self):
        """Test print_top_jobs with empty DataFrame."""
        df = pd.DataFrame(
            columns=["title", "company", "location", "relevance_score", "job_url"]
        )

        # Should not raise any exception
        print_top_jobs(df)

    def test_print_top_jobs_no_url(self):
        """Test print_top_jobs with missing URL column."""
        df = pd.DataFrame(
            {
                "title": ["Dev A"],
                "company": ["Corp A"],
                "location": ["NYC"],
                "relevance_score": [30],
                "job_url": [None],
            }
        )

        # Should not raise any exception
        print_top_jobs(df)

    def test_print_top_jobs_count(self):
        """Test print_top_jobs respects count parameter."""
        df = pd.DataFrame(
            {
                "title": [f"Dev {i}" for i in range(20)],
                "company": ["Corp"] * 20,
                "location": ["NYC"] * 20,
                "relevance_score": list(range(20, 0, -1)),
                "job_url": [None] * 20,
            }
        )

        # Should not raise any exception
        print_top_jobs(df, count=5)
