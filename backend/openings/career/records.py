"""Row helpers of the career area: settings rows and highlight records."""

from __future__ import annotations

import json

from pydantic import BaseModel

from ..common import decode_record, encode, now


def _highlight(row, *, full=True):
    """A highlight row as returned by reads."""
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
