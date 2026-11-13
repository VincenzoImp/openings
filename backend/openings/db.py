"""Small connection-per-operation SQLite store; no connections cross worker threads."""

import json
import logging
import math
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from . import compaction
from .errors import DomainError
from .posting import posting_complete

LOG = logging.getLogger(__name__)
SCHEMA_VERSION = 14
SCHEMA_SQL = Path(__file__).with_name("schema.sql")
TEMP_PREFIX = ".openings-temp-"
# A copy of the workspace taken before an in-place upgrade: the copy itself, the
# write-ahead log of the upgrade and some slack must fit on the data volume.
PRE_UPGRADE_ROOM = 2.2
PRE_UPGRADE_KEEP = 2
MIB = 1024**2


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


def pre_upgrade_copies(path):
    """The copies ``copy_before_upgrade`` kept beside the workspace ``path``, newest first."""
    path = Path(path)
    pattern = re.compile(re.escape(path.stem) + r"\.pre-schema\d+-(\d{8}T\d{6}Z)\.sqlite")
    found = [
        (match.group(1), item.name, item)
        for item in path.parent.iterdir()
        if (match := pattern.fullmatch(item.name)) and item.is_file()
    ]
    return [item for _, _, item in sorted(found, reverse=True)]


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
            if version in MIGRATIONS and existing_tables:
                # Before anything is written: a verified copy at the old version.
                self.copy_before_upgrade(conn, version)
            conn.execute("PRAGMA journal_mode=WAL")
            if version in MIGRATIONS:
                upgrade(conn)
            apply_schema(conn)
        from .compaction import compact

        compact(self)  # an upgrade or large deletions may have left most of the file free
        self.path.chmod(0o600)

    def copy_before_upgrade(self, conn, version):
        """Keep a verified copy of the workspace at ``version`` before upgrading it in place.

        The copy is ``<name>.pre-schema<version>-<UTC timestamp>.sqlite`` beside the
        workspace, mode 0600. Without room for it (``PRE_UPGRADE_ROOM`` times the
        file), or when it fails its check, the start is refused and the workspace
        file is left as it was. The two most recent copies are kept; older ones are
        removed only after the new one is verified.
        """
        size = file_bytes(self.path)
        needed = math.ceil(PRE_UPGRADE_ROOM * size)
        room, free = compaction.has_room(self.path.parent, needed)
        if not room:
            raise DomainError(
                507,
                "upgrade_room",
                f"Openings keeps a copy of the workspace before upgrading it from schema "
                f"{version} and needs {math.ceil(needed / MIB)} MiB of free space on the data "
                f"volume ({self.path.parent}); {free // MIB} MiB are free. Free some space and "
                "start again. The workspace file was not changed.",
                {"needed_bytes": needed, "free_bytes": free, "database_bytes": size},
            )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        target = self.path.parent / f"{self.path.stem}.pre-schema{version}-{utc_stamp()}.sqlite"
        temp = self.temp_file("pre-upgrade")
        os.unlink(temp)

        def same_version(copy):
            if copy.execute("PRAGMA user_version").fetchone()[0] != version:
                raise sqlite3.DatabaseError("The copy does not have the workspace's version.")

        try:
            write_verified_copy(conn, temp, target, same_version)
        except (sqlite3.Error, OSError) as error:
            raise DomainError(
                500,
                "upgrade_copy",
                f"Openings could not keep a verified copy of the workspace before upgrading it "
                f"from schema {version} ({error}). The workspace file was not changed.",
            ) from error
        for old in pre_upgrade_copies(self.path)[PRE_UPGRADE_KEEP:]:
            old.unlink(missing_ok=True)
        compaction.fsync_directory(self.path.parent)
        LOG.warning(
            "Copied the schema %d workspace to %s before upgrading it to schema %d.",
            version,
            target,
            SCHEMA_VERSION,
        )
        return target

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
    from .policy.upgrade import migrate_profile

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


# The applications table of schema 11; schema.sql holds the same text without
# note, which schema 13 dropped. Changing a CHECK constraint in SQLite means
# building the table again (_migrate_10_to_11).
APPLICATIONS = """CREATE TABLE {name} (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','applied','interview','offer','closed')),
 outcome TEXT CHECK(outcome IS NULL OR outcome IN ('accepted','rejected','not_pursued','no_response')),
 note TEXT NOT NULL DEFAULT '', questions TEXT NOT NULL DEFAULT '[]', answers TEXT NOT NULL DEFAULT '{{}}',
 version INTEGER NOT NULL DEFAULT 1, idempotency_key TEXT UNIQUE, applied_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 priority INTEGER CHECK(priority IS NULL OR priority BETWEEN 1 AND 5),
 deadline TEXT CHECK(deadline IS NULL OR (length(deadline)=10 AND date(deadline)=deadline)),
 requirements TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(requirements) AND json_type(requirements)='array'),
 ready_at TEXT, ready_by_kind TEXT, ready_by_id TEXT, ready_by_name TEXT, ready_by_token_kind TEXT,
 concluded_on TEXT CHECK(concluded_on IS NULL OR (length(concluded_on)=10 AND date(concluded_on)=concluded_on))
)"""


def _migrate_10_to_11(conn):
    # Additive: employer responses, the no_response outcome with the day it was
    # concluded, one response for each application whose stage already says the
    # employer answered (outcomes.backfill_responses), and the part hashes each
    # context froze (context_inputs.parts, derived from the payloads when the
    # workspace opens: staleness.backfill_context_inputs). The outcome CHECK constraint
    # changes, so the applications table is built again: every row keeps its rowid
    # and values, its indexes and triggers are recreated, and the tables that
    # reference it keep their rows (upgrade() runs with foreign keys off and checks
    # them before committing).
    from .outcomes import SCHEMA, backfill_responses

    columns = [row[1] for row in conn.execute("PRAGMA table_info(applications)")]
    kept = conn.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name='applications' "
        "AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY rowid"
    ).fetchall()
    count = conn.execute("SELECT count(*) FROM applications").fetchone()[0]
    conn.execute(APPLICATIONS.format(name="applications_rebuilt"))
    names = ",".join(f'"{column}"' for column in columns)
    conn.execute(
        f"INSERT INTO applications_rebuilt(rowid,{names}) SELECT rowid,{names} FROM applications"
    )
    if conn.execute("SELECT count(*) FROM applications_rebuilt").fetchone()[0] != count:
        raise sqlite3.IntegrityError("The applications table was not copied completely.")
    conn.execute("DROP TABLE applications")
    conn.execute("ALTER TABLE applications_rebuilt RENAME TO applications")
    for (sql,) in kept:
        conn.execute(sql)
    # executescript would commit the surrounding upgrade, so run each statement.
    for statement in SCHEMA.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    backfill_responses(conn)
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='context_inputs'").fetchone():
        conn.execute("ALTER TABLE context_inputs ADD COLUMN parts TEXT")


def _migrate_11_to_12(conn):
    # Additive. Per-workspace local notes of skills (skill_notes). Ingest signals
    # (job_signals, derived from each job and computed in the background after the
    # upgrade: SignalService.backfill), who dismissed each job, when, why and
    # through which policy rule (jobs.dismissed_*, filled for dismissed jobs from
    # their last dismissal event) and postings a company board no longer lists
    # (postings.unlisted_at, from the last complete run of each board). No existing
    # value changes.
    from . import job_signals, skill_notes

    skill_notes.migrate(conn)
    job_signals.migrate(conn)


def _migrate_12_to_13(conn):
    # The breaking group of 0.22, both parts in this one transaction.
    # One timeline: notes gain their author's run and a pin, and each application
    # note becomes a pinned note with the same text (applications.note is dropped).
    # Source-canonical documents: a CV or letter revision is its .tex source and
    # PDF. Its structured content moves, unchanged, to legacy_content (read-only),
    # the evidence ids it cited are copied to claim_ids and knowledge_ids, and its
    # text is derived from the attached source. Files gain source_sha256 (NULL for
    # every existing file). Ids, files, hashes, review states and versions stay.
    # The two parts touch different tables; neither reads what the other writes.
    from .documents.upgrade import migrate_to_13
    from .workspace import timeline_upgrade

    timeline_upgrade.migrate(conn)
    migrate_to_13(conn)


def _migrate_13_to_14(conn):
    # 0.23 removes what 0.19 to 0.22 deprecated, keeping every value it held.
    # A job's manual availability (anything but 'unknown') becomes a note on the
    # job with the value, checked byte for byte, then jobs.availability is dropped.
    # Each non-empty Profile preferences and roles text must be held by a policy
    # item (0.19 copied them into decision items); one that is not is copied into
    # a new unconfirmed decision item, and then both fields leave the Profile.
    # Frozen contexts keep the Profile and job they froze.
    from .policy import profile_upgrade
    from .workspace import availability_upgrade

    availability_upgrade.migrate(conn)
    profile_upgrade.migrate(conn)


# Each step upgrades from its key to the next version; steps chain inside one transaction.
MIGRATIONS = {
    5: _migrate_5_to_6,
    6: _migrate_6_to_7,
    7: _migrate_7_to_8,
    8: _migrate_8_to_9,
    9: _migrate_9_to_10,
    10: _migrate_10_to_11,
    11: _migrate_11_to_12,
    12: _migrate_12_to_13,
    13: _migrate_13_to_14,
}


def upgrade(conn):
    """Upgrade an older supported workspace to the current schema, all or nothing.

    Foreign keys are off while the steps run, because building a table again (to
    change a constraint) drops the old one, which would otherwise delete the rows
    that reference it. SQLite ignores the setting inside a transaction, so it is
    changed around it; before committing, no reference may be broken that was not
    broken before.
    """
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            broken = {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            while version in MIGRATIONS:
                MIGRATIONS[version](conn)
                version += 1
            if {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")} - broken:
                raise sqlite3.IntegrityError("The upgrade would break references between records.")
            conn.execute(f"PRAGMA user_version={version}")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


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
