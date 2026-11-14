"""Consistent portable snapshots and validated in-place restore."""

import asyncio
import json
import os
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from . import events
from .common import encode, now
from .compaction import compact
from .db import SCHEMA_VERSION, schema_error, utc_stamp
from .errors import DomainError
from .migrations import CONVERSIONS, UpgradeError, m15
from .retention import KEPT_RUNS_PER_SOURCE, retention_days

# Slack for sidecar files and for an upgraded copy slightly larger than its upload.
RESTORE_MARGIN = 64 * 1024**2
MIB = 1024**2


def database_bytes(db):
    """Bytes the workspace takes on the data volume: the file and its write-ahead log.

    The log can disappear between two calls when the last connection closes, so a
    missing file counts as zero bytes instead of failing the read.
    """
    total = 0
    for path in (db.path, Path(str(db.path) + "-wal")):
        try:
            total += path.stat().st_size
        except FileNotFoundError:
            pass
    return total


def replace_room(source, database):
    """Free bytes that replacing the workspace with a file of ``source`` bytes needs.

    The rollback copy of the current database, the write-ahead log that receives
    every page of the restored one, and the growth of the file when it is larger.
    """
    return database + source + max(0, source - database) + RESTORE_MARGIN


def restore_room(upload, database):
    """Free bytes on the data volume that restoring an ``upload``-byte backup needs.

    The upload itself and the upgraded copy of an earlier-format backup are written
    beside the database before it is replaced (``replace_room``).
    """
    return 2 * upload + replace_room(upload, database)


def restore_limit(free, database):
    """The largest backup that fits in ``free`` bytes: the inverse of ``restore_room``."""
    room = free - RESTORE_MARGIN
    if room <= 4 * database:
        return max(0, (room - database) // 3)
    return room // 4


def configured_restore_limit():
    """``OPENINGS_MAX_RESTORE_MB`` as bytes: an optional upper bound, unset by default."""
    value = (os.environ.get("OPENINGS_MAX_RESTORE_MB") or "").strip()
    return max(0, int(value)) * MIB if value else None


def storage_status(db):
    """Database size, free space on its volume, the restore limit and retention."""
    size, free = database_bytes(db), shutil.disk_usage(db.path.parent).free
    configured = configured_restore_limit()
    derived = restore_limit(free, size)
    return {
        "database_bytes": size,
        "free_bytes": free,
        "restore_limit_bytes": derived if configured is None else min(derived, configured),
        "restore_limit_configured_bytes": configured,
        "retention_days": retention_days(),
        "kept_runs_per_source": KEPT_RUNS_PER_SOURCE,
    }


def backup_too_large(size, status, needed=None):
    """The structured refusal of a backup that does not fit, with every size in its details."""
    needed = restore_room(size, status["database_bytes"]) if needed is None else needed
    configured = status["restore_limit_configured_bytes"]
    if needed <= status["free_bytes"] and configured is not None:
        message = (
            f"This backup is {size // MIB} MiB, above this installation's "
            f"OPENINGS_MAX_RESTORE_MB limit of {configured // MIB} MiB."
        )
    else:
        message = (
            f"This backup is {size // MIB} MiB. Restoring it needs {needed // MIB} MiB of free "
            f"space on the data volume, and {status['free_bytes'] // MIB} MiB are free."
        )
    return DomainError(
        413,
        "backup_size",
        message,
        {
            "size_bytes": size,
            "limit_bytes": status["restore_limit_bytes"],
            "free_bytes": status["free_bytes"],
            "needed_bytes": needed,
            "database_bytes": status["database_bytes"],
            "configured_limit_bytes": configured,
        },
    )


def preserve_provider_runtime(restored, current):
    """Keep recent request counts and active provider cooldowns across a restore."""
    result = {**restored, **current}
    result["events"] = sorted(
        {
            value
            for state in (restored, current)
            for value in state.get("events", [])
            if value > time.time() - 86400
        }
    )
    for key in ("next_allowed_at", "cooldown_until", "last_request_at"):
        result[key] = max(restored.get(key) or "", current.get(key) or "") or None
    for key in ("total_requests", "throttle_count"):
        result[key] = max(restored.get(key, 0), current.get(key, 0))
    if (restored.get("last_request_at") or "") > (current.get("last_request_at") or ""):
        for key in ("last_status", "last_error"):
            result[key] = restored.get(key)
    return result


def remove_installation_credentials(path):
    """Remove the owner password hash, the session secret and API tokens from a backup copy.

    A backup taken with an agent token must not carry what would grant owner
    access. Restore keeps the destination's own authentication, so the copy
    still restores completely.
    """
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("DELETE FROM settings WHERE key='auth'")
        conn.execute("DELETE FROM api_tokens")
        conn.execute("DELETE FROM transfer_grants")
        conn.commit()
        # The copy also holds the live database's free pages, where earlier versions
        # of these rows remain; rebuilding the file keeps only the live rows.
        conn.execute("VACUUM")


def restore_database(workspace, source_path):
    with closing(sqlite3.connect(source_path)) as source:
        version = source.execute("PRAGMA user_version").fetchone()[0]
    if version in CONVERSIONS:
        # Convert a copy of a backup of the previous schema; the uploaded file is only
        # read. The removed records go to an archive beside the database, as in an
        # upgrade at startup.
        upgraded = workspace.db.temp_file("upgrade")
        path = workspace.db.path
        archive = path.with_name(
            f"{path.stem}.pre-{m15.RELEASE}-archive-restored-{utc_stamp()}.json"
        )
        try:
            try:
                CONVERSIONS[version](source_path, upgraded, archive)
            except UpgradeError as error:
                raise DomainError(
                    422, "backup_integrity", "The backup could not be upgraded to this schema."
                ) from error
            result = _restore_current(workspace, upgraded)
        except BaseException:
            archive.unlink(missing_ok=True)
            raise
        finally:
            workspace.db.remove_temp(upgraded)
        compact(workspace.db)
        return result
    if version != SCHEMA_VERSION:
        error = schema_error(version)
        raise DomainError(422, "backup_version", error.message, error.details)
    return _restore_current(workspace, source_path)


def _restore_current(workspace, source_path):
    with sqlite3.connect(source_path) as source:
        if source.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise DomainError(
                422, "backup_version", "Select a database backup from this Openings schema."
            )
        if (
            source.execute("PRAGMA quick_check").fetchone()[0] != "ok"
            or source.execute("PRAGMA foreign_key_check").fetchall()
        ):
            raise DomainError(
                422, "backup_integrity", "The backup failed its database integrity check."
            )
        with workspace.db.connect() as live:
            tables = live.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'jobs_fts%' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for table in tables:
                name = table[0]
                expected = {r[1] for r in live.execute(f'PRAGMA table_info("{name}")')}
                actual = {r[1] for r in source.execute(f'PRAGMA table_info("{name}")')}
                if not expected.issubset(actual):
                    raise DomainError(
                        422, "backup_schema", "The backup does not match this workspace schema."
                    )
        # Both copies exist now; check the room the replacement itself still needs.
        status = storage_status(workspace.db)
        size = Path(source_path).stat().st_size
        needed = replace_room(size, status["database_bytes"])
        if status["free_bytes"] < needed:
            raise backup_too_large(size, status, needed)
        # Authentication belongs to the installation performing the restore.
        worker = getattr(workspace, "worker", None)
        if worker:
            worker.stop()
        rollback_name = workspace.db.temp_file("rollback")
        try:
            with workspace.db.lock:
                auth = workspace.db.one("SELECT * FROM settings WHERE key='auth'")
                tokens = workspace.db.all("SELECT * FROM api_tokens")
                providers = workspace.db.all("SELECT id,runtime FROM providers")
                workspace.db.backup(rollback_name)
                try:
                    with workspace.db.connect() as target:
                        source.backup(target)
                        target.execute("DELETE FROM transfer_grants")
                        target.execute("DELETE FROM api_tokens")
                        if auth:
                            target.execute(
                                "INSERT OR REPLACE INTO settings(key,data,version,updated_at) VALUES(?,?,?,?)",
                                (auth["key"], auth["data"], auth["version"], auth["updated_at"]),
                            )
                        target.executemany(
                            "INSERT INTO api_tokens(id,name,kind,token_hash,created_at,last_used_at) VALUES(?,?,?,?,?,?)",
                            [
                                (
                                    t["id"],
                                    t["name"],
                                    t["kind"],
                                    t["token_hash"],
                                    t["created_at"],
                                    t["last_used_at"],
                                )
                                for t in tokens
                            ],
                        )
                        for provider in providers:
                            restored = target.execute(
                                "SELECT runtime FROM providers WHERE id=?", (provider["id"],)
                            ).fetchone()
                            if restored:
                                runtime = preserve_provider_runtime(
                                    json.loads(restored[0]), json.loads(provider["runtime"])
                                )
                                target.execute(
                                    "UPDATE providers SET runtime=?,updated_at=? WHERE id=?",
                                    (encode(runtime), now(), provider["id"]),
                                )
                        target.execute(
                            "UPDATE tasks SET state='queued',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE state='running'",
                            (now(),),
                        )
                        target.commit()
                except BaseException:
                    with (
                        sqlite3.connect(rollback_name) as previous,
                        workspace.db.connect() as target,
                    ):
                        previous.backup(target)
                    raise
        finally:
            workspace.db.remove_temp(rollback_name)
            if worker:
                worker.start()
    return {
        "restored": True,
        "authentication_preserved": True,
        "message": "Workspace restored. Reload the dashboard.",
    }


def backup_file_for(workspace, actor):
    """A temporary consistent backup file; an agent's leaves out the installation credentials."""
    name = workspace.db.temp_file("backup")
    try:
        workspace.db.backup(name)
        if actor.is_agent:
            # An agent may back up before broad changes, but never receives the
            # password hash, the session secret or the tokens of the installation.
            remove_installation_credentials(name)
    except BaseException:
        workspace.db.remove_temp(name)
        raise
    return name


async def restore_upload(workspace, headers, chunks):
    """Receive a raw SQLite upload within the restore limit and restore it."""
    # Refuse before writing anything when the declared size cannot fit.
    status = storage_status(workspace.db)
    limit = status["restore_limit_bytes"]
    declared = headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise backup_too_large(int(declared), status)
    name = workspace.db.temp_file("restore")
    count = 0
    try:
        with open(name, "wb") as upload:  # noqa: ASYNC230 - local temp file, bounded chunks
            async for chunk in chunks:
                count += len(chunk)
                if count > limit:
                    raise backup_too_large(count, status)
                upload.write(chunk)
        with open(name, "rb") as check_file:  # noqa: ASYNC230 - 16-byte local read
            header = check_file.read(16)
        if header != b"SQLite format 3\x00":
            raise DomainError(422, "backup_format", "Select a SQLite database backup.")
        workspace.maintenance = True
        try:
            result = await asyncio.to_thread(restore_database, workspace, name)
            with workspace.db.transaction() as conn:
                events.record(conn, "workspace_restored", ("workspace", "backup"))
            # Other jobs now: build the duplicate index and missing signals again.
            workspace.reset_duplicates()
            workspace.warm_duplicates()
            return result
        except sqlite3.DatabaseError:
            raise DomainError(422, "backup_format", "This database backup could not be read.")
    finally:
        workspace.maintenance = False
        workspace.db.remove_temp(name)
