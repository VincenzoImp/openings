"""Idempotency keys of the creates whose records have no key column of their own.

Applications, contexts, responses, policy items, runs, questions and requests keep
their key on the record. Jobs, notes, Career entries, claims, templates, document
revisions, sources and API tokens record it in ``idempotency_keys``: the table of
the record, the key, the SHA-256 of the request without the key and the id of the
record the first request created or found. A retry with the same key and request
returns that record; the same key with another request is refused. A key whose
record no longer exists is free again, as a key column would be.
"""

import hashlib

from pydantic import BaseModel

from .common import encode, now
from .errors import conflict

# The tables whose creates take a key here; their records have an ``id``.
TABLES = frozenset(
    {"jobs", "notes", "knowledge", "claims", "templates", "documents", "sources", "api_tokens"}
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
