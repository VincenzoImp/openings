"""Schema 15 (0.24 to 0.27) to schema 16 (0.28): a new file with the workspace copied in.

0.28 adds one column, ``applications.salary`` (#348); nothing leaves the schema, so
the upgrade keeps every table, row and value and writes no archive.

The workspace is not changed in place. A new file, ``<db>.next``, is created from
``schema.sql`` (the same script that creates a new workspace), the schema-15 file
is attached read-only and every table is copied with one ``INSERT ... SELECT`` in one
transaction. After the checks below the original file becomes the pre-upgrade copy
and the new file takes its name, so an upgraded workspace has exactly the objects
of a new one and the original is never written.

``upgrade(path)``, at startup:

1. Room: the volume needs ``ROOM_FACTOR`` times the database; otherwise the start
   is refused and nothing is written.
2. ``wal_checkpoint(TRUNCATE)`` on the original; ``<db>.next`` from ``schema.sql``;
   the original attached read-only as ``old``.
3. One transaction: each table in the order of ``schema.sql``, then a rebuild of
   the search index. A column new in schema 16 takes its default.
4. Checks: ``integrity_check``, no broken reference the original did not have,
   the row count of every table and ``INVARIANTS``. Any failure removes the new
   file and refuses the start with the reason.
5. Swap: the original becomes ``<stem>.pre-0.28.sqlite``, the new file takes the
   database's name, the directory is flushed and both paths are logged.
6. ``recover(path)`` at the next start finishes an interrupted swap or removes an
   unfinished new file (the upgrade then runs again).

``convert(source, target)`` is steps 2 to 4 for a copy (restoring an uploaded
schema-15 backup): the source file is only read.

This module is frozen with its release: it imports only the standard library and
holds every statement it needs. Until 0.28 is released, the issues of that release
extend it ("edit the unreleased migration"): a table or column that leaves the
schema is refused by ``_plan`` until the migration says where its values go, and a
value that must not change gets an ``INVARIANTS`` entry.
"""

import json
import logging
import math
import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger(__name__)
FROM_VERSION = 15
TO_VERSION = 16
RELEASE = "0.28"
PREVIOUS_RELEASE = "0.27"
ROOM_FACTOR = 2.2
MIB = 1024**2
SCHEMA_SQL = Path(__file__).resolve().parents[1] / "schema.sql"


class UpgradeError(Exception):
    """The upgrade was refused or failed; the workspace file is unchanged.

    ``code`` is ``upgrade_room`` (not enough free space), ``upgrade_failed`` (a
    step or a check failed), ``upgrade_state`` (files of an interrupted upgrade
    that cannot be resolved automatically) or ``upgrade_source`` (the file is not
    a complete schema-15 workspace).
    """

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


# Values the copy must keep: (what, SQL over the new file, SQL over the original).
_STAGES = "SELECT group_concat(id||status||coalesce(outcome,''),',') FROM "
INVARIANTS = (
    (
        "application stages",
        _STAGES + "(SELECT * FROM main.applications ORDER BY id)",
        _STAGES + "(SELECT * FROM old.applications ORDER BY id)",
    ),
    (
        "applications without a salary",
        "SELECT count(*) FROM main.applications WHERE salary IS NULL",
        "SELECT count(*) FROM old.applications",
    ),
    (
        "job versions",
        "SELECT total(version) FROM main.jobs",
        "SELECT total(version) FROM old.jobs",
    ),
)


@dataclass(frozen=True)
class Files:
    database: Path
    next: Path
    pre_upgrade: Path


def files(path):
    """The files of an upgrade of the database at ``path``."""
    path = Path(path)
    return Files(
        database=path,
        next=path.with_name(path.name + ".next"),
        pre_upgrade=path.with_name(f"{path.stem}.pre-{RELEASE}.sqlite"),
    )


def upgrade(path, schema=None):
    """Upgrade the schema-15 workspace at ``path`` to schema 16 (steps 1 to 5)."""
    paths = files(Path(path).resolve())
    schema = SCHEMA_SQL.read_text() if schema is None else schema
    _check_room(paths.database)
    report = convert(paths.database, paths.next, schema)
    _swap(paths)
    LOG.warning(
        "Upgraded the workspace to schema %d. The schema-%d file is kept as %s.",
        TO_VERSION,
        FROM_VERSION,
        paths.pre_upgrade,
    )
    LOG.info("Upgrade report: %s", json.dumps(report, sort_keys=True))
    return report


def recover(path):
    """Resolve the files an interrupted upgrade left beside the database (step 6).

    The database missing while the new file and the pre-upgrade copy exist means
    the swap stopped between its two renames, after every check passed: it is
    finished. A new file beside the database is an unfinished upgrade: it is
    removed and the upgrade runs again.
    """
    paths = files(Path(path).resolve())
    if paths.database.exists():
        if paths.next.exists():
            _remove(paths.next)
            LOG.warning("Removed %s, left by an interrupted upgrade.", paths.next)
        return
    if paths.next.exists() and paths.pre_upgrade.exists():
        _replace(paths.next, paths.database)
        _fsync_directory(paths.database.parent)
        LOG.warning(
            "Finished an interrupted upgrade: %s is the schema-%d workspace and %s the "
            "schema-%d copy.",
            paths.database,
            TO_VERSION,
            paths.pre_upgrade,
            FROM_VERSION,
        )
    elif paths.next.exists() or paths.pre_upgrade.exists():
        present = paths.next if paths.next.exists() else paths.pre_upgrade
        raise UpgradeError(
            "upgrade_state",
            f"{paths.database.name} is missing but {present.name} is in {present.parent}. "
            f"To go back to Openings {PREVIOUS_RELEASE}, move {paths.pre_upgrade.name} to "
            f"{paths.database.name} and start the {PREVIOUS_RELEASE} image; to start a new "
            f"workspace, move {present.name} out of the folder.",
        )


def convert(source, target, schema=None):
    """Copy the schema-15 file ``source`` into a new schema-16 file ``target`` (steps 2-4).

    ``source`` is only read (after a checkpoint of its write-ahead log). On failure
    ``target`` is removed and ``UpgradeError`` is raised. Returns the row counts.
    """
    source, target = Path(source), Path(target)
    schema = SCHEMA_SQL.read_text() if schema is None else schema
    _remove(target)
    try:
        _checkpoint(source)
        report = _build(source, target, schema)
        _verify(source, target, report)
        return report
    except Exception as error:
        _remove(target)
        if isinstance(error, UpgradeError):
            raise
        raise UpgradeError(
            "upgrade_failed",
            f"The upgrade to Openings {RELEASE} stopped ({error}). The workspace file was not "
            "changed.",
        ) from error


# Planning: what each table copies.


def _tables(conn, schema):
    """Ordinary tables of ``schema`` in creation order: name -> without rowid."""
    order = {
        name: index
        for index, (name,) in enumerate(
            conn.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table'")
        )
    }
    tables = {
        row[1]: bool(row[4])
        for row in conn.execute(f"PRAGMA {schema}.table_list")
        if row[2] == "table" and not row[1].startswith("sqlite_")
    }
    return dict(sorted(tables.items(), key=lambda item: order.get(item[0], len(order))))


def _columns(conn, schema, table):
    """Columns of a table: name -> (declared type, primary key position)."""
    return {
        row[1]: (row[2], row[5])
        for row in conn.execute(f'PRAGMA {schema}.table_xinfo("{table}")')
        if row[6] == 0
    }


def _rowid(columns, without_rowid):
    """Whether rows have a rowid of their own (not an INTEGER PRIMARY KEY)."""
    key = [name for name, (_, pk) in columns.items() if pk]
    return not without_rowid and not (len(key) == 1 and columns[key[0]][0].upper() == "INTEGER")


def _quoted(names):
    return ",".join(f'"{name}"' for name in names)


def _plan(conn):
    """The copy statement of each table: (name, INSERT, count of the source rows)."""
    new, old = _tables(conn, "main"), _tables(conn, "old")
    missing = sorted(set(new) - set(old))
    if missing:
        raise UpgradeError(
            "upgrade_source",
            f"The workspace has no {', '.join(missing)} table, so it is not a complete schema-"
            f"{FROM_VERSION} workspace.",
        )
    dropped = sorted(set(old) - set(new))
    copies = []
    for name, without_rowid in new.items():
        target, origin = _columns(conn, "main", name), _columns(conn, "old", name)
        dropped += [f"{name}.{column}" for column in origin if column not in target]
        names = [column for column in target if column in origin]
        values = [f'o."{column}"' for column in names]
        if _rowid(target, without_rowid) and _rowid(origin, old[name]):
            # Rows keep their rowid: the search index and rowid order depend on it.
            names.insert(0, "rowid")
            values.insert(0, "o.rowid")
        source = f'FROM old."{name}" AS o'
        insert = f'INSERT INTO main."{name}"({_quoted(names)}) SELECT {",".join(values)} {source}'
        copies.append((name, insert, f"SELECT count(*) {source}"))
    if dropped:
        # Nothing leaves schema 16: a value without a place would be lost.
        raise UpgradeError(
            "upgrade_failed",
            f"The schema-{TO_VERSION} file has no place for {', '.join(dropped)}.",
        )
    return copies


# Steps.


def _connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ("?mode=ro" if readonly else "")
    conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def _attach(conn, source):
    conn.execute("ATTACH DATABASE ? AS old", (Path(source).resolve().as_uri() + "?mode=ro",))


def _bytes(path):
    total = 0
    for name in (Path(path), Path(str(path) + "-wal")):
        try:
            total += name.stat().st_size
        except FileNotFoundError:
            pass
    return total


def _check_room(path):
    """Step 1: refuse before writing anything when the volume is too small."""
    size = _bytes(path)
    needed = math.ceil(ROOM_FACTOR * size)
    free = shutil.disk_usage(Path(path).parent).free
    if free < needed:
        raise UpgradeError(
            "upgrade_room",
            f"Upgrading this workspace to Openings {RELEASE} needs {math.ceil(needed / MIB)} MiB "
            f"of free space on the data volume ({Path(path).parent}); {free // MIB} MiB are free. "
            "Free some space and start again. The workspace file was not changed.",
            {"needed_bytes": needed, "free_bytes": free, "database_bytes": size},
        )


def _checkpoint(source):
    """Move the write-ahead log into the file, so the copy reads one file."""
    conn = sqlite3.connect(source, isolation_level=None)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != FROM_VERSION:
            raise UpgradeError(
                "upgrade_source", f"The workspace has schema {version}, not {FROM_VERSION}."
            )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _build(source, target, schema):
    """Steps 2 and 3: the new file and the copy in one transaction."""
    conn = _connect(target)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.executescript(schema)
        _attach(conn, source)
        report = {"copied": {}, "expected": {}}
        conn.execute("BEGIN IMMEDIATE")
        for name, insert, count in _plan(conn):
            # Rows schema.sql seeds are replaced by the workspace's own.
            conn.execute(f'DELETE FROM main."{name}"')
            report["expected"][name] = conn.execute(count).fetchone()[0]
            report["copied"][name] = conn.execute(insert).rowcount
        conn.execute("INSERT INTO main.jobs_fts(jobs_fts) VALUES('rebuild')")
        conn.execute("COMMIT")
    finally:
        conn.close()
    _fsync(target)
    return report


def _verify(source, target, report):
    """Step 4: the checks that must pass before the new file replaces the original."""
    conn = _connect(target, readonly=True)
    try:
        _attach(conn, source)
        failures = []
        if conn.execute("PRAGMA main.integrity_check").fetchone()[0] != "ok":
            failures.append("the new file failed its integrity check")
        if conn.execute("PRAGMA main.user_version").fetchone()[0] != TO_VERSION:
            failures.append(f"the new file is not at schema {TO_VERSION}")
        before = {tuple(row[:3]) for row in conn.execute("PRAGMA old.foreign_key_check")}
        broken = {tuple(row[:3]) for row in conn.execute("PRAGMA main.foreign_key_check")}
        if broken - before:
            failures.append(f"{len(broken - before)} references between records would break")
        for name, expected in report["expected"].items():
            actual = conn.execute(f'SELECT count(*) FROM main."{name}"').fetchone()[0]
            if actual != expected:
                failures.append(f"{name} has {actual} rows instead of {expected}")
        for what, after, earlier in INVARIANTS:
            values = conn.execute(after).fetchone()[0], conn.execute(earlier).fetchone()[0]
            if values[0] != values[1]:
                failures.append(f"{what}: {values[0]} instead of {values[1]}")
    finally:
        conn.close()
    if failures:
        raise UpgradeError(
            "upgrade_failed",
            f"The upgrade to Openings {RELEASE} did not pass its checks: "
            + "; ".join(failures)
            + ". The workspace file was not changed.",
            {"failures": failures},
        )


def _swap(paths):
    """Step 5: the original becomes the pre-upgrade copy and the new file takes its name."""
    wal = Path(str(paths.database) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise UpgradeError(
            "upgrade_failed",
            f"{wal.name} still holds changes, so the workspace is in use by another process. "
            "Stop it and start again. The workspace file was not changed.",
        )
    for suffix in ("-wal", "-shm"):
        _remove(Path(str(paths.database) + suffix))
    for suffix in ("", "-wal", "-shm"):
        _remove(Path(str(paths.pre_upgrade) + suffix))
    _replace(paths.database, paths.pre_upgrade)
    _fsync_directory(paths.database.parent)
    _replace(paths.next, paths.database)
    _fsync_directory(paths.database.parent)


# File helpers; _replace is separate so a test can stop the swap between its renames.


def _replace(source, target):
    os.replace(source, target)


def _remove(path):
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _fsync(path):
    handle = os.open(path, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _fsync_directory(directory):
    try:
        handle = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)
