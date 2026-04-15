#!/usr/bin/env python3
"""
Job Search Tool - Main Entry Point.

Unified entry point that supports both single-shot and scheduled execution modes.
Integrates job search, database persistence, and notifications.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING

from config import get_config, reload_config
from database import cleanup_old_jobs, get_database, recalculate_all_scores
from exporter import save_results
from logger import get_logger, log_section, setup_logging
from models import generate_job_id
from notifier import NotificationManager, create_notification_data
from scheduler import create_scheduler
from scoring import filter_relevant_jobs
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
    """
    Execute a single job search iteration.

    This function performs the complete search workflow:
    1. Load configuration
    2. Search for jobs
    3. Filter by relevance
    4. Save to database
    5. Send notifications for new jobs

    Returns:
        True if search completed successfully, False otherwise.
    """
    # Reload config to pick up any changes
    config = reload_config()
    logger = setup_logging(config)

    try:
        # Print banner
        print_banner(config)

        # Initialize database
        db = get_database(config)
        db_stats = db.get_statistics()
        logger.info(f"Database: {db_stats['total_jobs']} jobs tracked")

        # Cleanup old jobs if enabled
        if config.database.cleanup_enabled and db_stats["total_jobs"] > 0:
            deleted_count = cleanup_old_jobs(db, config.database.cleanup_days)

            # Sync vector store deletions
            if config.vector_search.enabled and deleted_count > 0:
                try:
                    from vector_store import get_vector_store
                    from vector_commands import sync_deletions

                    vs = get_vector_store(config.chroma_path)
                    sync_deletions(db, vs)
                except Exception as e:
                    logger.warning(f"Vector store sync failed: {e}")

        # Search for jobs
        all_jobs, summary = search_jobs(config)

        if all_jobs is None or len(all_jobs) == 0:
            logger.warning("No jobs found in this search")

            # Still send notification if configured (to inform of empty results)
            _send_empty_notification(config, db)
            return True  # Not a failure, just no results

        # Save all results
        log_section(logger, "SAVING ALL RESULTS")
        save_results(all_jobs, config, "all_jobs")

        # Filter relevant jobs
        relevant_jobs = filter_relevant_jobs(all_jobs, config)
        filtered_relevant_jobs = db.filter_blacklisted_jobs(relevant_jobs)
        blacklisted_removed = len(relevant_jobs) - len(filtered_relevant_jobs)
        if blacklisted_removed > 0:
            logger.info(
                "Skipped %d blacklisted relevant job(s) before saving",
                blacklisted_removed,
            )
        relevant_jobs = filtered_relevant_jobs
        summary.relevant_jobs = len(relevant_jobs)

        if len(relevant_jobs) == 0:
            logger.warning("No highly relevant jobs found after filtering")
            logger.info("Tip: Check the 'all_jobs' file for broader results")

            _send_empty_notification(config, db)
            return True

        # Save filtered results
        log_section(logger, "SAVING FILTERED RESULTS")
        save_results(relevant_jobs, config, "relevant_jobs")

        current_run_new_job_ids = _get_current_run_new_job_ids(db, relevant_jobs)

        # Save to database and identify new jobs
        new_count, updated_count = db.save_jobs_from_dataframe(relevant_jobs)
        summary.new_jobs = new_count

        logger.info(f"Database updated: {new_count} new, {updated_count} existing")

        current_run_new_jobs = db.get_jobs_by_ids(current_run_new_job_ids)

        # Embed new jobs in vector store
        if config.vector_search.enabled and config.vector_search.embed_on_save:
            try:
                from vector_store import get_vector_store

                # Add job_id column so vector store can use it as document ID
                df_for_vs = relevant_jobs.copy()
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

        # Print top matches
        print_top_jobs(relevant_jobs)

        # Send notifications for new jobs
        if current_run_new_jobs:
            _send_notifications(
                config,
                db,
                current_run_new_jobs,
                updated_count,
                len(relevant_jobs),
            )

        # Print summary
        log_section(logger, "SEARCH COMPLETE")
        logger.info(f"Duration: {summary.duration_formatted}")
        logger.info(f"Total unique jobs: {summary.unique_jobs}")
        logger.info(f"Highly relevant jobs: {summary.relevant_jobs}")
        logger.info(f"New jobs (first time seen): {summary.new_jobs}")
        logger.info("Check the 'results' folder for detailed CSV and Excel files.")

        return True

    except Exception as e:
        logger.error(f"Search failed with error: {e}")
        logger.error(traceback.format_exc())
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
                min_score=telegram_config.min_score_for_notification,
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
                min_score=telegram_config.min_score_for_notification,
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
        )

        # Send notifications
        results = notification_manager.send_all_sync(notification_data)

        for channel, success in results.items():
            if success:
                logger.info(f"Empty results notification sent via {channel}")

    except Exception as e:
        logger.error(f"Error sending empty notification: {e}")


def main() -> int:
    """Main entry point.

    Starts the APScheduler loop and runs the search pipeline on the configured
    interval. Single-shot execution is available via ``python main.py --once``
    for ad-hoc runs and CI.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    scheduled_mode = "--once" not in sys.argv

    # Initial config load
    config = get_config()
    logger = setup_logging(config)

    log_section(logger, "JOB SEARCH TOOL STARTING")
    logger.info(f"Mode: {'Scheduled' if scheduled_mode else 'Single-shot (--once)'}")

    if scheduled_mode:
        logger.info(f"Interval: {config.scheduler.interval_hours} hours")
        logger.info(f"Run on startup: {config.scheduler.run_on_startup}")

    if config.notifications.enabled:
        channels = []
        if config.notifications.telegram.enabled:
            channels.append("Telegram")
        logger.info(
            f"Notifications: {', '.join(channels) if channels else 'None configured'}"
        )

    # Recalculate scores for existing jobs at startup (if enabled)
    db = get_database(config)
    db_stats = db.get_statistics()
    if config.database.recalculate_scores_on_startup and db_stats["total_jobs"] > 0:
        logger.info(
            f"Recalculating scores for {db_stats['total_jobs']} existing jobs..."
        )
        recalculate_all_scores(db, config)

    # Vector store backfill
    if config.vector_search.enabled and config.vector_search.backfill_on_startup:
        try:
            from vector_store import get_vector_store
            from vector_commands import backfill_embeddings

            vs = get_vector_store(config.chroma_path)
            backfilled = backfill_embeddings(db, vs, config.vector_search.batch_size)
            if backfilled:
                logger.info(f"Backfilled {backfilled} jobs into vector store")
        except Exception as e:
            logger.warning(f"Vector store backfill failed: {e}")

    # Create scheduler
    scheduler = create_scheduler(config, run_job_search)

    try:
        if scheduled_mode:
            # Scheduled mode - runs continuously
            scheduler.start()
        else:
            # Single-shot mode - run once and exit
            success = scheduler.run_once()
            return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
