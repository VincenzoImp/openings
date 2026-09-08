"""The collection run: collect -> score -> partition -> persist -> embed -> notify.

``run_collection`` is what the scheduler calls. ``prepare_runtime`` is the
boot-time pass that reconciles the database with the current configuration.
"""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from openings.logger import get_logger, log_section
from openings.models import Job, RunSummary, utcnow
from openings.notifier import NotificationManager, build_run_notification
from openings.scoring import partition_by_thresholds, score_jobs
from openings.sources.collect import collect_all

if TYPE_CHECKING:
    from openings.config import Config
    from openings.db import JobDatabase
    from openings.runtime import Runtime


def _jobs_from_frame(frame) -> list[Job]:
    return [Job.from_row(record) for record in frame.to_dict("records")]


def _embed(runtime: Runtime, jobs: list[Job]) -> None:
    config = runtime.config()
    if not jobs or not (config.embeddings.enabled and config.embeddings.embed_on_save):
        return
    embeddings = runtime.embeddings
    if embeddings is None:
        return
    try:
        embeddings.embed_jobs(jobs)
    except Exception as exc:  # noqa: BLE001 - embedding is best effort
        get_logger("pipeline").warning("Embedding failed: %s", exc)


def run_collection(runtime: Runtime) -> bool:
    """One full run. Returns False when the run failed or every source failed."""
    config = runtime.config(reload=True)
    logger = get_logger("pipeline")
    logging.getLogger("openings").setLevel(config.logging.level)
    db = runtime.db
    summary = RunSummary(started_at=utcnow())
    db.start_run(summary)

    try:
        if config.profile.name:
            logger.info("Openings run for %s", config.profile.name)
        logger.info("Database: %d jobs tracked", db.count_jobs())

        collected = collect_all(config, known=db.known_external_ids)
        summary.sources = collected.stats
        summary.errors = collected.errors
        summary.total_found = collected.total_found
        summary.unique_found = collected.unique_found
        if collected.every_task_failed:
            summary.success = False
            summary.errors.append("run: every source failed")
            logger.error("Every source failed; the run is marked failed")

        new_to_notify: list[Job] = []
        if collected.frame.empty:
            logger.warning("No rows collected")
        else:
            scored = score_jobs(collected.frame, config)
            partitions = partition_by_thresholds(scored, config)
            to_save = _jobs_from_frame(partitions.to_save)
            if not to_save:
                logger.warning("No rows above save_threshold")
            else:
                log_section(logger, "SAVING")
                result = db.upsert_jobs(to_save)
                summary.saved = result.new_count + result.updated_count
                summary.new_jobs = result.new_count
                logger.info(
                    "Saved %d new, %d updated, %d new postings on known jobs, "
                    "%d skipped as blacklisted",
                    result.new_count,
                    result.updated_count,
                    len(result.new_postings),
                    result.skipped_blacklisted,
                )
                _embed(runtime, db.get_jobs(result.new_ids + result.updated_ids))
                notify_ids = {
                    Job.from_row(record).job_id
                    for record in partitions.to_notify.to_dict("records")
                }
                new_to_notify = db.get_jobs(
                    [job_id for job_id in result.new_ids if job_id in notify_ids]
                )

        summary.finish()
        summary.notified = _notify(config, db, summary, new_to_notify)
        db.finish_run(summary)

        log_section(logger, "RUN COMPLETE" if summary.success else "RUN FAILED")
        logger.info("Duration: %s", summary.duration_formatted)
        logger.info("Collected %d, unique %d", summary.total_found, summary.unique_found)
        logger.info(
            "Saved %d, new %d, notified %d", summary.saved, summary.new_jobs, summary.notified
        )
        for stat in summary.sources:
            logger.info(
                "  %s: %d rows, %d/%d tasks ok", stat.name, stat.rows, stat.succeeded, stat.tasks
            )
        return summary.success

    except Exception as exc:  # noqa: BLE001 - the scheduler decides on retries
        logger.error("Run failed: %s", exc)
        logger.error(traceback.format_exc())
        summary.success = False
        summary.errors.append(f"run: {exc}")
        summary.finish()
        try:
            db.finish_run(summary)
        except Exception:  # noqa: BLE001
            logger.error("Could not record the failed run")
        return False


def _notify(config: Config, db: JobDatabase, summary: RunSummary, new_jobs: list[Job]) -> int:
    """Send the run digest; returns how many postings were included."""
    manager = NotificationManager(config)
    if not manager.has_channels():
        return 0
    data = build_run_notification(
        summary, new_jobs, config.scoring.notify_threshold, db.count_jobs(), config.logging.timezone
    )
    results = manager.send_run(data)
    logger = get_logger("notifications")
    for channel, ok in results.items():
        logger.info("%s notification %s", channel, "sent" if ok else "skipped or failed")
    if not any(results.values()):
        return 0
    return min(len(new_jobs), config.notifications.telegram.max_jobs)


def prepare_runtime(runtime: Runtime, *, scheduled: bool) -> Config:
    """Boot: banner, close stale runs, rescore, reconcile, backfill embeddings."""
    config = runtime.config()
    logger = get_logger("boot")
    log_section(logger, "OPENINGS STARTING")
    logger.info("Mode: %s", "scheduler" if scheduled else "single run")
    logger.info("Data directory: %s", config.data_dir)
    if scheduled:
        logger.info(
            "Interval: %d hours, run on startup: %s",
            config.scheduler.interval_hours,
            config.scheduler.run_on_startup,
        )

    db = runtime.db
    stale = db.close_stale_runs()
    if stale:
        logger.warning("Closed %d run(s) left open by a previous process", stale)
    total = db.count_jobs()
    if total:
        changed = db.rescore_all(config)
        logger.info("Rescored %d of %d jobs against the current configuration", changed, total)

    report = db.reconcile(config)
    logger.info(
        "Reconciliation: %d below save threshold, %d stale, %d protected",
        report.deleted_below_score,
        report.deleted_stale,
        report.protected,
    )

    if config.embeddings.enabled and config.embeddings.backfill_on_startup:
        embeddings = runtime.embeddings
        if embeddings is not None:
            try:
                embedded = embeddings.backfill()
                if embedded:
                    logger.info("Backfilled %d jobs into the embedding index", embedded)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding backfill failed: %s", exc)

    if report.total_deleted:
        manager = NotificationManager(config)
        if manager.has_channels():
            manager.send_reconcile(report)
    return config
