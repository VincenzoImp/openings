#!/usr/bin/env python3
"""
Job Search Tool - Main Entry Point.

Unified entry point that supports both single-shot and scheduled execution modes.
Integrates job search, database persistence, and notifications.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from config import get_config, reload_config
from database import get_database
from logger import get_logger, log_section, setup_logging
from notifier import NotificationManager, create_notification_data
from scheduler import create_scheduler
from search_jobs import (
    filter_relevant_jobs,
    print_banner,
    print_top_jobs,
    save_results,
    search_jobs,
)

if TYPE_CHECKING:
    from config import Config
    from database import JobDatabase
    from models import JobDBRecord


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
        summary.relevant_jobs = len(relevant_jobs)

        if len(relevant_jobs) == 0:
            logger.warning("No highly relevant jobs found after filtering")
            logger.info("Tip: Check the 'all_jobs' file for broader results")

            _send_empty_notification(config, db)
            return True

        # Save filtered results
        log_section(logger, "SAVING FILTERED RESULTS")
        save_results(relevant_jobs, config, "relevant_jobs")

        # Save to database and identify new jobs
        new_count, updated_count = db.save_jobs_from_dataframe(relevant_jobs)
        summary.new_jobs = new_count

        logger.info(f"Database updated: {new_count} new, {updated_count} existing")

        # Print top matches
        print_top_jobs(relevant_jobs)

        # Send notifications for new jobs
        if new_count > 0:
            _send_notifications(config, db, new_count, updated_count, len(relevant_jobs))

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
        import traceback
        logger.error(traceback.format_exc())
        return False


def _send_notifications(
    config: Config,
    db: JobDatabase,
    new_count: int,
    updated_count: int,
    total_found: int,
) -> None:
    """
    Send notifications for newly found jobs.

    Args:
        config: Configuration object.
        db: Database instance.
        new_count: Number of new jobs.
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
        # Get new jobs from database (jobs first seen today)
        new_jobs = db.get_jobs_first_seen_today()

        if not new_jobs:
            logger.info("No new jobs to notify about")
            return

        # Calculate average score
        avg_score = sum(j.relevance_score for j in new_jobs) / len(new_jobs) if new_jobs else 0

        # Create notification data
        notification_data = create_notification_data(
            new_jobs=new_jobs,
            updated_count=updated_count,
            total_found=total_found,
            avg_score=avg_score,
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

        # Create empty notification data
        notification_data = create_notification_data(
            new_jobs=[],
            updated_count=0,
            total_found=stats.get("seen_today", 0),
            avg_score=stats.get("avg_relevance_score", 0),
        )

        # Send notifications
        results = notification_manager.send_all_sync(notification_data)

        for channel, success in results.items():
            if success:
                logger.info(f"Empty results notification sent via {channel}")

    except Exception as e:
        logger.error(f"Error sending empty notification: {e}")


def main() -> int:
    """
    Main entry point.

    Determines execution mode (single-shot vs scheduled) based on configuration
    and runs the appropriate workflow.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Initial config load
    config = get_config()
    logger = setup_logging(config)

    log_section(logger, "JOB SEARCH TOOL STARTING")
    logger.info(f"Mode: {'Scheduled' if config.scheduler.enabled else 'Single-shot'}")

    if config.scheduler.enabled:
        logger.info(f"Interval: {config.scheduler.interval_hours} hours")
        logger.info(f"Run on startup: {config.scheduler.run_on_startup}")

    if config.notifications.enabled:
        channels = []
        if config.notifications.telegram.enabled:
            channels.append("Telegram")
        logger.info(f"Notifications: {', '.join(channels) if channels else 'None configured'}")

    # Create scheduler
    scheduler = create_scheduler(config, run_job_search)

    try:
        if config.scheduler.enabled:
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
