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


# ════════════════════════════════════════════════════════════════════════════
# Phase 3: Additional coverage
# ════════════════════════════════════════════════════════════════════════════


class TestPrepareRuntime:
    """Tests for _prepare_runtime startup logic."""

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    def test_calls_recalc_and_reconcile_scheduled(
        self,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import _prepare_runtime

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 10}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        config, db = _prepare_runtime(scheduled=True)

        mock_recalc.assert_called_once_with(mock_db, mock_config)
        mock_db.reconcile_with_config.assert_called_once_with(mock_config)
        assert config is mock_config
        assert db is mock_db

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    def test_skips_recalc_on_empty_db(
        self,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import _prepare_runtime

        mock_config = _make_runtime_config_mock()
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 0}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        _prepare_runtime(scheduled=False)

        mock_recalc.assert_not_called()
        mock_db.reconcile_with_config.assert_called_once()

    @patch("main.NotificationManager")
    @patch("main.create_reconcile_notification_data")
    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    def test_sends_reconcile_notification_when_deletions(
        self,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
        mock_create_data,
        mock_manager_cls,
    ):
        from main import _prepare_runtime

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_get_config.return_value = mock_config

        report = ReconciliationReport(deleted_below_score=3)
        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.reconcile_with_config.return_value = report
        mock_get_db.return_value = mock_db

        mock_mgr = MagicMock()
        mock_mgr.has_configured_notifiers.return_value = True
        mock_manager_cls.return_value = mock_mgr

        _prepare_runtime(scheduled=False)

        mock_create_data.assert_called_once_with(report)
        mock_mgr.send_reconcile_sync.assert_called_once()

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    def test_no_reconcile_notification_when_zero_deletions(
        self,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import _prepare_runtime

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_get_config.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.reconcile_with_config.return_value = _make_empty_report()
        mock_get_db.return_value = mock_db

        _prepare_runtime(scheduled=False)
        # No NotificationManager should be created

    @patch("main.get_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.recalculate_all_scores")
    def test_vector_sync_on_deletions(
        self,
        mock_recalc,
        mock_get_db,
        mock_setup_log,
        mock_get_config,
    ):
        from main import _prepare_runtime

        mock_config = _make_runtime_config_mock()
        mock_config.vector_search.enabled = True
        mock_config.vector_search.backfill_on_startup = True
        mock_config.vector_search.batch_size = 50
        mock_get_config.return_value = mock_config

        report = ReconciliationReport(deleted_stale=2)
        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}
        mock_db.reconcile_with_config.return_value = report
        mock_get_db.return_value = mock_db

        with (
            patch("vector_store.get_vector_store"),
            patch("vector_commands.sync_deletions") as mock_sync,
            patch("vector_commands.backfill_embeddings") as mock_backfill,
        ):
            mock_backfill.return_value = 3
            _prepare_runtime(scheduled=False)

            mock_sync.assert_called_once()
            mock_backfill.assert_called_once()


class TestRunJobSearchIntegration:
    """Tests where scoring and partitioning run for real against a temp DB."""

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.print_top_jobs")
    def test_jobs_above_save_threshold_are_saved(
        self,
        mock_print_top,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
        temp_db,
    ):
        """Mock search_jobs but let score_jobs and partition run for real."""
        from config import Config, ScoringConfig
        from main import run_job_search

        config = Config(
            scoring=ScoringConfig(
                save_threshold=10,
                notify_threshold=50,
                weights={"tech": 20},
                keywords={"tech": ["python"]},
            ),
        )
        config.notifications = MagicMock()
        config.notifications.enabled = False
        config.vector_search = MagicMock()
        config.vector_search.enabled = False
        config.vector_search.embed_on_save = False

        mock_reload.return_value = config
        mock_get_db.return_value = temp_db

        # Job with "python" scores 20, job without scores 0
        df = pd.DataFrame(
            [
                {
                    "title": "Python Dev",
                    "company": "A",
                    "location": "NYC",
                    "description": "python work",
                },
                {
                    "title": "Chef",
                    "company": "B",
                    "location": "NYC",
                    "description": "cooking",
                },
            ]
        )
        mock_search.return_value = (df, MagicMock())

        result = run_job_search()

        assert result is True
        all_jobs = temp_db.get_all_jobs()
        titles = {j.title for j in all_jobs}
        assert "Python Dev" in titles
        assert "Chef" not in titles  # Score 0 < save_threshold 10

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.print_top_jobs")
    @patch("main._send_notifications")
    def test_notifications_only_for_notify_threshold(
        self,
        mock_send_notif,
        mock_print_top,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
        temp_db,
    ):
        """Jobs between save and notify threshold should save but not notify."""
        from config import Config, ScoringConfig
        from main import run_job_search

        config = Config(
            scoring=ScoringConfig(
                save_threshold=0,
                notify_threshold=30,
                weights={"tech": 20},
                keywords={"tech": ["python"]},
            ),
        )
        config.notifications = MagicMock()
        config.notifications.enabled = True
        config.vector_search = MagicMock()
        config.vector_search.enabled = False
        config.vector_search.embed_on_save = False

        mock_reload.return_value = config
        mock_get_db.return_value = temp_db

        # "python" -> score 20 (above save=0 but below notify=30)
        df = pd.DataFrame(
            [
                {
                    "title": "Python Dev",
                    "company": "A",
                    "location": "NYC",
                    "description": "python",
                },
            ]
        )
        mock_search.return_value = (df, MagicMock())

        run_job_search()

        # Saved to DB
        assert len(temp_db.get_all_jobs()) == 1
        # But no notifications because score 20 < notify_threshold 30
        mock_send_notif.assert_not_called()

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    @patch("main.print_top_jobs")
    def test_blacklisted_jobs_excluded(
        self,
        mock_print_top,
        mock_search,
        mock_banner,
        mock_get_db,
        mock_setup_log,
        mock_reload,
        temp_db,
    ):
        from config import Config, ScoringConfig
        from main import run_job_search
        from models import Job

        config = Config(
            scoring=ScoringConfig(
                save_threshold=0,
                notify_threshold=100,
                weights={"tech": 20},
                keywords={"tech": ["python"]},
            ),
        )
        config.notifications = MagicMock()
        config.notifications.enabled = False
        config.vector_search = MagicMock()
        config.vector_search.enabled = False
        config.vector_search.embed_on_save = False
        mock_reload.return_value = config
        mock_get_db.return_value = temp_db

        # Blacklist a job first
        bl_job = Job(title="Python Dev", company="A", location="NYC")
        temp_db.save_job(bl_job)
        temp_db.blacklist_job(bl_job.job_id)

        df = pd.DataFrame(
            [
                {
                    "title": "Python Dev",
                    "company": "A",
                    "location": "NYC",
                    "description": "python",
                },
            ]
        )
        mock_search.return_value = (df, MagicMock())

        run_job_search()

        assert len(temp_db.get_all_jobs()) == 0

    @patch("main.reload_config")
    @patch("main.setup_logging")
    @patch("main.get_database")
    @patch("main.print_banner")
    @patch("main.search_jobs")
    def test_empty_search_results(
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
    def test_empty_dataframe_search_results(
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

        mock_search.return_value = (pd.DataFrame(), MagicMock())

        assert run_job_search() is True


class TestSendNotifications:
    """Tests for _send_notifications helper."""

    @patch("main.NotificationManager")
    def test_disabled_notifications(self, mock_manager_cls):
        from main import _send_notifications

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = False

        _send_notifications(mock_config, MagicMock(), [], 0, 0)
        mock_manager_cls.assert_not_called()

    @patch("main.NotificationManager")
    def test_no_configured_notifiers(self, mock_manager_cls):
        from main import _send_notifications

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_config.notifications.telegram.include_top_overall = False

        mock_mgr = MagicMock()
        mock_mgr.has_configured_notifiers.return_value = False
        mock_manager_cls.return_value = mock_mgr

        _send_notifications(mock_config, MagicMock(), [], 0, 0)
        mock_mgr.send_all_sync.assert_not_called()

    @patch("main.create_notification_data")
    @patch("main.NotificationManager")
    def test_sends_with_new_jobs(self, mock_manager_cls, mock_create_data):
        from main import _send_notifications
        from models import JobDBRecord

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_config.notifications.telegram.include_top_overall = False
        mock_config.scoring.notify_threshold = 10

        mock_mgr = MagicMock()
        mock_mgr.has_configured_notifiers.return_value = True
        mock_mgr.send_all_sync.return_value = {"telegram": True}
        mock_manager_cls.return_value = mock_mgr

        from datetime import date

        job = JobDBRecord(
            job_id="abc123",
            title="Dev",
            company="Co",
            location="NYC",
            relevance_score=30,
            first_seen=date.today(),
            last_seen=date.today(),
        )

        _send_notifications(mock_config, MagicMock(), [job], 5, 100)

        mock_create_data.assert_called_once()
        mock_mgr.send_all_sync.assert_called_once()

    @patch("main.create_notification_data")
    @patch("main.NotificationManager")
    def test_includes_top_overall(self, mock_manager_cls, mock_create_data):
        from main import _send_notifications
        from models import JobDBRecord

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_config.notifications.telegram.include_top_overall = True
        mock_config.notifications.telegram.max_top_overall = 5
        mock_config.scoring.notify_threshold = 10

        mock_mgr = MagicMock()
        mock_mgr.has_configured_notifiers.return_value = True
        mock_mgr.send_all_sync.return_value = {"telegram": True}
        mock_manager_cls.return_value = mock_mgr

        mock_db = MagicMock()
        from datetime import date

        top_job = JobDBRecord(
            job_id="top1",
            title="Top Dev",
            company="Co",
            location="NYC",
            relevance_score=80,
            first_seen=date.today(),
            last_seen=date.today(),
        )
        mock_db.get_top_jobs.return_value = [top_job]
        mock_db.get_job_count.return_value = 50

        new_job = JobDBRecord(
            job_id="new1",
            title="New Dev",
            company="Co",
            location="NYC",
            relevance_score=30,
            first_seen=date.today(),
            last_seen=date.today(),
        )

        _send_notifications(mock_config, mock_db, [new_job], 5, 100)

        mock_db.get_top_jobs.assert_called_once_with(limit=5, min_score=10)
        call_kwargs = mock_create_data.call_args
        assert call_kwargs.kwargs.get("total_jobs_in_db") == 50 or (
            len(call_kwargs.args) >= 6 and call_kwargs.args[5] == 50
        )


class TestSendEmptyNotification:
    """Tests for _send_empty_notification."""

    @patch("main.NotificationManager")
    def test_disabled_notifications(self, mock_manager_cls):
        from main import _send_empty_notification

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = False

        _send_empty_notification(mock_config, MagicMock())
        mock_manager_cls.assert_not_called()

    @patch("main.create_notification_data")
    @patch("main.NotificationManager")
    def test_sends_empty_with_top_overall(self, mock_manager_cls, mock_create_data):
        from main import _send_empty_notification

        mock_config = _make_runtime_config_mock()
        mock_config.notifications.enabled = True
        mock_config.notifications.telegram.include_top_overall = True
        mock_config.notifications.telegram.max_top_overall = 10
        mock_config.scoring.notify_threshold = 10

        mock_mgr = MagicMock()
        mock_mgr.has_configured_notifiers.return_value = True
        mock_mgr.send_all_sync.return_value = {"telegram": True}
        mock_manager_cls.return_value = mock_mgr

        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {
            "seen_today": 5,
            "avg_relevance_score": 15,
        }
        mock_db.get_top_jobs.return_value = []
        mock_db.get_job_count.return_value = 20

        _send_empty_notification(mock_config, mock_db)

        mock_create_data.assert_called_once()
        mock_mgr.send_all_sync.assert_called_once()


class TestCmdOnce:
    """Tests for _cmd_once."""

    @patch("main._prepare_runtime")
    @patch("main.create_scheduler")
    def test_calls_prepare_and_run_once(self, mock_create_sched, mock_prepare):
        from main import _cmd_once

        mock_config = _make_runtime_config_mock()
        mock_prepare.return_value = (mock_config, MagicMock())

        mock_sched = MagicMock()
        mock_sched.run_once.return_value = True
        mock_create_sched.return_value = mock_sched

        result = _cmd_once()

        assert result == 0
        mock_prepare.assert_called_once_with(scheduled=False)
        mock_sched.run_once.assert_called_once()

    @patch("main._prepare_runtime")
    @patch("main.create_scheduler")
    def test_returns_1_on_failure(self, mock_create_sched, mock_prepare):
        from main import _cmd_once

        mock_config = _make_runtime_config_mock()
        mock_prepare.return_value = (mock_config, MagicMock())

        mock_sched = MagicMock()
        mock_sched.run_once.return_value = False
        mock_create_sched.return_value = mock_sched

        assert _cmd_once() == 1

    @patch("main._prepare_runtime")
    @patch("main.create_scheduler")
    def test_keyboard_interrupt(self, mock_create_sched, mock_prepare):
        from main import _cmd_once

        mock_config = _make_runtime_config_mock()
        mock_prepare.return_value = (mock_config, MagicMock())

        mock_sched = MagicMock()
        mock_sched.run_once.side_effect = KeyboardInterrupt
        mock_create_sched.return_value = mock_sched

        assert _cmd_once() == 0


class TestCmdScheduler:
    """Tests for _cmd_scheduler."""

    @patch("main._prepare_runtime")
    @patch("main.create_scheduler")
    def test_normal_start(self, mock_create_sched, mock_prepare):
        from main import _cmd_scheduler

        mock_config = _make_runtime_config_mock()
        mock_prepare.return_value = (mock_config, MagicMock())

        mock_sched = MagicMock()
        mock_create_sched.return_value = mock_sched

        result = _cmd_scheduler()

        assert result == 0
        mock_prepare.assert_called_once_with(scheduled=True)
        mock_sched.start.assert_called_once()

    @patch("main._prepare_runtime")
    @patch("main.create_scheduler")
    def test_keyboard_interrupt(self, mock_create_sched, mock_prepare):
        from main import _cmd_scheduler

        mock_config = _make_runtime_config_mock()
        mock_prepare.return_value = (mock_config, MagicMock())

        mock_sched = MagicMock()
        mock_sched.start.side_effect = KeyboardInterrupt
        mock_create_sched.return_value = mock_sched

        assert _cmd_scheduler() == 0

    @patch("main._prepare_runtime")
    @patch("main.create_scheduler")
    def test_fatal_error(self, mock_create_sched, mock_prepare):
        from main import _cmd_scheduler

        mock_config = _make_runtime_config_mock()
        mock_prepare.return_value = (mock_config, MagicMock())

        mock_sched = MagicMock()
        mock_sched.start.side_effect = RuntimeError("boom")
        mock_create_sched.return_value = mock_sched

        assert _cmd_scheduler() == 1
