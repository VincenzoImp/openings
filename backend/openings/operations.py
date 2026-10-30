"""Consistent portable snapshots and validated in-place restore."""

import os
import json
import sqlite3
import tempfile
import time
from pathlib import Path

from .common import now, encode
from .errors import DomainError
from .db import SCHEMA_VERSION, migrate_workspace


def preserve_request_windows(restored, current):
    """Restoring an older archive cannot undo HTTP requests already sent by this installation."""
    result = {**restored, **current}
    result["events"] = sorted(
        {
            value
            for state in (restored, current)
            for value in state.get("events", [])
            if value > time.time() - 86400
        }
    )
    runs = dict(restored.get("runs", {}))
    for key, value in current.get("runs", {}).items():
        if key not in runs or value.get("count", 0) >= runs[key].get("count", 0):
            runs[key] = value
    result["runs"] = dict(sorted(runs.items(), key=lambda pair: pair[1].get("at", 0))[-200:])
    for key in ("next_allowed_at", "cooldown_until", "last_request_at"):
        result[key] = max(restored.get(key) or "", current.get(key) or "") or None
    for key in ("total_requests", "throttle_count"):
        result[key] = max(restored.get(key, 0), current.get(key, 0))
    if (restored.get("last_request_at") or "") > (current.get("last_request_at") or ""):
        for key in ("last_status", "last_error"):
            result[key] = restored.get(key)
    return result


def restore_database(workspace, source_path):
    # Never migrate the owner's backup in place, including service-level use.
    with sqlite3.connect(source_path) as uploaded:
        version = uploaded.execute("PRAGMA user_version").fetchone()[0]
        if version == 1:
            with tempfile.TemporaryDirectory(prefix="openings-upgrade-") as directory:
                upgraded = Path(directory) / "workspace.sqlite"
                with sqlite3.connect(upgraded) as target:
                    uploaded.backup(target)
                return _restore_database(workspace, upgraded)
    return _restore_database(workspace, source_path)


def _restore_database(workspace, source_path):
    with sqlite3.connect(source_path) as source:
        if source.execute("PRAGMA user_version").fetchone()[0] not in (1, SCHEMA_VERSION):
            raise DomainError(
                422, "backup_version", "Select a database backup from this Openings schema."
            )
        # The upload is a temporary copy: upgrading it never modifies the user's
        # original backup, and restore validates against the current schema.
        migrate_workspace(source)
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
        # Authentication belongs to the installation performing the restore.
        worker = getattr(workspace, "worker", None)
        if worker:
            worker.stop()
        rollback_handle, rollback_name = tempfile.mkstemp(
            prefix="openings-rollback-", suffix=".sqlite"
        )
        os.close(rollback_handle)
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
                            "INSERT INTO api_tokens(id,name,token_hash,created_at,last_used_at) VALUES(?,?,?,?,?)",
                            [
                                (
                                    t["id"],
                                    t["name"],
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
                                runtime = preserve_request_windows(
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
            Path(rollback_name).unlink(missing_ok=True)
            if worker:
                worker.start()
    return {
        "restored": True,
        "authentication_preserved": True,
        "message": "Workspace restored. Reload the dashboard.",
    }
