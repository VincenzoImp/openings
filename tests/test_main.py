"""Tests for main.py entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from database import ReconciliationReport


def _make_empty_report() -> ReconciliationReport:
    return ReconciliationReport()


def _make_runtime_config_mock() -> MagicMock:
    """Build a MagicMock config that satisfies _prepare_runtime and friends."""
    cfg = MagicMock()
    cfg.notifications.enabled = False
    cfg.notifications.telegram.include_top_overall = False
    cfg.vector_search.enabled = False
    cfg.vector_search.embed_on_save = False
    cfg.scoring.save_threshold = 0
    cfg.scoring.notify_threshold = 20
    cfg.scheduler.interval_hours = 24
    cfg.scheduler.run_on_startup = True
    return cfg


class TestRunJobSearch:
    """Tests for run_job_search function."""

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.score_jobs")
    @patch("main.partition_by_thresholds")
    @patch("main.print_top_jobs")
    def test_successful_search(
        self,
        mock_print_top,
        mock_partition,
        mock_score,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
    ):
        from main import run_job_search
        from scoring import Partitions

        mock_config = _make_runtime_config_mock()
        mock_reload.return_value = mock_config

        mock_df = pd.DataFrame(
            [{"title": "Dev", "company": "Co", "location": "NY", "relevance_score": 30}]
        )

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.save_jobs_from_dataframe.return_value = (2, 3)
        mock_db.exclude_blacklisted.side_effect = lambda df: df
        mock_db.get_new_job_ids.return_value = set()
        mock_db.get_jobs_by_ids.return_value = []
        mock_get_db.return_value = mock_db

        mock_summary = MagicMock()
        mock_search.return_value = (mock_df, mock_summary)
        mock_score.return_value = mock_df
        mock_partition.return_value = Partitions(
            scored=mock_df, to_save=mock_df, to_notify=mock_df.iloc[0:0]
        )

        result = run_job_search()

        assert result is True
        mock_search.assert_called_once_with(mock_config)
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
        from main import run_job_search

        mock_config = _make_runtime_config_mock()
        mock_reload.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_search.return_value = (None, MagicMock())

        assert run_job_search() is True

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
        from main import run_job_search

        mock_config = _make_runtime_config_mock()
        mock_reload.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_get_db.return_value = mock_db

        mock_search.side_effect = RuntimeError("boom")

        assert run_job_search() is False

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.score_jobs")
    @patch("main.partition_by_thresholds")
    @patch("main.print_top_jobs")
    @patch("main._send_notifications")
    def test_notifications_only_include_current_run_new_jobs(
        self,
        mock_send_notifications,
        mock_print_top,
        mock_partition,
        mock_score,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
    ):
        from main import run_job_search
        from models import JobDBRecord, generate_job_id
        from scoring import Partitions

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_config.scoring.notify_threshold = 20
        mock_reload.return_value = mock_config

        new_row = {
            "title": "New Role",
            "company": "Acme",
            "location": "Remote",
            "relevance_score": 25,
        }
        existing_row = {
            "title": "Existing Role",
            "company": "Acme",
            "location": "Remote",
            "relevance_score": 22,
        }
        relevant_df = pd.DataFrame([new_row, existing_row])
        new_job_id = generate_job_id("New Role", "Acme", "Remote")

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.exclude_blacklisted.side_effect = lambda df: df
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

        mock_search.return_value = (relevant_df, MagicMock())
        mock_score.return_value = relevant_df
        # Both above save_threshold=0, both above notify_threshold=20.
        mock_partition.return_value = Partitions(
            scored=relevant_df,
            to_save=relevant_df,
            to_notify=relevant_df,
        )

        result = run_job_search()

        assert result is True
        mock_db.get_jobs_by_ids.assert_called_once_with([new_job_id])
        mock_send_notifications.assert_called_once()
        notified_jobs = mock_send_notifications.call_args.args[2]
        assert len(notified_jobs) == 1
        assert notified_jobs[0].title == "New Role"


class TestMain:
    """Tests for main() entry point."""

    @patch("sys.argv", ["main.py", "once"])
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    @patch("main.create_scheduler")
    def test_single_shot_success(
        self,
        mock_create_scheduler,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import main

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = True
        mock_create_scheduler.return_value = mock_scheduler

        assert main() == 0
        mock_scheduler.run_once.assert_called_once()
        mock_scheduler.start.assert_not_called()

    @patch("sys.argv", ["main.py", "once"])
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    @patch("main.create_scheduler")
    def test_single_shot_failure(
        self,
        mock_create_scheduler,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import main

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = False
        mock_create_scheduler.return_value = mock_scheduler

        assert main() == 1

    @patch("sys.argv", ["main.py", "once"])
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    @patch("main.create_scheduler")
    def test_score_recalculation_always_runs_when_db_nonempty(
        self,
        mock_create_scheduler,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import main

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 10}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = True
        mock_create_scheduler.return_value = mock_scheduler

        main()

        mock_recalc.assert_called_once_with(mock_db, mock_config)
        mock_db.reconcile_with_config.assert_called_once_with(mock_config)

    @patch("sys.argv", ["main.py", "once"])
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
        from main import main

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_scheduler.run_once.return_value = True
        mock_create_scheduler.return_value = mock_scheduler

        main()

        mock_recalc.assert_not_called()

    @patch("sys.argv", ["main.py"])
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.create_scheduler")
    def test_default_is_scheduled_mode(
        self,
        mock_create_scheduler,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import main

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        mock_scheduler = MagicMock()
        mock_create_scheduler.return_value = mock_scheduler

        result = main()

        assert result == 0
        mock_scheduler.start.assert_called_once()
        mock_scheduler.run_once.assert_not_called()

    @patch("sys.argv", ["main.py", "dashboard"])
    @patch("main.os.execvp")
    def test_dashboard_subcommand_execs_streamlit(self, mock_execvp):
        from main import main

        main()

        mock_execvp.assert_called_once()
        cmd, args = mock_execvp.call_args.args
        assert cmd == "streamlit"
        assert args[0] == "streamlit"
        assert args[1] == "run"
        assert args[2].endswith("dashboard.py")
