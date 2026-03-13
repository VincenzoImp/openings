"""
Utility commands for vector store maintenance.

Provides backfill and sync operations to keep the ChromaDB vector store
aligned with the SQLite job database.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database import JobDatabase
    from vector_store import JobVectorStore

logger = logging.getLogger("job_search.vector_commands")


def backfill_embeddings(
    db: JobDatabase,
    vector_store: JobVectorStore,
    batch_size: int = 100,
) -> int:
    """Embed all existing jobs from SQLite that aren't yet in ChromaDB.

    Compares the set of job IDs in the vector store against those in the
    database and embeds any that are missing.

    Args:
        db: The SQLite job database.
        vector_store: The ChromaDB vector store.
        batch_size: Number of jobs to embed per ChromaDB upsert call.

    Returns:
        Number of newly embedded jobs.
    """
    all_jobs = db.get_all_jobs()
    embedded_ids = vector_store.get_embedded_ids()

    to_embed = [job for job in all_jobs if job.job_id not in embedded_ids]
    if not to_embed:
        logger.info("All %d jobs already embedded", len(all_jobs))
        return 0

    logger.info(
        "Backfilling %d jobs (%d already embedded)",
        len(to_embed),
        len(embedded_ids),
    )

    records: list[dict] = []
    for job in to_embed:
        records.append(
            {
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description,
                "site": job.site,
                "relevance_score": job.relevance_score,
                "first_seen": str(job.first_seen) if job.first_seen else None,
                "job_url": job.job_url,
            }
        )

    count = vector_store.add_jobs(records, batch_size=batch_size)
    logger.info("Backfill complete: %d jobs embedded", count)
    return count


def sync_deletions(
    db: JobDatabase,
    vector_store: JobVectorStore,
) -> int:
    """Remove embeddings for jobs no longer present in SQLite.

    Computes the set difference between the vector store and the database,
    then deletes any stale entries from ChromaDB.

    Args:
        db: The SQLite job database.
        vector_store: The ChromaDB vector store.

    Returns:
        Number of stale embeddings removed.
    """
    db_ids = {job.job_id for job in db.get_all_jobs()}
    vec_ids = vector_store.get_embedded_ids()

    stale = vec_ids - db_ids
    if not stale:
        logger.info("No stale embeddings to remove")
        return 0

    logger.info("Removing %d stale embeddings", len(stale))
    vector_store.delete_jobs(list(stale))
    return len(stale)
