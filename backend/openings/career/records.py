"""Shared row helpers: settings rows, record lookup, claim records and pagination."""

from __future__ import annotations

import json

from pydantic import BaseModel

from ..common import decode_record, encode, now
from ..errors import DomainError, missing


def _claim(row, *, full=True):
    """A claim row as returned by reads."""
    row = decode_record(row, ["metadata"]) if full else dict(row)
    row["career_id"] = row.pop("knowledge_id")
    row["approved"] = bool(row["approved"])
    row["always_include"] = bool(row["always_include"])
    return row


def values(value):
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_unset=True)
    return dict(value)


def _setting(conn, key, default):
    row = conn.execute("SELECT * FROM settings WHERE key=?", (key,)).fetchone()
    return (
        {"data": json.loads(row["data"]), "version": row["version"]}
        if row
        else {"data": default, "version": 0}
    )


def _write_setting(conn, key, data, version):
    conn.execute(
        "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
        (key, encode(data), version, now()),
    )


def _get(conn, table, record_id, label):
    # Table names are fixed internally, never client-controlled.
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
    if row is None:
        missing(label)
    return dict(row)


def _page(limit, offset):
    if not 1 <= limit <= 200 or offset < 0:
        raise DomainError(422, "pagination", "Limit must be 1–200 and offset must be nonnegative.")
