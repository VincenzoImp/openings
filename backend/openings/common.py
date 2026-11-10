from datetime import UTC, datetime
from uuid import uuid4

from .db import decode_record, encode
from .errors import DomainError, conflict, missing


def now():
    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id():
    return uuid4().hex


def check_version(row, expected):
    if row is None:
        missing()
    if expected is not None and row["version"] != expected:
        conflict(details={"current_version": row["version"]})


__all__ = [
    "DomainError",
    "check_version",
    "conflict",
    "decode_record",
    "encode",
    "missing",
    "new_id",
    "now",
]
