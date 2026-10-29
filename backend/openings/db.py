"""Small connection-per-operation SQLite store; no connections cross worker threads."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .errors import DomainError


class Database:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            existing_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if version == 0 and existing_tables:
                raise DomainError(
                    400,
                    "schema_version",
                    "Use an empty database or a compatible Openings workspace. Existing unrelated databases are not modified.",
                )
            if version not in (0, 1):
                raise DomainError(400, "schema_version", "Unsupported workspace database version.")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.lock, self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def one(self, sql, params=()):
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def all(self, sql, params=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def execute(self, sql, params=()):
        with self.transaction() as conn:
            return conn.execute(sql, params).rowcount

    def backup(self, destination):
        with self.lock, self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)

    def collect_blobs(self):
        return self.execute("DELETE FROM blobs WHERE sha256 NOT IN (SELECT sha256 FROM files)")


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
