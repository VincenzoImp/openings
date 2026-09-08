"""Keep the Chroma index aligned with the SQLite database."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openings.database import JobDatabase
    from openings.vector_store import JobVectorStore

logger = logging.getLogger("openings.vector_commands")


def backfill_embeddings(
    db: JobDatabase, vector_store: JobVectorStore, batch_size: int = 100
) -> int:
    """Embed every stored job that the index does not have yet."""
    embedded = vector_store.get_embedded_ids()
    missing = [job for job in db.iter_jobs() if job.job_id not in embedded]
    if not missing:
        return 0
    logger.info("Backfilling %d jobs (%d already embedded)", len(missing), len(embedded))
    return vector_store.add_jobs([job.to_dict() for job in missing], batch_size=batch_size)


def sync_deletions(db: JobDatabase, vector_store: JobVectorStore) -> int:
    """Drop embeddings whose job no longer exists."""
    db_ids = {job.job_id for job in db.iter_jobs()}
    stale = vector_store.get_embedded_ids() - db_ids
    if not stale:
        return 0
    logger.info("Removing %d stale embeddings", len(stale))
    vector_store.delete_jobs(list(stale))
    return len(stale)
