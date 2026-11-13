"""Workspace: settings and the attributed change log, composed with the area services."""

import json
import threading

from ..actors import current_actor, pop_actor
from ..common import new_id, now
from ..db import Database, decode_record, encode
from ..errors import conflict
from ..job_signals import SignalService
from .application_changes import ApplicationChanges
from .applications import ApplicationReads
from .bulk import BulkChanges
from .identity import JobIdentity
from .job_changes import JobChanges
from .jobs import JobReads
from .notes import Notes
from .overview import Overview
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
    Overview,
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
                conflict(details={"current_version": version})
            if row and self.get_settings(key)["data"] == data:
                return {"data": data, "version": version}
            c.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
                (key, encode(data), version + 1, now()),
            )
        return {"data": data, "version": version + 1}

    def event(
        self,
        kind,
        job_id=None,
        application_id=None,
        payload=None,
        conn=None,
        *,
        subject=None,
        actor=None,
    ):
        """Record one change with its actor and, for a token with an open run, that run.

        ``subject`` is ``(type, id)`` of the changed record; it defaults to the
        application or job. Payloads hold identifiers, field names and versions,
        never record content.
        """
        if conn is None:
            with self.db.transaction() as connection:
                return self.event(
                    kind, job_id, application_id, payload, connection, subject=subject, actor=actor
                )
        actor = actor or current_actor()
        stamp, run_id = now(), self.open_run_id(conn, actor)
        if run_id:
            conn.execute("UPDATE runs SET last_activity_at=? WHERE id=?", (stamp, run_id))
        if subject is None:
            subject = (
                ("application", application_id)
                if application_id
                else ("job", job_id)
                if job_id
                else (None, None)
            )
        conn.execute(
            "INSERT INTO events(id,job_id,application_id,kind,payload,created_at,subject_type,subject_id,actor_kind,actor_id,actor_name,actor_token_kind,run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                job_id,
                application_id,
                kind,
                encode(payload or {}),
                stamp,
                *subject,
                *actor.columns(),
                run_id,
            ),
        )
        return None

    @staticmethod
    def open_run_id(conn, actor):
        """The open run of a token actor; the owner session and the system have none."""
        if actor.kind != "token":
            return None
        run = conn.execute(
            "SELECT id FROM runs WHERE token_id=? AND status='open'", (actor.id,)
        ).fetchone()
        return run["id"] if run else None

    @staticmethod
    def event_record(row):
        """An event as returned by history reads: decoded payload, subject and actor."""
        item = decode_record(row, ("payload",))
        kind = item.pop("subject_type", None)
        identifier = item.pop("subject_id", None)
        if kind is None:
            # Events from before schema 8 belong to their application or job.
            kind, identifier = (
                ("application", item.get("application_id"))
                if item.get("application_id")
                else ("job", item.get("job_id"))
                if item.get("job_id")
                else (None, None)
            )
        item["subject"] = {"type": kind, "id": identifier}
        item["actor"] = pop_actor(item)
        return item
