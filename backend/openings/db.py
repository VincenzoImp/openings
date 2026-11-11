"""Small connection-per-operation SQLite store; no connections cross worker threads."""

import json
import os
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from .errors import DomainError
from .posting import posting_complete

SCHEMA_VERSION = 10
SCHEMA_SQL = Path(__file__).with_name("schema.sql")
TEMP_PREFIX = ".openings-temp-"


class Database:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # No backup or restore survives a restart; remove copies left by a crash.
        for stale in self.path.parent.glob(TEMP_PREFIX + "*"):
            stale.unlink(missing_ok=True)
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
                    "Use an empty database or a current-format Openings workspace. Existing unrelated databases are not modified.",
                )
            if version not in (0, *MIGRATIONS, SCHEMA_VERSION):
                raise DomainError(400, "schema_version", "Unsupported workspace database version.")
            conn.execute("PRAGMA journal_mode=WAL")
            if version in MIGRATIONS:
                upgrade(conn)
            apply_schema(conn)
        from .compaction import compact

        compact(self)  # an upgrade or large deletions may have left most of the file free
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
        """Remove snapshot parts and file bytes that nothing references any more."""
        from .snapshots import collect_unused

        with self.transaction() as conn:
            collect_unused(conn)


def _migrate_5_to_6(conn):
    # Only obsolete derived data is removed; owned documents and snapshots stay intact.
    conn.execute("DROP TABLE IF EXISTS assessments")
    conn.execute("ALTER TABLE jobs DROP COLUMN initial_score_pending")
    conn.execute("DELETE FROM tasks WHERE kind='score'")
    conn.execute(
        "DELETE FROM settings WHERE key IN ('scoring','scoring_profile_revision','scoring_config_revision','scoring_periodic_last_run')"
    )
    conn.execute(
        "UPDATE settings SET data=json_remove(data,'$.scoring_summary') WHERE key='profile'"
    )


def _migrate_6_to_7(conn):
    # Application planning fields; existing attempts keep their versions and gain empty values.
    conn.execute(
        "ALTER TABLE applications ADD COLUMN priority INTEGER CHECK(priority IS NULL OR priority BETWEEN 1 AND 5)"
    )
    conn.execute(
        "ALTER TABLE applications ADD COLUMN deadline TEXT CHECK(deadline IS NULL OR (length(deadline)=10 AND date(deadline)=deadline))"
    )
    conn.execute(
        "ALTER TABLE applications ADD COLUMN requirements TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(requirements) AND json_type(requirements)='array')"
    )


def _migrate_7_to_8(conn):
    # Attribution, agent runs, questions for the owner and requests for the agent,
    # the stored Ready step and token kinds. Existing rows keep every
    # value; their new actor columns stay NULL, which reads as "unknown (before 0.17)".
    conn.execute(
        """CREATE TABLE runs (
 id TEXT PRIMARY KEY, token_id TEXT NOT NULL, token_name TEXT NOT NULL,
 workflow TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','finished','interrupted')),
 note TEXT NOT NULL DEFAULT '', report TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(report)),
 change_counts TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(change_counts)),
 superseded_by TEXT, idempotency_key TEXT UNIQUE, version INTEGER NOT NULL DEFAULT 1,
 started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL, ended_at TEXT, updated_at TEXT NOT NULL,
 token_kind TEXT
)"""
    )
    conn.execute(
        """CREATE TABLE questions (
 id TEXT PRIMARY KEY, subject_type TEXT CHECK(subject_type IS NULL OR subject_type IN ('job','application','knowledge')),
 job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
 application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
 knowledge_id TEXT REFERENCES knowledge(id) ON DELETE SET NULL,
 subject_label TEXT NOT NULL DEFAULT '', question TEXT NOT NULL, why TEXT NOT NULL DEFAULT '',
 choices TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(choices) AND json_type(choices)='array'),
 state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','answered','withdrawn')),
 answer TEXT NOT NULL DEFAULT '', answer_choice TEXT,
 asked_by_kind TEXT NOT NULL, asked_by_id TEXT, asked_by_name TEXT, asked_by_token_kind TEXT,
 run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
 resolved_by_kind TEXT, resolved_by_id TEXT, resolved_by_name TEXT, resolved_by_token_kind TEXT,
 resolved_at TEXT,
 idempotency_key TEXT UNIQUE, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((job_id IS NOT NULL)+(application_id IS NOT NULL)+(knowledge_id IS NOT NULL)<=1)
)"""
    )
    # A request for the agent: the owner's instruction, read at the next run.
    conn.execute(
        """CREATE TABLE requests (
 id TEXT PRIMARY KEY, subject_type TEXT CHECK(subject_type IS NULL OR subject_type IN ('job','application','knowledge')),
 job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
 application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
 knowledge_id TEXT REFERENCES knowledge(id) ON DELETE SET NULL,
 subject_label TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','taken','done','declined','withdrawn')),
 result TEXT NOT NULL DEFAULT '',
 created_by_kind TEXT NOT NULL, created_by_id TEXT, created_by_name TEXT, created_by_token_kind TEXT,
 taken_by_kind TEXT, taken_by_id TEXT, taken_by_name TEXT, taken_by_token_kind TEXT, taken_at TEXT,
 run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
 resolved_by_kind TEXT, resolved_by_id TEXT, resolved_by_name TEXT, resolved_by_token_kind TEXT,
 resolved_at TEXT,
 idempotency_key TEXT UNIQUE, version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((job_id IS NOT NULL)+(application_id IS NOT NULL)+(knowledge_id IS NOT NULL)<=1)
)"""
    )
    for column in (
        "subject_type TEXT",
        "subject_id TEXT",
        "actor_kind TEXT",
        "actor_id TEXT",
        "actor_name TEXT",
        "actor_token_kind TEXT",
        "run_id TEXT REFERENCES runs(id) ON DELETE SET NULL",
    ):
        conn.execute("ALTER TABLE events ADD COLUMN " + column)
    for column in (
        "author_kind TEXT",
        "author_id TEXT",
        "author_name TEXT",
        "author_token_kind TEXT",
    ):
        conn.execute("ALTER TABLE notes ADD COLUMN " + column)
    # Ready as a stored step: when an application was judged complete, and by whom.
    for column in (
        "ready_at TEXT",
        "ready_by_kind TEXT",
        "ready_by_id TEXT",
        "ready_by_name TEXT",
        "ready_by_token_kind TEXT",
    ):
        conn.execute("ALTER TABLE applications ADD COLUMN " + column)
    # Scoped tokens: every existing token keeps full access as an owner token.
    conn.execute(
        "ALTER TABLE api_tokens ADD COLUMN kind TEXT NOT NULL DEFAULT 'owner' CHECK(kind IN ('owner','agent'))"
    )


def _migrate_8_to_9(conn):
    # Storage only: frozen payloads become shared content-addressed parts and context
    # asset files leave the files table. Every context reads back byte for byte.
    # Re-sighting events go and observations keep only the provider values in use.
    from .retention import trim_history
    from .snapshots import migrate_contexts

    migrate_contexts(conn)
    trim_history(conn)


# Claim metadata keys copied to the typed selection fields: the key has the field's
# name and its value is already a valid value of the field. Nothing else is guessed.
CLAIM_FIELDS_FROM_METADATA = {
    "default_in_cv": "json_type(metadata,'$.default_in_cv') IN ('true','false')",
    "role": "json_type(metadata,'$.role')='text' AND json_extract(metadata,'$.role') IN ('core','supporting','bench')",
    "group": "json_type(metadata,'$.group')='text' AND length(json_extract(metadata,'$.group'))<=100",
}


def _migrate_9_to_10(conn):
    # Additive: the typed policy, typed claim selection fields and the policy versions
    # a context froze. Profile metadata, preferences and roles are copied into
    # unconfirmed policy items and stay where they are; no existing value changes.
    from .policy import migrate_profile

    for column in (
        "default_in_cv INTEGER NOT NULL DEFAULT 0 CHECK(default_in_cv IN (0,1))",
        "role TEXT NOT NULL DEFAULT 'supporting' CHECK(role IN ('core','supporting','bench'))",
        "\"group\" TEXT NOT NULL DEFAULT ''",
    ):
        conn.execute("ALTER TABLE claims ADD COLUMN " + column)
    for name, exact in CLAIM_FIELDS_FROM_METADATA.items():
        conn.execute(
            f"UPDATE claims SET \"{name}\"=json_extract(metadata,'$.{name}') "
            f"WHERE json_valid(metadata) AND {exact}"
        )
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='context_inputs'").fetchone():
        conn.execute("ALTER TABLE context_inputs ADD COLUMN policy TEXT")
    migrate_profile(conn)


# Each step upgrades from its key to the next version; steps chain inside one transaction.
MIGRATIONS = {
    5: _migrate_5_to_6,
    6: _migrate_6_to_7,
    7: _migrate_7_to_8,
    8: _migrate_8_to_9,
    9: _migrate_9_to_10,
}


def upgrade(conn):
    """Upgrade an older supported workspace to the current schema, all or nothing."""
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        while version in MIGRATIONS:
            MIGRATIONS[version](conn)
            version += 1
        conn.execute(f"PRAGMA user_version={version}")


def apply_schema(conn):
    """Create missing tables and indexes and derive missing context summaries."""
    from .staleness import backfill_context_inputs

    conn.executescript(SCHEMA_SQL.read_text())
    backfill_context_inputs(conn)
    conn.commit()


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
