"""Consistent portable snapshots and validated in-place restore."""

import os
import sqlite3
import tempfile
from pathlib import Path

from .common import now
from .errors import DomainError


def restore_database(workspace, source_path):
    with sqlite3.connect(source_path) as source:
        if source.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise DomainError(422, "backup_version", "Select an Openings 1.0 database backup.")
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
