from datetime import datetime, timezone
from uuid import uuid4

from .db import decode_record, encode
from .errors import DomainError, conflict, missing

CONTEXT_BUILDER_VERSION = 3


def assessment_context_version_sql(alias="a"):
    return f"coalesce(json_extract({alias}.payload,'$.context.versions.context_builder'),1)"


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
    "CONTEXT_BUILDER_VERSION",
    "assessment_context_version_sql",
    "now",
    "new_id",
    "check_version",
    "encode",
    "decode_record",
    "DomainError",
    "missing",
    "conflict",
]
