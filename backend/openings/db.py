"""Small connection-per-operation SQLite store; no connections cross worker threads."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .errors import DomainError
from .posting import posting_complete
from .identities import job_identities

SCHEMA_VERSION = 2


def migrate_workspace(conn):
    """Upgrade the supported workspace format atomically, preserving ambiguous aliases.

    Old archives may already contain duplicate source keys. Keep both jobs and
    let ingestion require an explicit merge instead of silently losing history.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 1:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            conn.execute(
                "CREATE TABLE job_identities(identity TEXT NOT NULL,job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,PRIMARY KEY(identity,job_id))"
            )
            conn.execute("CREATE INDEX job_identities_job ON job_identities(job_id)")
            conn.execute(
                "CREATE TABLE posting_details(identity TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,checked_at TEXT NOT NULL)"
            )
            conn.execute("CREATE INDEX posting_details_job ON posting_details(job_id)")
            for row in conn.execute("SELECT id,url FROM jobs"):
                conn.executemany(
                    "INSERT OR IGNORE INTO job_identities VALUES(?,?)",
                    [(key, row[0]) for key in job_identities(row[1])],
                )
            for row in conn.execute("SELECT job_id,identity,url,payload FROM postings"):
                keys = job_identities(row[2], json.loads(row[3]).get("source_key"))
                conn.executemany(
                    "INSERT OR IGNORE INTO job_identities VALUES(?,?)",
                    [(key, row[0]) for key in set(keys + [row[1]])],
                )
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


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
            if version not in (0, 1, SCHEMA_VERSION):
                raise DomainError(400, "schema_version", "Unsupported workspace database version.")
            conn.execute("PRAGMA journal_mode=WAL")
            migrate_workspace(conn)
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.create_function("posting_complete", 3, posting_complete, deterministic=True)
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
