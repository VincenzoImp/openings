"""Scheduled local copies of the workspace, and the owner's access to every kept copy.

The worker calls ``run_if_due`` on each cycle. When the newest scheduled backup
is 24 hours old (or there is none), ``run_backup`` writes
``openings-<UTC timestamp>.sqlite`` into ``OPENINGS_BACKUP_DIR`` (default
``<data dir>/backups``, created 0700) through ``VACUUM INTO`` a temporary name,
``quick_check``, mode 0600, an atomic rename and fsync, then keeps the newest
``OPENINGS_BACKUP_KEEP`` (default 3; ``0`` disables scheduled backups). Without
1.2 times the database size free on that volume the run is skipped with a
warning. The time, outcome and error of the last attempt are stored in the
``backup`` setting; after a failed or skipped attempt the next one waits
``RETRY_HOURS``.

The copies an upgrade keeps beside the workspace (``<name>.pre-*.sqlite``) are
listed here too: the owner can download them and delete one deliberately.
Every copy holds the whole workspace, including the password hash, the session
secret and token hashes, so only the owner reaches them (REST, never MCP).
"""

import json
import logging
import math
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

from . import compaction
from .db import Database, file_bytes, utc_stamp, write_verified_copy
from .errors import DomainError

LOG = logging.getLogger(__name__)
SETTING = "backup"
DEFAULT_KEEP = 3
INTERVAL_HOURS = 24
RETRY_HOURS = 1
ROOM_FACTOR = 1.2
NAME = re.compile(r"openings-(\d{8}T\d{6}Z)\.sqlite")
STAMP = "%Y%m%dT%H%M%SZ"
# One backup at a time per process: the worker's, or a test's.
LOCK = threading.Lock()


def backup_dir(db):
    """Where scheduled backups go: ``OPENINGS_BACKUP_DIR`` or ``<data dir>/backups``."""
    value = (os.environ.get("OPENINGS_BACKUP_DIR") or "").strip()
    return Path(value).expanduser().resolve() if value else db.path.parent / "backups"


def backup_keep():
    """``OPENINGS_BACKUP_KEEP``: scheduled backups kept; ``0`` disables them."""
    value = (os.environ.get("OPENINGS_BACKUP_KEEP") or "").strip()
    if not value:
        return DEFAULT_KEEP
    try:
        return max(0, int(value))
    except ValueError:
        LOG.warning("OPENINGS_BACKUP_KEEP=%r is not a number; keeping %d.", value, DEFAULT_KEEP)
        return DEFAULT_KEEP


def stamp_time(stamp):
    return datetime.strptime(stamp, STAMP).replace(tzinfo=UTC)


def iso(moment):
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def scheduled(directory):
    """Scheduled backups in ``directory``, newest first, as (time, path)."""
    try:
        entries = list(Path(directory).iterdir())
    except FileNotFoundError:
        return []
    found = [
        (stamp_time(match.group(1)), item)
        for item in entries
        if (match := NAME.fullmatch(item.name)) and item.is_file()
    ]
    return sorted(found, key=lambda pair: pair[0], reverse=True)


def pre_upgrade(db):
    """Copies kept beside the workspace before an upgrade, newest first, as (time, path)."""
    prefix = db.path.stem + ".pre-"
    found = []
    for item in db.path.parent.iterdir():
        if item.name.startswith(prefix) and item.name.endswith(".sqlite") and item.is_file():
            match = re.search(r"-(\d{8}T\d{6}Z)\.sqlite$", item.name)
            moment = (
                stamp_time(match.group(1))
                if match
                else datetime.fromtimestamp(item.stat().st_mtime, UTC)
            )
            found.append((moment, item))
    return sorted(found, key=lambda pair: pair[0], reverse=True)


def run_backup(db, directory, keep):
    """Write one verified backup into ``directory`` and keep the newest ``keep``.

    Returns the backup's name and size, or None when the volume lacks room (a
    warning is logged). Errors of the copy itself are raised.
    """
    directory = Path(directory)
    with LOCK:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        # A copy left by an interrupted run is never a backup.
        for stale in directory.glob(".openings-temp-*"):
            Database.remove_temp(stale)
        size = file_bytes(db.path)
        needed = math.ceil(ROOM_FACTOR * size)
        room, free = compaction.has_room(directory, needed)
        if not room:
            LOG.warning(
                "Scheduled backup skipped: it needs %d MiB free in %s and %d MiB are free.",
                math.ceil(needed / 1024**2),
                directory,
                free // 1024**2,
            )
            return None
        target = directory / f"openings-{utc_stamp()}.sqlite"
        temp = directory / f".openings-temp-backup-{os.getpid()}-{threading.get_ident()}.sqlite"
        Database.remove_temp(temp)
        with db.connect() as conn:
            write_verified_copy(conn, temp, target)
        for _, old in scheduled(directory)[max(1, keep) :]:
            old.unlink(missing_ok=True)
        compaction.fsync_directory(directory)
        LOG.info("Scheduled backup written to %s.", target)
        return {"name": target.name, "size_bytes": target.stat().st_size}


def record(db, data):
    """Store the last attempt in the ``backup`` setting (JSON, no schema change)."""
    stamp = data["attempted_at"]
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,1,?) "
            "ON CONFLICT(key) DO UPDATE SET data=excluded.data,"
            "version=settings.version+1,updated_at=excluded.updated_at",
            (SETTING, json.dumps(data, sort_keys=True), stamp),
        )


def last_attempt(db):
    row = db.one("SELECT data FROM settings WHERE key=?", (SETTING,))
    return json.loads(row["data"]) if row else None


def due(db, moment=None):
    """Whether a scheduled backup should run now."""
    keep = backup_keep()
    if keep == 0:
        return False
    moment = moment or datetime.now(UTC)
    last = last_attempt(db)
    if last and last.get("outcome") != "ok":
        tried = datetime.fromisoformat(last["attempted_at"])
        if (moment - tried).total_seconds() < RETRY_HOURS * 3600:
            return False
    newest = scheduled(backup_dir(db))
    return not newest or (moment - newest[0][0]).total_seconds() >= INTERVAL_HOURS * 3600


def run_if_due(db, moment=None):
    """Run a scheduled backup when one is due and record the attempt; never raises.

    Returns the recorded attempt, or None when nothing was due.
    """
    try:
        if not due(db, moment):
            return None
    except OSError as error:
        LOG.warning("Scheduled backups could not be listed: %s", error)
        return None
    attempt = {"attempted_at": iso(moment or datetime.now(UTC)), "name": None, "error": None}
    try:
        result = run_backup(db, backup_dir(db), backup_keep())
        if result is None:
            attempt.update(outcome="skipped", error="Not enough free space for a backup.")
        else:
            attempt.update(outcome="ok", name=result["name"])
    except Exception as error:
        LOG.exception("Scheduled backup failed.")
        attempt.update(outcome="failed", error=str(error) or type(error).__name__)
    try:
        record(db, attempt)
    except Exception:
        LOG.exception("The scheduled backup attempt could not be recorded.")
    return attempt


def status(db, moment=None):
    """The newest scheduled backup, its age and the last attempt, for /health and Settings."""
    moment = moment or datetime.now(UTC)
    keep = backup_keep()
    try:
        newest = scheduled(backup_dir(db))
    except OSError:
        newest = []
    last = last_attempt(db)
    age = (moment - newest[0][0]).total_seconds() / 3600 if newest else None
    return {
        "enabled": keep > 0,
        "keep": keep,
        "last_at": iso(newest[0][0]) if newest else None,
        "age_hours": round(age, 2) if age is not None else None,
        # A recent backup exists and the last attempt did not fail or skip.
        "ok": bool(
            keep
            and newest
            and age < INTERVAL_HOURS * 2
            and (last is None or last.get("outcome") == "ok")
        ),
        "last_attempt": last,
    }


def listing(db):
    """Every kept copy: scheduled backups and pre-upgrade copies, newest first."""
    items = []
    for kind, entries in (
        ("scheduled", scheduled(backup_dir(db))),
        ("pre_upgrade", pre_upgrade(db)),
    ):
        for moment, path in entries:
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                continue  # rotated while listing
            items.append(
                {"name": path.name, "kind": kind, "size_bytes": size, "created_at": iso(moment)}
            )
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


def find(db, name):
    """The kept copy named exactly ``name`` in the listing, or 404."""
    for kind, entries in (
        ("scheduled", scheduled(backup_dir(db))),
        ("pre_upgrade", pre_upgrade(db)),
    ):
        for _, path in entries:
            if path.name == name:
                return kind, path
    raise DomainError(404, "not_found", "Backup not found.")


def delete_pre_upgrade(db, name):
    """Delete a pre-upgrade copy deliberately; scheduled backups rotate by themselves."""
    kind, path = find(db, name)
    if kind != "pre_upgrade":
        raise DomainError(
            409,
            "backup_scheduled",
            "Scheduled backups are rotated automatically; only pre-upgrade copies are deleted by hand.",
        )
    path.unlink(missing_ok=True)
    compaction.fsync_directory(path.parent)
    return {"deleted": True, "name": name}
