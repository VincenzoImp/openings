"""Tests for main.py entry point."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestRunJobSearch:
    """Tests for run_job_search function."""

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.filter_relevant_jobs")
    @patch("main.save_results")
    @patch("main.print_top_jobs")
    def test_successful_search(
        self,
        mock_print_top,
        mock_save,
        mock_filter,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
    ):
        """Test successful search flow."""
        from main import run_job_search

        # Setup mocks
        mock_config = MagicMock()
        mock_config.database.cleanup_enabled = False
        mock_config.notifications.enabled = False
        mock_reload.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.save_jobs_from_dataframe.return_value = (2, 3)
        mock_get_db.return_value = mock_db

        mock_summary = MagicMock()
        mock_df = pd.DataFrame([{"title": "Dev", "company": "Co", "location": "NY"}])
        mock_search.return_value = (mock_df, mock_summary)
        mock_filter.return_value = mock_df

        result = run_job_search()

        assert result is True
        mock_search.assert_called_once_with(mock_config)
        mock_filter.assert_called_once()
        mock_db.save_jobs_from_dataframe.assert_called_once()

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    def test_no_results(
        self,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
    ):
        """Test search with no results returns True (not a failure)."""
        from main import run_job_search

        mock_config = MagicMock()
        mock_config.database.cleanup_enabled = False
        mock_config.notifications.enabled = False
        mock_reload.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_summary = MagicMock()
        mock_search.return_value = (None, mock_summary)

        result = run_job_search()

        assert result is True

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    def test_exception_returns_false(
        self,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
    ):
        """Test that exceptions during search return False."""
        from main import run_job_search

        mock_config = MagicMock()
        mock_config.database.cleanup_enabled = False
        mock_reload.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_search.side_effect = RuntimeError("Search failed")

        result = run_job_search()

        assert result is False


class TestMain:
    """Tests for main() entry point."""

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.create_scheduler")
    def test_single_shot_success(
        self,
        mock_create_scheduler,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        """Test single-shot mode returns 0 on success."""
        from main import main

        mock_config = MagicMock()
        mock_config.scheduler.enabled = False
        mock_config.notifications.enabled = False
        mock_config.database.recalculate_scores_on_startup = False
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = True
        mock_create_scheduler.return_value = mock_scheduler

        result = main()

        assert result == 0
        mock_scheduler.run_once.assert_called_once()

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.create_scheduler")
    def test_single_shot_failure(
        self,
        mock_create_scheduler,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        """Test single-shot mode returns 1 on failure."""
        from main import main

        mock_config = MagicMock()
        mock_config.scheduler.enabled = False
        mock_config.notifications.enabled = False
        mock_config.database.recalculate_scores_on_startup = False
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = False
        mock_create_scheduler.return_value = mock_scheduler

        result = main()

        assert result == 1

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    @patch("main.create_scheduler")
    def test_score_recalculation_on_startup(
        self,
        mock_create_scheduler,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        """Test that scores are recalculated on startup when enabled."""
        from main import main

        mock_config = MagicMock()
        mock_config.scheduler.enabled = False
        mock_config.notifications.enabled = False
        mock_config.database.recalculate_scores_on_startup = True
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 10}
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = True
        mock_create_scheduler.return_value = mock_scheduler

        main()

        mock_recalc.assert_called_once_with(mock_db, mock_config)

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    @patch("main.create_scheduler")
    def test_skip_recalculation_empty_db(
        self,
        mock_create_scheduler,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        """Test that score recalculation is skipped when DB is empty."""
        from main import main

        mock_config = MagicMock()
        mock_config.scheduler.enabled = False
        mock_config.notifications.enabled = False
        mock_config.database.recalculate_scores_on_startup = True
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = True
        mock_create_scheduler.return_value = mock_scheduler

        main()

        mock_recalc.assert_not_called()
