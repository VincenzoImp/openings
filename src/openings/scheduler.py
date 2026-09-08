"""The continuous loop: collect on a start-to-start interval, retry failures,
run on demand when ``{DATA_DIR}/run-now`` appears."""

from __future__ import annotations

import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from openings.logger import get_logger, log_section
from openings.models import utcnow

if TYPE_CHECKING:
    from openings.config import Config

RUN_NOW_POLL_SECONDS = 30
MAIN_JOB = "main"
RETRY_JOB = "retry"
RUN_NOW_JOB = "run-now"


def request_run(path: Path) -> None:
    """Ask the scheduler for a collection as soon as possible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(utcnow().isoformat(), encoding="utf-8")


def run_requested(path: Path) -> bool:
    return path.is_file()


class Scheduler:
    """Single-shot or continuous execution of the collection function."""

    def __init__(self, config: Config, job_function: Callable[[], bool]):
        self.config = config
        self.job_function = job_function
        self.logger = get_logger("scheduler")
        self._scheduler: BlockingScheduler | None = None
        self._last_run_success = False
        self._run_count = 0
        self._consecutive_failures = 0

    # ------------------------------------------------------------------

    def _stamp(self, moment: datetime | None = None) -> str:
        return (
            (moment or utcnow())
            .astimezone(self.config.logging.zone)
            .strftime("%Y-%m-%d %H:%M:%S %Z")
        )

    def _setup_signal_handlers(self) -> None:
        def shutdown_handler(signum: int, frame) -> None:
            self.logger.info("Received signal %s, shutting down", signum)
            self.stop()

        try:
            signal.signal(signal.SIGINT, shutdown_handler)
            signal.signal(signal.SIGTERM, shutdown_handler)
        except ValueError:
            # Signal handlers can only be installed from the main thread.
            self.logger.debug("Not the main thread; signal handlers not installed")

    def _execute_job(self, *, is_retry: bool = False, manual: bool = False) -> None:
        self._run_count += 1
        run_start = utcnow()
        # The interval is start-to-start: schedule the next run before this one begins.
        if self._scheduler and not is_retry and not manual:
            self._schedule_next_run(run_start)

        label = "RETRY RUN" if is_retry else "REQUESTED RUN" if manual else "SCHEDULED RUN"
        log_section(self.logger, f"{label} #{self._run_count}")
        self.logger.info("Started at %s", self._stamp(run_start))

        try:
            self._last_run_success = self.job_function()
            if self._last_run_success:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                self.logger.warning(
                    "Run finished with failures (consecutive: %d)", self._consecutive_failures
                )
                if self.config.scheduler.retry_on_failure:
                    self._schedule_retry()
        except Exception as exc:  # noqa: BLE001 - the loop must survive any run
            self._last_run_success = False
            self._consecutive_failures += 1
            self.logger.error(
                "Run failed (consecutive failures: %d): %s", self._consecutive_failures, exc
            )
            if self.config.scheduler.retry_on_failure:
                self._schedule_retry()

        self.logger.info(
            "Run #%d took %.1f seconds",
            self._run_count,
            (utcnow() - run_start).total_seconds(),
        )
        if self._scheduler and not is_retry:
            main = self._scheduler.get_job(MAIN_JOB)
            next_run = getattr(main, "next_run_time", None) if main else None
            if next_run:
                self.logger.info("Next scheduled run: %s", self._stamp(next_run))

    def _schedule_next_run(self, current_run_start: datetime) -> None:
        interval = timedelta(hours=self.config.scheduler.interval_hours)
        next_run_time = current_run_start + interval
        now = utcnow()
        if next_run_time <= now:
            passed = int((now - current_run_start) / interval) + 1
            next_run_time = current_run_start + interval * passed
            self.logger.warning(
                "Run duration exceeded the interval; skipped %d slot(s), next at %s",
                passed - 1,
                self._stamp(next_run_time),
            )
        if self._scheduler:
            self._scheduler.add_job(
                self._execute_job,
                trigger=DateTrigger(run_date=next_run_time),
                id=MAIN_JOB,
                name="Collection",
                kwargs={"is_retry": False},
                replace_existing=True,
                max_instances=1,
            )

    def _schedule_retry(self) -> None:
        max_retries = self.config.scheduler.max_retries
        if max_retries > 0 and self._consecutive_failures >= max_retries:
            self.logger.error("Max retries reached (%d); waiting for the next slot", max_retries)
            return
        delay = timedelta(minutes=self.config.scheduler.retry_delay_minutes)
        if self._scheduler:
            retry_time = utcnow() + delay
            self._scheduler.add_job(
                self._execute_job,
                trigger=DateTrigger(run_date=retry_time),
                id=RETRY_JOB,
                name="Retry",
                kwargs={"is_retry": True},
                replace_existing=True,
            )
            self.logger.info(
                "Retry %d/%s at %s",
                self._consecutive_failures,
                max_retries or "unlimited",
                self._stamp(retry_time),
            )

    def _poll_run_now(self) -> None:
        path = self.config.run_now_path
        if not run_requested(path):
            return
        try:
            path.unlink()
        except OSError:
            return
        self.logger.info("Run requested through %s", path)
        self._execute_job(manual=True)

    # ------------------------------------------------------------------

    def run_once(self) -> bool:
        """Execute one collection and return whether it succeeded."""
        self._setup_signal_handlers()
        try:
            self._run_count += 1
            self._last_run_success = self.job_function()
            return self._last_run_success
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Run failed: %s", exc)
            return False

    def start(self) -> None:
        """Block until stopped, collecting on the configured interval."""
        log_section(self.logger, "STARTING SCHEDULER")
        self.logger.info("Interval: %d hours", self.config.scheduler.interval_hours)
        self.logger.info("Run on startup: %s", self.config.scheduler.run_on_startup)
        self.logger.info("Retry on failure: %s", self.config.scheduler.retry_on_failure)
        self._setup_signal_handlers()
        self._scheduler = BlockingScheduler(timezone="UTC")
        self._scheduler.add_job(
            self._poll_run_now,
            trigger=IntervalTrigger(seconds=RUN_NOW_POLL_SECONDS),
            id=RUN_NOW_JOB,
            name="Run-now poll",
            max_instances=1,
        )
        if self.config.scheduler.run_on_startup:
            self._execute_job()
        else:
            first_run = utcnow() + timedelta(hours=self.config.scheduler.interval_hours)
            self._scheduler.add_job(
                self._execute_job,
                trigger=DateTrigger(run_date=first_run),
                id=MAIN_JOB,
                name="Collection",
                kwargs={"is_retry": False},
                max_instances=1,
            )
            self.logger.info("First run at %s", self._stamp(first_run))
        self.logger.info("Waiting for the next run")
        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self) -> None:
        if self._scheduler and self._scheduler.running:
            self.logger.info("Stopping")
            self._scheduler.shutdown(wait=False)
        self._scheduler = None

    @property
    def last_run_success(self) -> bool:
        return self._last_run_success

    @property
    def run_count(self) -> int:
        return self._run_count


def create_scheduler(config: Config, job_function: Callable[[], bool]) -> Scheduler:
    return Scheduler(config, job_function)
