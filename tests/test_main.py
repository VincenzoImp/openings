"""Tests for main.py entry point."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd


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
        mock_db.filter_blacklisted_jobs.side_effect = lambda df: df
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
        mock_db.filter_blacklisted_jobs.side_effect = lambda df: df
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
        mock_db.filter_blacklisted_jobs.side_effect = lambda df: df
        mock_get_db.return_value = mock_db

        mock_search.side_effect = RuntimeError("Search failed")

        result = run_job_search()

        assert result is False

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.filter_relevant_jobs")
    @patch("main.save_results")
    @patch("main.print_top_jobs")
    @patch("main._send_notifications")
    def test_notifications_only_include_current_run_new_jobs(
        self,
        mock_send_notifications,
        mock_print_top,
        mock_save,
        mock_filter,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
    ):
        """Test notifications use only jobs that are new in the current run."""
        from main import run_job_search
        from models import JobDBRecord, generate_job_id

        mock_config = MagicMock()
        mock_config.database.cleanup_enabled = False
        mock_config.notifications.enabled = True
        mock_config.notifications.telegram.include_top_overall = True
        mock_config.vector_search.enabled = False
        mock_reload.return_value = mock_config

        relevant_df = pd.DataFrame(
            [
                {
                    "title": "New Role",
                    "company": "Acme",
                    "location": "Remote",
                },
                {
                    "title": "Existing Role",
                    "company": "Acme",
                    "location": "Remote",
                },
            ]
        )
        new_job_id = generate_job_id("New Role", "Acme", "Remote")

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.filter_blacklisted_jobs.side_effect = lambda df: df
        mock_db.get_new_job_ids.return_value = {new_job_id}
        mock_db.save_jobs_from_dataframe.return_value = (1, 1)
        mock_db.get_jobs_by_ids.return_value = [
            JobDBRecord(
                job_id=new_job_id,
                title="New Role",
                company="Acme",
                location="Remote",
                relevance_score=25,
                first_seen=pd.Timestamp("2026-04-14").date(),
                last_seen=pd.Timestamp("2026-04-14").date(),
            )
        ]
        mock_get_db.return_value = mock_db

        mock_summary = MagicMock()
        mock_search.return_value = (relevant_df, mock_summary)
        mock_filter.return_value = relevant_df

        result = run_job_search()

        assert result is True
        mock_db.get_jobs_by_ids.assert_called_once_with([new_job_id])
        mock_send_notifications.assert_called_once()
        notified_jobs = mock_send_notifications.call_args.args[2]
        assert len(notified_jobs) == 1
        assert notified_jobs[0].title == "New Role"


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

    @patch.dict(os.environ, {"JOB_SEARCH_MODE": "scheduled"}, clear=False)
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.create_scheduler")
    def test_env_override_forces_scheduled_mode(
        self,
        mock_create_scheduler,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        """Test JOB_SEARCH_MODE=scheduled overrides config for compose usage."""
        from main import main

        mock_config = MagicMock()
        mock_config.scheduler.enabled = False
        mock_config.scheduler.interval_hours = 24
        mock_config.scheduler.run_on_startup = True
        mock_config.notifications.enabled = False
        mock_config.database.recalculate_scores_on_startup = False
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_create_scheduler.return_value = mock_scheduler

        result = main()

        assert result == 0
        mock_scheduler.start.assert_called_once()
        mock_scheduler.run_once.assert_not_called()

    @patch.dict(os.environ, {"JOB_SEARCH_MODE": "single"}, clear=False)
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.create_scheduler")
    def test_env_override_forces_single_shot_mode(
        self,
        mock_create_scheduler,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        """Test JOB_SEARCH_MODE=single overrides config for compose usage."""
        from main import main

        mock_config = MagicMock()
        mock_config.scheduler.enabled = True
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
        mock_scheduler.start.assert_not_called()
