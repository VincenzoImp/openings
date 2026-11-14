"""Small connection-per-operation SQLite store; no connections cross worker threads."""

import json
import os
import sqlite3
import tempfile
import threading
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from . import compaction
from .errors import DomainError
from .migrations import MIGRATIONS, UpgradeError, recover
from .posting import posting_complete

SCHEMA_VERSION = 15
SCHEMA_SQL = Path(__file__).with_name("schema.sql")
TEMP_PREFIX = ".openings-temp-"
# The only workspace an upgrade starts from is one of the previous schema.
OLDER = (
    "This workspace was written by Openings older than 0.23. Open it once with the 0.23 "
    "image, then start this version."
)
NEWER = (
    "This workspace was written by a newer Openings (schema {version}). Start that version "
    "or a newer one."
)


def utc_stamp():
    """A UTC timestamp for file names: ``20260302T080000Z``."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def file_bytes(path):
    """Bytes of a SQLite file and its write-ahead log; a missing file counts as zero."""
    total = 0
    for name in (Path(path), Path(str(path) + "-wal")):
        try:
            total += name.stat().st_size
        except FileNotFoundError:
            pass
    return total


def write_verified_copy(conn, temp, target, check=None):
    """``VACUUM INTO`` a temporary name, check it, make it private and rename it into place.

    ``temp`` must not exist. The copy must pass ``quick_check`` (and ``check`` on
    its connection, when given) before it takes its final name; the rename and the
    file are flushed to disk. On failure the temporary copy is removed and the
    error is raised.
    """
    try:
        conn.execute("VACUUM INTO ?", (str(temp),))
        with closing(sqlite3.connect(temp)) as copy:
            if copy.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("The copy failed its integrity check.")
            if check:
                check(copy)
        os.chmod(temp, 0o600)
        handle = os.open(temp, os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
        os.replace(temp, target)
        compaction.fsync_directory(Path(target).parent)
    except BaseException:
        Database.remove_temp(temp)
        raise


def schema_error(version):
    """The refusal of a workspace file whose schema this version does not open or upgrade."""
    message = NEWER.format(version=version) if version > SCHEMA_VERSION else OLDER
    return DomainError(400, "schema_version", message, {"schema_version": version})


def upgrade_error(error):
    """An ``UpgradeError`` of a migration as the refusal to start."""
    status = {"upgrade_room": 507, "upgrade_state": 409, "upgrade_source": 400}.get(error.code, 500)
    return DomainError(status, error.code, error.message, error.details)


def read_version(path):
    """The schema of the file at ``path`` and whether it has tables; (0, False) when missing."""
    if not Path(path).exists():
        return 0, False
    with closing(sqlite3.connect(path)) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone()
    return version, tables is not None


def create(path):
    """Create a new workspace from ``schema.sql``, all or nothing."""
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript("BEGIN;\n" + SCHEMA_SQL.read_text() + "\nCOMMIT;")


def prepare(path):
    """Bring the file at ``path`` to ``SCHEMA_VERSION``: create it, upgrade it or open it.

    A missing or empty file becomes a new workspace. A workspace of the previous
    schema is upgraded by its migration (``migrations/``); any other version is
    refused with what to do. Files an interrupted upgrade left are resolved first.
    """
    path = Path(path)
    try:
        recover(path)
        version, tables = read_version(path)
        if version == SCHEMA_VERSION:
            return
        if version == 0:
            if tables:
                raise DomainError(
                    400,
                    "schema_version",
                    "Use an empty database or a current-format Openings workspace. Existing "
                    "unrelated databases are not modified.",
                )
            create(path)
        elif version in MIGRATIONS:
            MIGRATIONS[version](path, schema=SCHEMA_SQL.read_text())
        else:
            raise schema_error(version)
    except UpgradeError as error:
        raise upgrade_error(error) from error


class Database:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # No backup or restore survives a restart; remove copies left by a crash.
        for stale in self.path.parent.glob(TEMP_PREFIX + "*"):
            stale.unlink(missing_ok=True)
        self.lock = threading.RLock()
        prepare(self.path)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        from .compaction import compact

        compact(self)  # large deletions may have left most of the file free
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

    def temp_file(self, purpose):
        """Reserve a private file beside the database, on the same data volume."""
        handle, name = tempfile.mkstemp(
            prefix=TEMP_PREFIX + purpose + "-", suffix=".sqlite", dir=self.path.parent
        )
        os.close(handle)
        return name

    @staticmethod
    def remove_temp(name):
        """Remove a temporary copy and the WAL sidecars SQLite created beside it."""
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(str(name) + suffix).unlink(missing_ok=True)

    def backup(self, destination):
        with self.lock, self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)

    def collect_blobs(self):
        """Remove file bytes that no file references any more."""
        with self.transaction() as conn:
            collect_unused(conn)


def collect_unused(conn):
    """Remove file bytes that no file references any more, in the caller's transaction."""
    conn.execute("DELETE FROM blobs WHERE sha256 NOT IN (SELECT sha256 FROM files)")


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
