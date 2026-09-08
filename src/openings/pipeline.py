"""The collection run: collect -> score -> partition -> persist -> embed -> notify.

``run_collection`` is what the scheduler calls. ``prepare_runtime`` is the
boot-time pass that reconciles the database with the current configuration.
"""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from openings.config import get_config, reload_config
from openings.database import JobDatabase, get_database
from openings.logger import get_logger, log_section, setup_logging
from openings.models import Job, RunSummary
from openings.notifier import NotificationManager, build_run_notification
from openings.scoring import partition_by_thresholds, score_jobs
from openings.sources.collect import collect_all

if TYPE_CHECKING:
    from openings.config import Config


def _jobs_from_frame(frame) -> list[Job]:
    return [Job.from_row(record) for record in frame.to_dict("records")]


def _embed(config: Config, jobs: list[Job]) -> None:
    if not jobs or not (config.vector_search.enabled and config.vector_search.embed_on_save):
        return
    try:
        from openings.vector_store import get_vector_store

        store = get_vector_store(config.chroma_path)
        store.add_jobs([job.to_dict() for job in jobs], batch_size=config.vector_search.batch_size)
    except Exception as exc:  # noqa: BLE001 - embedding is best effort
        get_logger("pipeline").warning("Embedding failed: %s", exc)


def run_collection() -> bool:
    """One full run. Returns False when the run failed outright."""
    config = reload_config()
    logger = setup_logging(config)
    summary = RunSummary(started_at=datetime.now())
    db = get_database(config)

    try:
        if config.profile.name:
            logger.info("Openings run for %s", config.profile.name)
        logger.info("Database: %d jobs tracked", db.count_jobs())

        collected = collect_all(config)
        summary.sources = collected.stats
        summary.errors = collected.errors
        summary.total_found = collected.total_found
        summary.unique_found = collected.unique_found

        if collected.frame.empty:
            logger.warning("No rows collected")
            summary.finish()
            db.record_run(summary)
            _notify(config, db, summary, [])
            return True

        scored = score_jobs(collected.frame, config)
        partitions = partition_by_thresholds(scored, config)
        to_save = _jobs_from_frame(partitions.to_save)
        if not to_save:
            logger.warning("No rows above save_threshold")
            summary.finish()
            db.record_run(summary)
            _notify(config, db, summary, [])
            return True

        log_section(logger, "SAVING")
        result = db.upsert_jobs(to_save)
        summary.saved = result.new_count + result.updated_count
        summary.new_jobs = result.new_count
        logger.info(
            "Saved %d new, %d updated, %d skipped as blacklisted",
            result.new_count,
            result.updated_count,
            result.skipped_blacklisted,
        )

        saved_ids = set(result.new_ids) | set(result.updated_ids)
        _embed(config, [job for job in to_save if job.job_id in saved_ids])

        notify_ids = {Job.from_row(r).job_id for r in partitions.to_notify.to_dict("records")}
        new_to_notify = db.get_jobs([job_id for job_id in result.new_ids if job_id in notify_ids])
        summary.finish()
        summary.notified = _notify(config, db, summary, new_to_notify)
        db.record_run(summary)

        log_section(logger, "RUN COMPLETE")
        logger.info("Duration: %s", summary.duration_formatted)
        logger.info("Collected %d, unique %d", summary.total_found, summary.unique_found)
        logger.info(
            "Saved %d, new %d, notified %d", summary.saved, summary.new_jobs, summary.notified
        )
        for stat in summary.sources:
            logger.info(
                "  %s: %d rows, %d/%d tasks ok", stat.name, stat.rows, stat.succeeded, stat.tasks
            )
        return True

    except Exception as exc:  # noqa: BLE001 - the scheduler decides on retries
        logger.error("Run failed: %s", exc)
        logger.error(traceback.format_exc())
        summary.success = False
        summary.errors.append(f"run: {exc}")
        summary.finish()
        try:
            db.record_run(summary)
        except Exception:  # noqa: BLE001
            logger.error("Could not record the failed run")
        return False


def _notify(config: Config, db: JobDatabase, summary: RunSummary, new_jobs: list[Job]) -> int:
    """Send the run digest; returns how many postings were included."""
    manager = NotificationManager(config)
    if not manager.has_channels():
        return 0
    data = build_run_notification(
        summary, new_jobs, config.scoring.notify_threshold, db.count_jobs()
    )
    results = manager.send_run(data)
    logger = get_logger("notifications")
    for channel, ok in results.items():
        logger.info("%s notification %s", channel, "sent" if ok else "failed")
    return (
        min(len(new_jobs), config.notifications.telegram.max_jobs) if any(results.values()) else 0
    )


def prepare_runtime(*, scheduled: bool) -> tuple[Config, JobDatabase]:
    """Boot: load config, rescore, reconcile, sync embeddings, report cleanup."""
    config = get_config()
    logger = setup_logging(config)
    log_section(logger, "OPENINGS STARTING")
    logger.info("Mode: %s", "scheduler" if scheduled else "single run")
    logger.info("Data directory: %s", config.data_dir)
    if scheduled:
        logger.info(
            "Interval: %d hours, run on startup: %s",
            config.scheduler.interval_hours,
            config.scheduler.run_on_startup,
        )

    db = get_database(config)
    total = db.count_jobs()
    if total:
        changed = db.rescore_all(config)
        logger.info("Rescored %d of %d jobs against the current configuration", changed, total)

    report = db.reconcile(config)
    logger.info(
        "Reconciliation: %d below save threshold, %d stale, %d blacklist entries purged, %d protected",
        report.deleted_below_score,
        report.deleted_stale,
        report.purged_blacklist,
        report.protected,
    )

    if config.vector_search.enabled:
        try:
            from openings.vector_commands import backfill_embeddings, sync_deletions
            from openings.vector_store import get_vector_store

            store = get_vector_store(config.chroma_path)
            if report.total_deleted:
                sync_deletions(db, store)
            if config.vector_search.backfill_on_startup:
                embedded = backfill_embeddings(db, store, config.vector_search.batch_size)
                if embedded:
                    logger.info("Backfilled %d jobs into the vector store", embedded)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector store maintenance failed: %s", exc)

    if report.total_deleted:
        manager = NotificationManager(config)
        if manager.has_channels():
            manager.send_reconcile(report)

    return config, db


def make_vector_maintenance(config: Config, db: JobDatabase) -> Callable[[], None] | None:
    """Periodic Chroma upkeep for the scheduler, the sole writer to the index.

    Prunes embeddings of deleted jobs and embeds rows added outside a run,
    such as postings handed in through ``add_job`` by the web process.
    """
    if not config.vector_search.enabled:
        return None
    from openings.vector_commands import backfill_embeddings, sync_deletions
    from openings.vector_store import get_vector_store

    store = get_vector_store(config.chroma_path)

    def maintain() -> None:
        sync_deletions(db, store)
        backfill_embeddings(db, store, config.vector_search.batch_size)

    return maintain
