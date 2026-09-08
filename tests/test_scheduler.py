import threading
import time
from datetime import timedelta
from unittest.mock import MagicMock

from openings.models import utcnow
from openings.scheduler import MAIN_JOB, RETRY_JOB, Scheduler, request_run, run_requested


def test_run_once_returns_the_job_result(config):
    scheduler = Scheduler(config, lambda: True)
    assert scheduler.run_once() is True
    assert scheduler.run_count == 1 and scheduler.last_run_success is True
    failing = Scheduler(config, MagicMock(side_effect=RuntimeError("boom")))
    assert failing.run_once() is False


def test_execute_job_schedules_next_run_from_start_and_retries_on_failure(config):
    config.scheduler.interval_hours = 1
    config.scheduler.retry_delay_minutes = 5
    scheduler = Scheduler(config, lambda: False)
    scheduler._scheduler = MagicMock()
    scheduler._scheduler.get_job.return_value = None
    scheduler._execute_job()
    ids = [call.kwargs["id"] for call in scheduler._scheduler.add_job.call_args_list]
    assert ids == [MAIN_JOB, RETRY_JOB]
    main_call = scheduler._scheduler.add_job.call_args_list[0]
    next_run = main_call.kwargs["trigger"].run_date
    assert timedelta(minutes=59) < next_run - utcnow() <= timedelta(hours=1)


def test_manual_run_does_not_reschedule_the_interval(config):
    scheduler = Scheduler(config, lambda: True)
    scheduler._scheduler = MagicMock()
    scheduler._scheduler.get_job.return_value = None
    scheduler._execute_job(manual=True)
    assert scheduler._scheduler.add_job.call_count == 0


def test_retry_stops_at_max_retries(config):
    config.scheduler.max_retries = 2
    scheduler = Scheduler(config, lambda: False)
    scheduler._scheduler = MagicMock()
    scheduler._scheduler.get_job.return_value = None
    scheduler._execute_job()
    scheduler._execute_job(is_retry=True)
    ids = [call.kwargs["id"] for call in scheduler._scheduler.add_job.call_args_list]
    assert ids.count(RETRY_JOB) == 1


def test_long_run_skips_missed_slots(config):
    config.scheduler.interval_hours = 1
    scheduler = Scheduler(config, lambda: True)
    scheduler._scheduler = MagicMock()
    scheduler._schedule_next_run(utcnow() - timedelta(hours=2, minutes=30))
    run_date = scheduler._scheduler.add_job.call_args.kwargs["trigger"].run_date
    assert run_date > utcnow()


def test_run_now_flag(config):
    path = config.run_now_path
    assert run_requested(path) is False
    request_run(path)
    assert run_requested(path) is True
    scheduler = Scheduler(config, lambda: True)
    scheduler._scheduler = MagicMock()
    scheduler._scheduler.get_job.return_value = None
    scheduler._poll_run_now()
    assert run_requested(path) is False and scheduler.run_count == 1
    scheduler._poll_run_now()
    assert scheduler.run_count == 1


def test_start_runs_on_startup_and_stops(config):
    """A real BlockingScheduler in a thread: the startup run fires, then stop() returns."""
    config.scheduler.run_on_startup = True
    ran = threading.Event()

    def job() -> bool:
        ran.set()
        return True

    scheduler = Scheduler(config, job)
    thread = threading.Thread(target=scheduler.start, daemon=True)
    thread.start()
    assert ran.wait(5)
    deadline = time.time() + 5
    while scheduler._scheduler is None or not scheduler._scheduler.running:
        if time.time() > deadline:
            break
        time.sleep(0.05)
    scheduler.stop()
    thread.join(timeout=5)
    assert not thread.is_alive()
