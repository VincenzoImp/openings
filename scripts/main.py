#!/usr/bin/env python3
"""
Job Search Tool - Main Entry Point.

Unified entry point that supports both single-shot and scheduled execution modes.
Integrates job search, database persistence, and notifications.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from config import get_config, reload_config
from database import get_database, recalculate_all_scores
from logger import get_logger, log_section, setup_logging
from models import generate_job_id
from notifier import (
    NotificationManager,
    create_notification_data,
    create_reconcile_notification_data,
)
from scheduler import create_scheduler
from scoring import partition_by_thresholds, score_jobs
from search_jobs import (
    print_banner,
    print_top_jobs,
    search_jobs,
)

if TYPE_CHECKING:
    from config import Config
    from database import JobDatabase
    from models import JobDBRecord


def _extract_job_ids_from_dataframe(jobs_df) -> list[str]:
    """Build ordered unique job IDs from a result DataFrame."""
    job_ids = []
    seen_ids: set[str] = set()
    for record in jobs_df.to_dict("records"):
        job_id = generate_job_id(
            str(record.get("title", "")),
            str(record.get("company", "")),
            str(record.get("location", "")),
        )
        if job_id not in seen_ids:
            seen_ids.add(job_id)
            job_ids.append(job_id)
    return job_ids


def _get_current_run_new_job_ids(db: JobDatabase, jobs_df) -> list[str]:
    """Return the subset of result IDs that are new in the current run."""
    current_job_ids = _extract_job_ids_from_dataframe(jobs_df)
    new_job_id_set = db.get_new_job_ids(current_job_ids)
    return [job_id for job_id in current_job_ids if job_id in new_job_id_set]


def run_job_search() -> bool:
    """Execute a single job search iteration.

    Pipeline: reload config → search → score → partition by save/notify
    thresholds → exclude blacklist → upsert → embed → notify on the
    ``to_notify`` partition.
    """
    config = reload_config()
    logger = setup_logging(config)

    try:
        print_banner(config)

        db = get_database(config)
        db_stats = db.get_statistics()
        logger.info(f"Database: {db_stats['total_jobs']} jobs tracked")

        all_jobs, summary = search_jobs(config)

        if all_jobs is None or len(all_jobs) == 0:
            logger.warning("No jobs found in this search")
            _send_empty_notification(config, db)
            return True

        scored = score_jobs(all_jobs, config)
        partitions = partition_by_thresholds(scored, config)

        to_save = db.exclude_blacklisted(partitions.to_save)
        blacklisted_removed = len(partitions.to_save) - len(to_save)
        if blacklisted_removed > 0:
            logger.info(
                "Skipped %d blacklisted job(s) before saving", blacklisted_removed
            )

        if len(to_save) == 0:
            logger.warning("No jobs above save_threshold after filtering")
            _send_empty_notification(config, db)
            return True

        log_section(logger, "SAVING RESULTS")
        current_run_new_job_ids = _get_current_run_new_job_ids(db, to_save)
        new_count, updated_count = db.save_jobs_from_dataframe(to_save)
        summary.new_jobs = new_count
        summary.relevant_jobs = len(to_save)
        logger.info(f"Database updated: {new_count} new, {updated_count} existing")

        if config.vector_search.enabled and config.vector_search.embed_on_save:
            try:
                from vector_store import get_vector_store

                df_for_vs = to_save.copy()
                df_for_vs["job_id"] = df_for_vs.apply(
                    lambda r: generate_job_id(
                        str(r.get("title", "")),
                        str(r.get("company", "")),
                        str(r.get("location", "")),
                    ),
                    axis=1,
                )
                vs = get_vector_store(config.chroma_path)
                vs.add_jobs_from_dataframe(df_for_vs)
            except Exception as e:
                logger.warning(f"Vector store embedding failed: {e}")

        print_top_jobs(to_save)

        notify_ids = (
            set(partitions.to_notify["job_id"])
            if "job_id" in partitions.to_notify.columns
            else None
        )
        if notify_ids is None:
            notify_job_ids_in_run = [
                job_id
                for job_id in current_run_new_job_ids
                if _job_id_in_frame(partitions.to_notify, job_id)
            ]
        else:
            notify_job_ids_in_run = [
                jid for jid in current_run_new_job_ids if jid in notify_ids
            ]
        new_jobs_to_notify = db.get_jobs_by_ids(notify_job_ids_in_run)

        if new_jobs_to_notify:
            _send_notifications(
                config,
                db,
                new_jobs_to_notify,
                updated_count,
                len(to_save),
            )

        log_section(logger, "SEARCH COMPLETE")
        logger.info(f"Duration: {summary.duration_formatted}")
        logger.info(f"Total unique jobs: {summary.unique_jobs}")
        logger.info(f"Saved jobs (≥ save_threshold): {summary.relevant_jobs}")
        logger.info(f"New jobs (first time seen): {summary.new_jobs}")

        return True

    except Exception as e:
        logger.error(f"Search failed with error: {e}")
        logger.error(traceback.format_exc())
        return False


def _job_id_in_frame(df, job_id: str) -> bool:
    """Check whether ``job_id`` appears in a DataFrame by recomputing the hash.

    Used when the frame doesn't carry a precomputed ``job_id`` column yet.
    """
    for record in df.to_dict("records"):
        computed = generate_job_id(
            str(record.get("title", "")),
            str(record.get("company", "")),
            str(record.get("location", "")),
        )
        if computed == job_id:
            return True
    return False


def _send_notifications(
    config: Config,
    db: JobDatabase,
    new_jobs: list[JobDBRecord],
    updated_count: int,
    total_found: int,
) -> None:
    """
    Send notifications for newly found jobs.

    Args:
        config: Configuration object.
        db: Database instance.
        new_jobs: Jobs discovered for the first time in the current run.
        updated_count: Number of updated jobs.
        total_found: Total jobs found.
    """
    logger = get_logger("notifications")

    if not config.notifications.enabled:
        logger.debug("Notifications disabled")
        return

    notification_manager = NotificationManager(config)

    if not notification_manager.has_configured_notifiers():
        logger.debug("No notification channels configured")
        return

    log_section(logger, "SENDING NOTIFICATIONS")

    try:
        # Get top jobs overall from database (for notifications)
        top_jobs_overall = []
        total_jobs_in_db = 0
        telegram_config = config.notifications.telegram
        if telegram_config.include_top_overall:
            top_jobs_overall = db.get_top_jobs(
                limit=telegram_config.max_top_overall,
                min_score=config.scoring.notify_threshold,
            )
            total_jobs_in_db = db.get_job_count()

        if not new_jobs and not top_jobs_overall:
            logger.info("No new jobs or top jobs to notify about")
            return

        # Calculate average score
        avg_score = (
            sum(j.relevance_score for j in new_jobs) / len(new_jobs) if new_jobs else 0
        )

        # Create notification data
        notification_data = create_notification_data(
            new_jobs=new_jobs,
            updated_count=updated_count,
            total_found=total_found,
            avg_score=avg_score,
            top_jobs_overall=top_jobs_overall,
            total_jobs_in_db=total_jobs_in_db,
            notify_threshold=config.scoring.notify_threshold,
        )

        # Send notifications
        results = notification_manager.send_all_sync(notification_data)

        for channel, success in results.items():
            if success:
                logger.info(f"Notification sent via {channel}")
            else:
                logger.warning(f"Failed to send notification via {channel}")

    except Exception as e:
        logger.error(f"Error sending notifications: {e}")


def _send_empty_notification(config: Config, db: JobDatabase) -> None:
    """
    Send notification when no new jobs are found.

    Args:
        config: Configuration object.
        db: Database instance.
    """
    logger = get_logger("notifications")

    if not config.notifications.enabled:
        return

    notification_manager = NotificationManager(config)

    if not notification_manager.has_configured_notifiers():
        return

    try:
        # Get database stats for context
        stats = db.get_statistics()

        # Get top jobs overall even when no new jobs found
        top_jobs_overall = []
        total_jobs_in_db = 0
        telegram_config = config.notifications.telegram
        if telegram_config.include_top_overall:
            top_jobs_overall = db.get_top_jobs(
                limit=telegram_config.max_top_overall,
                min_score=config.scoring.notify_threshold,
            )
            total_jobs_in_db = db.get_job_count()

        # Create notification data
        notification_data = create_notification_data(
            new_jobs=[],
            updated_count=0,
            total_found=stats.get("seen_today", 0),
            avg_score=stats.get("avg_relevance_score", 0),
            top_jobs_overall=top_jobs_overall,
            total_jobs_in_db=total_jobs_in_db,
            notify_threshold=config.scoring.notify_threshold,
        )

        # Send notifications
        results = notification_manager.send_all_sync(notification_data)

        for channel, success in results.items():
            if success:
                logger.info(f"Empty results notification sent via {channel}")

    except Exception as e:
        logger.error(f"Error sending empty notification: {e}")


def _prepare_runtime(*, scheduled: bool) -> tuple[Config, JobDatabase]:
    """Shared startup: load config, set up logging, recalc scores, backfill vectors.

    Returns the loaded ``Config`` and an initialised ``JobDatabase`` ready for use.
    """
    config = get_config()
    logger = setup_logging(config)

    log_section(logger, "JOB SEARCH TOOL STARTING")
    logger.info(f"Mode: {'Scheduled' if scheduled else 'Single-shot'}")

    if scheduled:
        logger.info(f"Interval: {config.scheduler.interval_hours} hours")
        logger.info(f"Run on startup: {config.scheduler.run_on_startup}")

    if config.notifications.enabled:
        channels = []
        if config.notifications.telegram.enabled:
            channels.append("Telegram")
        logger.info(
            f"Notifications: {', '.join(channels) if channels else 'None configured'}"
        )

    db = get_database(config)
    db_stats = db.get_statistics()
    if db_stats["total_jobs"] > 0:
        logger.info(
            f"Recalculating scores for {db_stats['total_jobs']} existing jobs..."
        )
        recalculate_all_scores(db, config)

    report = db.reconcile_with_config(config)
    logger.info(
        "Reconciliation: %d below score, %d stale, %d blacklist purged",
        report.deleted_below_score,
        report.deleted_stale,
        report.purged_blacklist,
    )

    if config.vector_search.enabled:
        try:
            from vector_store import get_vector_store
            from vector_commands import backfill_embeddings, sync_deletions

            vs = get_vector_store(config.chroma_path)
            if report.total_deleted > 0:
                sync_deletions(db, vs)
            if config.vector_search.backfill_on_startup:
                backfilled = backfill_embeddings(
                    db, vs, config.vector_search.batch_size
                )
                if backfilled:
                    logger.info(f"Backfilled {backfilled} jobs into vector store")
        except Exception as e:
            logger.warning(f"Vector store sync/backfill failed: {e}")

    if report.total_deleted > 0 and config.notifications.enabled:
        try:
            manager = NotificationManager(config)
            if manager.has_configured_notifiers():
                manager.send_reconcile_sync(create_reconcile_notification_data(report))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Reconcile notification failed: {e}")

    return config, db


def _cmd_scheduler() -> int:
    """Run the continuous APScheduler loop."""
    logger = get_logger("main")
    config, _db = _prepare_runtime(scheduled=True)
    scheduler = create_scheduler(config, run_job_search)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


def _cmd_once() -> int:
    """Run a single search iteration and exit."""
    logger = get_logger("main")
    config, _db = _prepare_runtime(scheduled=False)
    scheduler = create_scheduler(config, run_job_search)

    try:
        success = scheduler.run_once()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


def _cmd_dashboard() -> int:
    """Replace the current process with Streamlit serving the dashboard."""
    dashboard_py = Path(__file__).parent / "dashboard.py"
    args = [
        "streamlit",
        "run",
        str(dashboard_py),
        "--server.address=0.0.0.0",
        "--server.port=8501",
    ]
    # execvp replaces the Python process; signals and exit status flow naturally.
    os.execvp("streamlit", args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-search",
        description="Job Search Tool — scheduled scraping, scoring and notifications.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "scheduler",
        help="Run the continuous scheduled search loop (default).",
    )
    sub.add_parser(
        "once",
        help="Run a single search iteration and exit.",
    )
    sub.add_parser(
        "dashboard",
        help="Launch the Streamlit dashboard on port 8501.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the requested subcommand (``scheduler`` is the default)."""
    args = _build_parser().parse_args(argv)
    command = args.command or "scheduler"

    if command == "scheduler":
        return _cmd_scheduler()
    if command == "once":
        return _cmd_once()
    if command == "dashboard":
        return _cmd_dashboard()

    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    sys.exit(main())
