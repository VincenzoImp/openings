"""DocumentService: upload limits, composed with revisions and files."""

from __future__ import annotations

import asyncio

from .files import FileOperations
from .revisions import RevisionOperations


class DocumentService(RevisionOperations, FileOperations):
    def __init__(self, workspace, max_file_bytes: int = 20 * 1024 * 1024):
        self.workspace = workspace
        self.db = workspace.db
        self.max_file_bytes = max_file_bytes
        self._upload_slots = asyncio.Semaphore(2)
        # PDF-only revisions whose text could not be read, tried once per process.
        self._unreadable = set()
