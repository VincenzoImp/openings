"""Attachment bytes on disk under ``{DATA_DIR}/attachments/{job_id}/``."""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


class AttachmentTooLarge(ValueError):
    pass


def safe_filename(name: str) -> str:
    """Strip directories and unusual characters; never empty."""
    base = Path(name or "").name
    cleaned = _SAFE.sub("_", base).strip("._") or "attachment"
    return cleaned[:120]


class AttachmentStore:
    def __init__(self, root: Path, max_bytes: int):
        self.root = Path(root)
        self.max_bytes = max_bytes

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", job_id):
            raise ValueError("Invalid job id")
        return self.root / job_id

    def save(self, job_id: str, filename: str, content: bytes) -> tuple[str, str, int]:
        """Write bytes; returns ``(stored_name, sha256, size)``."""
        if len(content) > self.max_bytes:
            raise AttachmentTooLarge(
                f"Attachment is {len(content)} bytes; the limit is {self.max_bytes} bytes"
            )
        if not content:
            raise ValueError("Attachment is empty")
        directory = self._job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}-{safe_filename(filename)}"
        (directory / stored_name).write_bytes(content)
        return stored_name, hashlib.sha256(content).hexdigest(), len(content)

    def path(self, job_id: str, stored_name: str) -> Path:
        return self._job_dir(job_id) / Path(stored_name).name

    def delete(self, job_id: str, stored_name: str) -> None:
        path = self.path(job_id, stored_name)
        if path.is_file():
            path.unlink()
        directory = self._job_dir(job_id)
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()

    def delete_job(self, job_id: str) -> None:
        directory = self._job_dir(job_id)
        if directory.is_dir():
            shutil.rmtree(directory, ignore_errors=True)

    def move(self, from_job: str, to_job: str, stored_name: str) -> None:
        """Relocate one file when jobs are merged; stored names are unique."""
        source = self.path(from_job, stored_name)
        if not source.is_file():
            return
        target_dir = self._job_dir(to_job)
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target_dir / stored_name))
        old_dir = self._job_dir(from_job)
        if old_dir.is_dir() and not any(old_dir.iterdir()):
            old_dir.rmdir()
