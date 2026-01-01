"""Tests for scheduler module.

Tests for APScheduler integration including:
- Scheduler initialization and configuration
- Single-shot mode execution
- Scheduled mode execution
- Retry logic on failure
- Signal handling
"""

import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import Config, SchedulerConfig
from scheduler import JobSearchScheduler, create_scheduler


# =============================================================================
# TEST SCHEDULER INITIALIZATION
# =============================================================================


class TestJobSearchSchedulerInit:
    """Tests for JobSearchScheduler initialization."""

    @pytest.fixture
    def scheduler_config(self):
        """Create a SchedulerConfig for testing."""
        return SchedulerConfig(
            enabled=True,
            interval_hours=12,
            run_on_startup=True,
            retry_on_failure=True,
            retry_delay_minutes=15,
        )

    @pytest.fixture
    def config(self, scheduler_config):
        """Create a Config with scheduler settings."""
        return Config(scheduler=scheduler_config)

    @pytest.fixture
    def mock_job_function(self):
        """Create a mock job function."""
        return MagicMock(return_value=True)

    def test_init_stores_config(self, config, mock_job_function):
        """Test that config is stored on initialization."""
        scheduler = JobSearchScheduler(config, mock_job_function)

        assert scheduler.config == config
        assert scheduler.job_function == mock_job_function

    def test_init_defaults(self, config, mock_job_function):
        """Test initial state of scheduler."""
        scheduler = JobSearchScheduler(config, mock_job_function)

        assert scheduler.is_running is False
        assert scheduler.last_run_success is False
        assert scheduler.run_count == 0
        assert scheduler._scheduler is None

    def test_create_scheduler_factory(self, config, mock_job_function):
        """Test create_scheduler factory function."""
        scheduler = create_scheduler(config, mock_job_function)

        assert isinstance(scheduler, JobSearchScheduler)
        assert scheduler.config == config


# =============================================================================
# TEST SINGLE-SHOT MODE
# =============================================================================


class TestJobSearchSchedulerRunOnce:
    """Tests for single-shot (run_once) execution."""

    @pytest.fixture
    def scheduler_config(self):
        """Create a disabled scheduler config for single-shot mode."""
        return SchedulerConfig(enabled=False)

    @pytest.fixture
    def config(self, scheduler_config):
        """Create a Config with disabled scheduler."""
        return Config(scheduler=scheduler_config)

    def test_run_once_success(self, config):
        """Test run_once returns True on successful job."""
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        result = scheduler.run_once()

        assert result is True
        assert scheduler.last_run_success is True
        assert scheduler.run_count == 1
        mock_job.assert_called_once()

    def test_run_once_failure(self, config):
        """Test run_once returns False when job returns False."""
        mock_job = MagicMock(return_value=False)
        scheduler = JobSearchScheduler(config, mock_job)

        result = scheduler.run_once()

        assert result is False
        assert scheduler.last_run_success is False
        assert scheduler.run_count == 1

    def test_run_once_exception(self, config):
        """Test run_once handles exceptions gracefully."""
        mock_job = MagicMock(side_effect=Exception("Job failed"))
        scheduler = JobSearchScheduler(config, mock_job)

        result = scheduler.run_once()

        assert result is False
        assert scheduler.run_count == 1

    def test_run_once_increments_run_count(self, config):
        """Test that run_once increments run count each time."""
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        scheduler.run_once()
        scheduler.run_once()
        scheduler.run_once()

        assert scheduler.run_count == 3


# =============================================================================
# TEST SCHEDULED MODE
# =============================================================================


class TestJobSearchSchedulerScheduledMode:
    """Tests for scheduled (continuous) mode execution."""

    @pytest.fixture
    def scheduler_config(self):
        """Create an enabled scheduler config."""
        return SchedulerConfig(
            enabled=True,
            interval_hours=1,
            run_on_startup=True,
            retry_on_failure=True,
            retry_delay_minutes=5,
        )

    @pytest.fixture
    def config(self, scheduler_config):
        """Create a Config with enabled scheduler."""
        return Config(scheduler=scheduler_config)

    def test_start_runs_on_startup(self, config):
        """Test that start() runs job immediately when run_on_startup is True."""
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        # Mock BlockingScheduler to avoid blocking
        with patch("scheduler.BlockingScheduler") as mock_blocking:
            mock_sched = MagicMock()
            mock_blocking.return_value = mock_sched
            # Make start() raise to exit immediately
            mock_sched.start.side_effect = KeyboardInterrupt()

            try:
                scheduler.start()
            except SystemExit:
                pass

            # Job should have been called once (on startup)
            mock_job.assert_called_once()

    def test_start_skips_startup_run_when_disabled(self, scheduler_config):
        """Test that start() skips initial run when run_on_startup is False."""
        scheduler_config.run_on_startup = False
        config = Config(scheduler=scheduler_config)
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        with patch("scheduler.BlockingScheduler") as mock_blocking:
            mock_sched = MagicMock()
            mock_blocking.return_value = mock_sched
            mock_sched.start.side_effect = KeyboardInterrupt()

            try:
                scheduler.start()
            except SystemExit:
                pass

            # Job should NOT have been called
            mock_job.assert_not_called()

    def test_start_adds_interval_job(self, config):
        """Test that start() adds an interval job to the scheduler."""
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        with patch("scheduler.BlockingScheduler") as mock_blocking:
            mock_sched = MagicMock()
            mock_blocking.return_value = mock_sched
            mock_sched.start.side_effect = KeyboardInterrupt()

            try:
                scheduler.start()
            except SystemExit:
                pass

            # Should have called add_job
            mock_sched.add_job.assert_called_once()

    def test_start_disabled_scheduler_runs_once(self):
        """Test that start() runs once and exits when scheduler is disabled."""
        config = Config(scheduler=SchedulerConfig(enabled=False))
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        # Should run once and return (not block)
        scheduler.start()

        mock_job.assert_called_once()


# =============================================================================
# TEST EXECUTE JOB
# =============================================================================


class TestJobSearchSchedulerExecuteJob:
    """Tests for _execute_job method."""

    @pytest.fixture
    def config(self):
        """Create a Config with retry enabled."""
        return Config(
            scheduler=SchedulerConfig(
                enabled=True,
                retry_on_failure=True,
                retry_delay_minutes=5,
            )
        )

    def test_execute_job_success(self, config):
        """Test _execute_job on successful run."""
        mock_job = MagicMock(return_value=True)
        scheduler = JobSearchScheduler(config, mock_job)

        scheduler._execute_job()

        assert scheduler.last_run_success is True
        assert scheduler.run_count == 1

    def test_execute_job_failure_with_retry(self, config):
        """Test _execute_job schedules retry on failure."""
        mock_job = MagicMock(return_value=False)
        scheduler = JobSearchScheduler(config, mock_job)

        # Set up mock scheduler
        with patch("scheduler.BlockingScheduler") as mock_blocking:
            mock_sched = MagicMock()
            mock_blocking.return_value = mock_sched
            scheduler._scheduler = mock_sched

            scheduler._execute_job()

            assert scheduler.last_run_success is False
            # Should have scheduled a retry
            mock_sched.add_job.assert_called()

    def test_execute_job_exception_with_retry(self, config):
        """Test _execute_job schedules retry on exception."""
        mock_job = MagicMock(side_effect=Exception("Error"))
        scheduler = JobSearchScheduler(config, mock_job)

        with patch("scheduler.BlockingScheduler") as mock_blocking:
            mock_sched = MagicMock()
            mock_blocking.return_value = mock_sched
            scheduler._scheduler = mock_sched

            scheduler._execute_job()

            assert scheduler.last_run_success is False
            # Should have scheduled a retry
            mock_sched.add_job.assert_called()

    def test_execute_job_no_retry_when_disabled(self):
        """Test _execute_job doesn't retry when retry_on_failure is False."""
        config = Config(
            scheduler=SchedulerConfig(
                enabled=True,
                retry_on_failure=False,
            )
        )
        mock_job = MagicMock(return_value=False)
        scheduler = JobSearchScheduler(config, mock_job)

        with patch("scheduler.BlockingScheduler") as mock_blocking:
            mock_sched = MagicMock()
            mock_blocking.return_value = mock_sched
            scheduler._scheduler = mock_sched

            scheduler._execute_job()

            # Should NOT have scheduled a retry
            mock_sched.add_job.assert_not_called()


# =============================================================================
# TEST SCHEDULE RETRY
# =============================================================================


class TestJobSearchSchedulerRetry:
    """Tests for retry scheduling functionality."""

    @pytest.fixture
    def config(self):
        """Create a Config with retry settings."""
        return Config(
            scheduler=SchedulerConfig(
                enabled=True,
                retry_on_failure=True,
                retry_delay_minutes=15,
            )
        )

    def test_schedule_retry_adds_job(self, config):
        """Test _schedule_retry adds a retry job."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)

        mock_sched = MagicMock()
        scheduler._scheduler = mock_sched

        scheduler._schedule_retry()

        mock_sched.add_job.assert_called_once()
        call_kwargs = mock_sched.add_job.call_args
        assert call_kwargs.kwargs.get("trigger") == "date"
        assert call_kwargs.kwargs.get("id") == "retry_job"
        assert call_kwargs.kwargs.get("replace_existing") is True

    def test_schedule_retry_uses_configured_delay(self, config):
        """Test retry uses configured delay."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)

        mock_sched = MagicMock()
        scheduler._scheduler = mock_sched

        before = datetime.now()
        scheduler._schedule_retry()
        after = datetime.now()

        # Get the run_date from the call
        call_kwargs = mock_sched.add_job.call_args
        run_date = call_kwargs.kwargs.get("run_date")

        # Should be approximately 15 minutes from now
        expected_min = before + timedelta(minutes=15)
        expected_max = after + timedelta(minutes=15) + timedelta(seconds=1)

        assert expected_min <= run_date <= expected_max

    def test_schedule_retry_no_scheduler(self, config):
        """Test _schedule_retry handles no scheduler gracefully."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)
        scheduler._scheduler = None

        # Should not raise
        scheduler._schedule_retry()


# =============================================================================
# TEST STOP
# =============================================================================


class TestJobSearchSchedulerStop:
    """Tests for scheduler stop functionality."""

    @pytest.fixture
    def config(self):
        """Create a Config for testing."""
        return Config(scheduler=SchedulerConfig(enabled=True))

    def test_stop_sets_running_false(self, config):
        """Test stop() sets _running to False."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)
        scheduler._running = True

        scheduler.stop()

        assert scheduler.is_running is False

    def test_stop_shuts_down_scheduler(self, config):
        """Test stop() shuts down the APScheduler."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)

        mock_sched = MagicMock()
        mock_sched.running = True
        scheduler._scheduler = mock_sched

        scheduler.stop()

        mock_sched.shutdown.assert_called_once_with(wait=False)
        assert scheduler._scheduler is None

    def test_stop_no_scheduler(self, config):
        """Test stop() handles no scheduler gracefully."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)
        scheduler._scheduler = None

        # Should not raise
        scheduler.stop()


# =============================================================================
# TEST PROPERTIES
# =============================================================================


class TestJobSearchSchedulerProperties:
    """Tests for scheduler property accessors."""

    @pytest.fixture
    def scheduler(self):
        """Create a scheduler instance for testing."""
        config = Config(scheduler=SchedulerConfig(enabled=True))
        return JobSearchScheduler(config, lambda: True)

    def test_is_running_property(self, scheduler):
        """Test is_running property."""
        assert scheduler.is_running is False

        scheduler._running = True
        assert scheduler.is_running is True

    def test_last_run_success_property(self, scheduler):
        """Test last_run_success property."""
        assert scheduler.last_run_success is False

        scheduler._last_run_success = True
        assert scheduler.last_run_success is True

    def test_run_count_property(self, scheduler):
        """Test run_count property."""
        assert scheduler.run_count == 0

        scheduler._run_count = 5
        assert scheduler.run_count == 5


# =============================================================================
# TEST SIGNAL HANDLERS
# =============================================================================


class TestJobSearchSchedulerSignals:
    """Tests for signal handler setup."""

    @pytest.fixture
    def config(self):
        """Create a Config for testing."""
        return Config(scheduler=SchedulerConfig(enabled=True))

    def test_setup_signal_handlers(self, config):
        """Test _setup_signal_handlers sets up SIGINT and SIGTERM."""
        mock_job = MagicMock()
        scheduler = JobSearchScheduler(config, mock_job)

        with patch("signal.signal") as mock_signal:
            scheduler._setup_signal_handlers()

            # Should set up SIGINT and SIGTERM handlers
            calls = mock_signal.call_args_list
            signals_set = [c[0][0] for c in calls]

            assert signal.SIGINT in signals_set
            assert signal.SIGTERM in signals_set
