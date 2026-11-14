"""Workspace: settings, composed with the area services. Changes are recorded with ``events.record``."""

import json
import threading

from ..common import encode, now
from ..db import Database
from ..errors import conflict
from ..job_signals import SignalService
from .application_changes import ApplicationChanges
from .applications import ApplicationReads
from .batches import BatchOperations
from .bulk import BulkChanges
from .identity import JobIdentity
from .job_changes import JobChanges
from .jobs import JobReads
from .notes import Notes
from .replies import ReplyChanges
from .shortlist import Shortlist
from .timeline import Timeline


class Workspace(
    JobReads,
    JobChanges,
    JobIdentity,
    Notes,
    Timeline,
    ApplicationReads,
    ApplicationChanges,
    ReplyChanges,
    Shortlist,
    BulkChanges,
    BatchOperations,
):
    def __init__(self, path):
        self.db = Database(path)
        self.discovery = None
        # Duplicate features per job, reused until that job changes.
        self._duplicates = ({}, {}, None)
        self._duplicates_lock = threading.Lock()
        self.signals = SignalService(self)

    def get_settings(self, key, default=None):
        row = self.db.one("SELECT * FROM settings WHERE key=?", (key,))
        return (
            {"data": json.loads(row["data"]), "version": row["version"]}
            if row
            else {"data": default if default is not None else {}, "version": 0}
        )

    def set_settings(self, key, data, expected_version=None):
        with self.db.transaction() as c:
            row = c.execute("SELECT version FROM settings WHERE key=?", (key,)).fetchone()
            version = row["version"] if row else 0
            if expected_version is not None and expected_version != version:
                conflict(details={"current_version": version, "id": key})
            if row and self.get_settings(key)["data"] == data:
                return {"data": data, "version": version}
            c.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
                (key, encode(data), version + 1, now()),
            )
        return {"data": data, "version": version + 1}
