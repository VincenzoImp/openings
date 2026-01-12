"""
Scheduler for Job Search Tool.

Provides automated periodic execution of job searches using APScheduler.
"""

from __future__ import annotations

import signal
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger

if TYPE_CHECKING:
    from config import Config

from logger import get_logger, log_section


class JobSearchScheduler:
    """
    Manages scheduled execution of job searches.

    Provides both single-shot and scheduled execution modes.
    Handles graceful shutdown and retry logic.
    """

    def __init__(self, config: Config, job_function: Callable[[], bool]):
        """
        Initialize the scheduler.

        Args:
            config: Configuration object.
            job_function: Function to execute for each search.
                         Should return True on success, False on failure.
        """
        self.config = config
        self.job_function = job_function
        self.logger = get_logger("scheduler")
        self._scheduler: BlockingScheduler | None = None
        self._running = False
        self._last_run_success = False
        self._run_count = 0

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown.

        Note: We don't call sys.exit() here because APScheduler's BlockingScheduler
        will handle the shutdown gracefully when stop() is called. Calling sys.exit()
        can interrupt cleanup and cause issues with database connections.
        """

        def shutdown_handler(signum: int, frame) -> None:
            self.logger.info(f"Received signal {signum}, requesting graceful shutdown...")
            self.stop()

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    def _execute_job(self) -> None:
        """Execute the job search with error handling and retry logic."""
        self._run_count += 1
        run_start = datetime.now()

        # Schedule next run immediately based on START time (not end time)
        # This ensures consistent interval from start-to-start
        if self._scheduler and self.config.scheduler.enabled:
            self._schedule_next_run(run_start)

        log_section(self.logger, f"SCHEDULED RUN #{self._run_count}")
        self.logger.info(f"Starting scheduled search at {run_start.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            self._last_run_success = self.job_function()

            if self._last_run_success:
                self.logger.info("Scheduled search completed successfully")
            else:
                self.logger.warning("Scheduled search completed with issues")

                # Retry logic
                if self.config.scheduler.retry_on_failure:
                    self._schedule_retry()

        except Exception as e:
            self._last_run_success = False
            self.logger.error(f"Scheduled search failed: {e}")

            if self.config.scheduler.retry_on_failure:
                self._schedule_retry()

        run_duration = (datetime.now() - run_start).total_seconds()
        self.logger.info(f"Run #{self._run_count} completed in {run_duration:.1f} seconds")

        # Log next scheduled run
        if self._scheduler and self.config.scheduler.enabled:
            jobs = self._scheduler.get_jobs()
            main_job = next((j for j in jobs if j.id == "main_job"), None)
            if main_job and main_job.next_run_time:
                self.logger.info(f"Next scheduled run: {main_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def _schedule_next_run(self, current_run_start: datetime) -> None:
        """
        Schedule the next run based on the START time of the current run.

        This ensures consistent start-to-start intervals regardless of how long
        each run takes to complete.

        If the run duration exceeds the interval, the next run is scheduled
        for the next future interval slot (skipping missed slots).

        Args:
            current_run_start: The start time of the current run.
        """
        interval = timedelta(hours=self.config.scheduler.interval_hours)
        next_run_time = current_run_start + interval
        now = datetime.now()

        # If next_run_time is in the past, find the next future slot
        if next_run_time <= now:
            # Calculate how many intervals have passed
            time_since_start = now - current_run_start
            intervals_passed = int(time_since_start / interval) + 1
            next_run_time = current_run_start + (interval * intervals_passed)
            self.logger.warning(
                f"Run duration exceeded interval. Skipped {intervals_passed - 1} slot(s). "
                f"Next run at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        if self._scheduler:
            self._scheduler.add_job(
                self._execute_job,
                trigger=DateTrigger(run_date=next_run_time),
                id="main_job",
                name="Job Search",
                replace_existing=True,
                max_instances=1,
            )
            self.logger.debug(f"Scheduled next run at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def _schedule_retry(self) -> None:
        """Schedule a retry after failure."""
        delay_minutes = self.config.scheduler.retry_delay_minutes
        self.logger.info(f"Scheduling retry in {delay_minutes} minutes...")

        if self._scheduler:
            retry_time = datetime.now() + timedelta(minutes=delay_minutes)
            self._scheduler.add_job(
                self._execute_job,
                trigger="date",
                run_date=retry_time,
                id="retry_job",
                replace_existing=True,
            )
            self.logger.info(f"Retry scheduled at {retry_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def run_once(self) -> bool:
        """
        Execute a single search (non-scheduled mode).

        Returns:
            True if search was successful, False otherwise.
        """
        self.logger.info("Running in single-shot mode")
        self._setup_signal_handlers()

        try:
            self._run_count += 1
            self._last_run_success = self.job_function()
            return self._last_run_success
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return False

    def start(self) -> None:
        """
        Start the scheduler in continuous mode.

        This method blocks until the scheduler is stopped.
        """
        if not self.config.scheduler.enabled:
            self.logger.info("Scheduler disabled, running once and exiting")
            self.run_once()
            return

        log_section(self.logger, "STARTING JOB SEARCH SCHEDULER")
        self.logger.info(f"Interval: {self.config.scheduler.interval_hours} hours")
        self.logger.info(f"Run on startup: {self.config.scheduler.run_on_startup}")
        self.logger.info(f"Retry on failure: {self.config.scheduler.retry_on_failure}")

        self._setup_signal_handlers()
        self._running = True

        # Initialize scheduler
        self._scheduler = BlockingScheduler()

        # Run immediately on startup if configured, otherwise schedule first run
        if self.config.scheduler.run_on_startup:
            self.logger.info("Executing initial run on startup...")
            self._execute_job()
        else:
            # Schedule first run after interval_hours from now
            first_run_time = datetime.now() + timedelta(hours=self.config.scheduler.interval_hours)
            self._scheduler.add_job(
                self._execute_job,
                trigger=DateTrigger(run_date=first_run_time),
                id="main_job",
                name="Job Search",
                max_instances=1,
            )
            self.logger.info(f"First run scheduled at {first_run_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Start the scheduler (this blocks)
        self.logger.info("Scheduler started, waiting for next run...")
        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Scheduler interrupted")
            self.stop()

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        if self._scheduler and self._scheduler.running:
            self.logger.info("Stopping scheduler...")
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    @property
    def is_running(self) -> bool:
        """Check if scheduler is currently running."""
        return self._running

    @property
    def last_run_success(self) -> bool:
        """Check if the last run was successful."""
        return self._last_run_success

    @property
    def run_count(self) -> int:
        """Get total number of runs executed."""
        return self._run_count


def create_scheduler(config: Config, job_function: Callable[[], bool]) -> JobSearchScheduler:
    """
    Factory function to create a JobSearchScheduler.

    Args:
        config: Configuration object.
        job_function: Function to execute for each search.

    Returns:
        Configured JobSearchScheduler instance.
    """
    return JobSearchScheduler(config, job_function)
