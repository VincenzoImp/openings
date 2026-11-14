"""Idempotency keys of creates.

A create that takes an ``idempotency_key`` records it in ``idempotency_keys``: the
table of the record, the key, the SHA-256 of the request without the key and the
id of the record the first request created or found. A retry with the same key and
request returns that record; the same key with another request is refused (409).
A key whose record no longer exists is free again. (Before schema 15 some tables
kept the key on the record; the 0.24 upgrade archives those values.)
"""

import hashlib

from pydantic import BaseModel

from .common import encode, now
from .errors import conflict

# The tables whose creates take a key here; their records have an ``id``.
TABLES = frozenset(
    {
        "api_tokens",
        "applications",
        "claims",
        "contexts",
        "documents",
        "jobs",
        "knowledge",
        "notes",
        "responses",
        "sources",
        "templates",
    }
)


def fingerprint(value):
    """The SHA-256 of a create request without its idempotency key."""
    data = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    data.pop("idempotency_key", None)
    return hashlib.sha256(encode(data).encode()).hexdigest()


def replay(conn, table, key, digest):
    """The id of the record a request with this key created, or None for a first use.

    Runs in a write transaction: a key whose record is gone is removed.
    """
    if not key:
        return None
    assert table in TABLES
    row = conn.execute(
        "SELECT fingerprint,record_id FROM idempotency_keys WHERE scope=? AND key=?",
        (table, key),
    ).fetchone()
    if row is None:
        return None
    # Table names are fixed internally, never client-controlled.
    if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (row[1],)).fetchone():
        conn.execute("DELETE FROM idempotency_keys WHERE scope=? AND key=?", (table, key))
        return None
    if row[0] != digest:
        conflict("This idempotency key was used for another request.")
    return row[1]


def remember(conn, table, key, digest, record_id):
    """Record the record a first request with this key created or found."""
    if key:
        assert table in TABLES
        conn.execute(
            "INSERT INTO idempotency_keys(scope,key,fingerprint,record_id,created_at) VALUES(?,?,?,?,?)",
            (table, key, digest, record_id, now()),
        )
