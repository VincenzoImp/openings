import json
from datetime import UTC, datetime
from uuid import uuid4

from .actors import current_batch
from .errors import DomainError, conflict, missing


def now():
    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id():
    return uuid4().hex


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode_record(row, fields=()):
    if row is None:
        return None
    row = dict(row)
    for name in fields:
        if isinstance(row.get(name), str):
            row[name] = json.loads(row[name])
    return row


def check_version(row, expected):
    if row is None:
        missing()
    if expected is not None and row["version"] != expected:
        details = {"current_version": row["version"]}
        if "id" in row.keys():  # noqa: SIM118 - a sqlite3.Row tests values with `in`
            details["id"] = row["id"]
        conflict(details=details)


def error_body(error):
    return {
        "code": error.code,
        "message": error.message,
        "status": error.status,
        "details": error.details,
    }


def run_items(db, items, key, apply, collect=False):
    """Apply each item of a batch on its own and return the BatchResult.

    ``key(item)`` is the item's record id (None for a create, whose id comes from
    its result). A rule or validation failure fails that item only; nothing is
    rolled back across items. ``collect`` removes unused file bytes once at the end.
    """
    from pydantic import ValidationError

    from .errors import invalid

    results = []
    try:
        for item in items:
            identifier = key(item)
            try:
                with db.lock:
                    result = apply(item)
                identifier = identifier or (result or {}).get("id")
                results.append({"id": identifier, "ok": True, "result": result})
            except DomainError as error:
                results.append({"id": identifier, "ok": False, "error": error_body(error)})
            except ValidationError as error:
                failure = error_body(invalid(error))
                results.append({"id": identifier, "ok": False, "error": failure})
    finally:
        if collect and any(result["ok"] for result in results):
            db.collect_blobs()
    return batch_result(results)


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
