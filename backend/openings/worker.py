"""One SQLite queue with independent scheduler and collection lanes."""

import logging
import threading
import time
from contextvars import Context
from uuid import uuid4

from . import backups
from .common import now
from .retention import prune

LOG = logging.getLogger(__name__)


class Worker:
    heartbeat_seconds = 15  # lease renewals; a lease lasts 90 seconds
    prune_seconds = 6 * 3600  # old finished runs and tasks: once at start, then at this pace
    prune_backlog_seconds = 60  # while a bounded pass still left old records behind
    # /health reports the worker stalled when its scheduler has not cycled for this long.
    stall_seconds = 900

    def __init__(self, workspace, discovery=None):
        self.workspace = workspace
        self.discovery = discovery or workspace.discovery
        self.owner = None
        self.stopping = threading.Event()
        self.thread = None
        self.threads = []
        self.beat = None  # time.monotonic() of the scheduler's latest cycle

    def start(self):
        if self.thread and self.thread.is_alive() and not self.stopping.is_set():
            return
        # An old request may still be finishing. Its event/owner are never reused.
        self.owner = uuid4().hex
        self.stopping = threading.Event()
        self.beat = time.monotonic()
        self.thread = threading.Thread(
            target=self._schedule_loop,
            args=(self.stopping,),
            name="openings-scheduler",
            daemon=True,
            # Worker threads never inherit the actor of the request that (re)starts them.
            context=Context(),
        )
        self.threads = [self.thread] + [
            threading.Thread(
                target=self._loop,
                args=(self.owner, self.stopping, kind),
                name="openings-" + kind,
                daemon=True,
                context=Context(),
            )
            for kind in ("collect",)
        ]
        for thread in self.threads:
            thread.start()

    def stop(self, timeout=5):
        self.stopping.set()
        if self.owner is not None:
            self.workspace.db.execute(
                "UPDATE tasks SET state='queued',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE state='running' AND lease_owner=?",
                (now(), self.owner),
            )
        deadline = time.monotonic() + timeout
        for thread in self.threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))

    def heartbeat_age(self):
        """Seconds since the scheduler's latest cycle, or None before it started."""
        return None if self.beat is None else max(0.0, time.monotonic() - self.beat)

    def stalled(self):
        """Whether the started scheduler stopped cycling: its thread died or hangs."""
        age = self.heartbeat_age()
        if age is None or self.stopping.is_set():
            return False
        return age >= self.stall_seconds or not (self.thread and self.thread.is_alive())

    def _run(self, task, owner, stopping):
        done = threading.Event()

        def heartbeat():
            while not done.wait(self.heartbeat_seconds) and not stopping.is_set():
                try:
                    if not self.discovery.heartbeat(task["id"], owner):
                        return
                except Exception:  # noqa: BLE001 - the heartbeat thread must survive
                    LOG.warning(
                        "Task heartbeat failed; the lease will expire if recovery is needed."
                    )

        pulse = threading.Thread(
            target=heartbeat, name="openings-lease", daemon=True, context=Context()
        )
        pulse.start()
        try:
            if not stopping.is_set():
                self.discovery.run_task(task, owner)
        finally:
            done.set()
            pulse.join(timeout=1)

    def _schedule_loop(self, stopping):
        next_prune = time.monotonic()
        while not stopping.is_set():
            self.beat = time.monotonic()
            try:
                self.discovery.schedule_due(stopping)
            except Exception:
                LOG.exception("The scheduler could not complete this cycle.")
            if (
                self.workspace is not None
                and time.monotonic() >= next_prune
                and not stopping.is_set()
            ):
                wait = self.prune_seconds
                try:
                    if prune(self.workspace.db)["more"]:
                        wait = self.prune_backlog_seconds
                except Exception:
                    LOG.exception("Old collection runs and tasks could not be pruned.")
                next_prune = time.monotonic() + wait
            if self.workspace is not None and not stopping.is_set():
                # Checked on every cycle; a failure is recorded, never raised.
                backups.run_if_due(self.workspace.db)
            self.beat = time.monotonic()
            stopping.wait(15)

    def _loop(self, owner, stopping, kind):
        while not stopping.is_set():
            try:
                if stopping.is_set():
                    break
                task = self.discovery.claim_task(owner, kind)
                if task:
                    self._run(task, owner, stopping)
                    continue
            except Exception:
                LOG.exception("The background worker could not complete this cycle.")
            stopping.wait(1)
