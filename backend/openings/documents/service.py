"""Frozen application context, immutable documents and bounded SQLite file transfers."""

from __future__ import annotations

import asyncio

from .contexts import ContextOperations
from .files import FileOperations
from .revisions import RevisionOperations


class DocumentService(ContextOperations, RevisionOperations, FileOperations):
    def __init__(self, workspace, max_file_bytes: int = 20 * 1024 * 1024):
        self.workspace = workspace
        self.db = workspace.db
        self.max_file_bytes = max_file_bytes
        self._upload_slots = asyncio.Semaphore(2)
