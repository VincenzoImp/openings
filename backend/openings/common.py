from datetime import datetime, timezone
from uuid import uuid4

from .db import decode_record, encode
from .errors import DomainError, conflict, missing


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id():
    return uuid4().hex


def check_version(row, expected):
    if row is None:
        missing()
    if expected is not None and row["version"] != expected:
        conflict()


__all__ = [
    "now",
    "new_id",
    "check_version",
    "encode",
    "decode_record",
    "DomainError",
    "missing",
    "conflict",
]
