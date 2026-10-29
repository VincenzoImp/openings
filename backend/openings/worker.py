"""One bounded background worker with persisted claims and restart-safe leases."""

import logging
import threading
import time
from uuid import uuid4

from .common import now

LOG = logging.getLogger(__name__)


class Worker:
    def __init__(self, workspace, discovery=None):
        self.workspace = workspace
        self.discovery = discovery or workspace.discovery
        self.owner = None
        self.stopping = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive() and not self.stopping.is_set():
            return
        # An old request may still be finishing. Its event/owner are never reused.
        self.owner = uuid4().hex
        self.stopping = threading.Event()
        self.thread = threading.Thread(
            target=self._loop, args=(self.owner, self.stopping), name="openings-worker", daemon=True
        )
        self.thread.start()

    def stop(self, timeout=5):
        self.stopping.set()
        if self.owner is not None:
            self.workspace.db.execute(
                "UPDATE tasks SET state='queued',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE state='running' AND lease_owner=?",
                (now(), self.owner),
            )
        if self.thread:
            self.thread.join(timeout=timeout)

    def _run(self, task, owner, stopping):
        done = threading.Event()

        def heartbeat():
            while not done.wait(15) and not stopping.is_set():
                try:
                    if not self.discovery.heartbeat(task["id"], owner):
                        return
                except Exception:
                    LOG.warning(
                        "Task heartbeat failed; the lease will expire if recovery is needed."
                    )

        pulse = threading.Thread(target=heartbeat, name="openings-lease", daemon=True)
        pulse.start()
        try:
            if not stopping.is_set():
                self.discovery.run_task(task, owner)
        finally:
            done.set()
            pulse.join(timeout=1)

    def _loop(self, owner, stopping):
        scheduled = 0.0
        while not stopping.is_set():
            try:
                if time.monotonic() >= scheduled:
                    self.discovery.schedule_due(stopping)
                    scheduled = time.monotonic() + 15
                if stopping.is_set():
                    break
                task = self.discovery.claim_task(owner)
                if task:
                    self._run(task, owner, stopping)
                    continue
            except Exception:
                LOG.exception("The background worker could not complete this cycle.")
            stopping.wait(1)
