"""The one object a process builds: configuration, database, files, embeddings, service.

``Runtime`` replaces module-level singletons. The CLI builds one per process;
the web layer keeps one for the lifetime of the server; tests build their own
against a temporary directory.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from openings.config import Config, ConfigError, default_config_path, default_data_dir, load_config
from openings.logger import get_logger

if TYPE_CHECKING:
    from openings.application.attachments import AttachmentStore
    from openings.application.jobs import JobApplicationService
    from openings.db import JobDatabase
    from openings.embeddings import Embeddings


class Runtime:
    def __init__(self, *, data_dir: Path | None = None, config_path: Path | None = None):
        self.data_dir = Path(data_dir or default_data_dir())
        self.config_path = Path(config_path or default_config_path(self.data_dir))
        self._lock = threading.RLock()
        self._config: Config | None = None
        self._config_mtime: float | None = None
        self._db: JobDatabase | None = None
        self._attachments: AttachmentStore | None = None
        self._embeddings: Embeddings | None = None
        self._embeddings_unavailable: str | None = None
        self._service: JobApplicationService | None = None
        self.logger = get_logger("runtime")

    @classmethod
    def from_env(cls) -> Runtime:
        data_dir = default_data_dir()
        return cls(data_dir=data_dir, config_path=default_config_path(data_dir))

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def config(self, *, reload: bool = False) -> Config:
        """The current configuration; re-read when the file changed on disk."""
        with self._lock:
            try:
                mtime = os.path.getmtime(self.config_path)
            except OSError:
                mtime = None
            if self._config is None:
                self._config = load_config(self.config_path, data_dir=self.data_dir)
                self._config_mtime = mtime
            elif reload or (mtime is not None and mtime != self._config_mtime):
                try:
                    self._config = load_config(self.config_path, data_dir=self.data_dir)
                    self._config_mtime = mtime
                    self._embeddings = None
                    self._embeddings_unavailable = None
                    if not reload:
                        self.logger.info("Configuration reloaded from %s", self.config_path)
                except ConfigError as exc:
                    self._config_mtime = mtime
                    self.logger.error("Keeping the previous configuration: %s", exc)
            return self._config

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------

    @property
    def db(self) -> JobDatabase:
        with self._lock:
            if self._db is None:
                from openings.db import JobDatabase

                self._db = JobDatabase(self.config().database_path)
            return self._db

    @property
    def attachments(self) -> AttachmentStore:
        with self._lock:
            if self._attachments is None:
                from openings.application.attachments import AttachmentStore

                config = self.config()
                self._attachments = AttachmentStore(
                    config.attachments_dir, config.attachments.max_size_mb * 1024 * 1024
                )
            return self._attachments

    @property
    def embeddings(self) -> Embeddings | None:
        """The embedding index, or ``None`` when disabled or unavailable."""
        with self._lock:
            config = self.config()
            if not config.embeddings.enabled or self._embeddings_unavailable:
                return None
            if self._embeddings is None:
                from openings.embeddings import Embeddings

                try:
                    self._embeddings = Embeddings(self.db, config)
                except Exception as exc:  # noqa: BLE001 - search is optional
                    self._embeddings_unavailable = str(exc)
                    self.logger.warning("Embeddings unavailable: %s", exc)
                    return None
            return self._embeddings

    @property
    def embeddings_status(self) -> str:
        config = self.config()
        if not config.embeddings.enabled:
            return "disabled"
        if self._embeddings_unavailable:
            return f"unavailable: {self._embeddings_unavailable}"
        return "ready" if self._embeddings is not None else "not loaded"

    @property
    def service(self) -> JobApplicationService:
        with self._lock:
            if self._service is None:
                from openings.application.jobs import JobApplicationService

                self._service = JobApplicationService(self)
            return self._service

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
            self._db = None
            self._service = None
            self._embeddings = None
            self._embeddings_unavailable = None
            self._attachments = None


_runtime: Runtime | None = None
_runtime_lock = threading.Lock()


def get_runtime() -> Runtime:
    """The process-wide runtime, built from the environment on first use."""
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = Runtime.from_env()
        return _runtime


def set_runtime(runtime: Runtime | None) -> None:
    """Replace the process-wide runtime (tests, embedding callers)."""
    global _runtime
    with _runtime_lock:
        if _runtime is not None and _runtime is not runtime:
            _runtime.close()
        _runtime = runtime
