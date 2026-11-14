from datetime import UTC, datetime
from uuid import uuid4

from .actors import current_batch
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
        details = {"current_version": row["version"]}
        if "id" in row.keys():  # noqa: SIM118 - a sqlite3.Row tests values with `in`
            details["id"] = row["id"]
        conflict(details=details)


def batch_result(items):
    """A batch's results (BatchResult): each ``{id, ok, result | error}`` numbered in
    request order, with the record's new version and the batch of the changes."""
    items = [
        {"index": index, **item, **_version(item.get("result"))} for index, item in enumerate(items)
    ]
    succeeded = sum(item["ok"] for item in items)
    return {
        "batch_id": current_batch() if succeeded else None,
        "items": items,
        "total": len(items),
        "succeeded": succeeded,
        "failed": len(items) - succeeded,
    }


def _version(result):
    version = result.get("version") if isinstance(result, dict) else None
    return {} if version is None else {"version": version}


__all__ = [
    "DomainError",
    "batch_result",
    "check_version",
    "conflict",
    "decode_record",
    "encode",
    "missing",
    "new_id",
    "now",
]
