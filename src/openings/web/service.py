"""Process-wide service wiring for the web process."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from openings.application.attachments import AttachmentStore
from openings.application.jobs import JobApplicationService
from openings.config import get_config
from openings.database import JobDatabase, close_database, get_database
from openings.logger import get_logger

if TYPE_CHECKING:
    from openings.vector_store import ReadOnlyVectorStore

logger = get_logger("web")

_lock = threading.Lock()
_service: JobApplicationService | None = None
_vector_store: ReadOnlyVectorStore | None = None
_vector_store_attempted = False


def get_db() -> JobDatabase:
    return get_database(get_config())


def get_vector_store() -> ReadOnlyVectorStore | None:
    """Read-only view: only the scheduler process writes to the index."""
    global _vector_store, _vector_store_attempted
    if not _vector_store_attempted:
        _vector_store_attempted = True
        try:
            from openings.vector_store import ReadOnlyVectorStore, get_vector_store as open_store

            _vector_store = ReadOnlyVectorStore(open_store(get_config().chroma_path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector store unavailable: %s", exc)
            _vector_store = None
    return _vector_store


def get_service() -> JobApplicationService:
    global _service
    with _lock:
        if _service is None:
            config = get_config()
            _service = JobApplicationService(
                get_db(),
                get_config,
                AttachmentStore(
                    config.attachments_dir, config.attachments.max_size_mb * 1024 * 1024
                ),
                vector_store_factory=get_vector_store,
            )
        return _service


def reset_service() -> None:
    """Drop cached state (tests and config reloads)."""
    global _service, _vector_store, _vector_store_attempted
    with _lock:
        _service = None
        _vector_store = None
        _vector_store_attempted = False
        close_database()
