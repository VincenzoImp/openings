"""One SQLite queue with independent scheduler, collection and inference lanes."""

import logging
import threading
import time
from uuid import uuid4

from .common import now

LOG = logging.getLogger(__name__)
INFERENCE_LOCKS = {}
LOCKS_LOCK = threading.Lock()


class Worker:
    def __init__(self, workspace, discovery=None):
        self.workspace = workspace
        self.discovery = discovery or workspace.discovery
        self.owner = None
        self.stopping = threading.Event()
        self.thread = None
        self.threads = []
        with LOCKS_LOCK:
            self.inference_lock = INFERENCE_LOCKS.setdefault(
                str(workspace.db.path), threading.Lock()
            )

    def start(self):
        if self.thread and self.thread.is_alive() and not self.stopping.is_set():
            return
        # An old request may still be finishing. Its event/owner are never reused.
        self.owner = uuid4().hex
        self.stopping = threading.Event()
        self.thread = threading.Thread(
            target=self._schedule_loop,
            args=(self.stopping,),
            name="openings-scheduler",
            daemon=True,
        )
        self.threads = [self.thread] + [
            threading.Thread(
                target=self._loop,
                args=(self.owner, self.stopping, kind),
                name="openings-" + kind,
                daemon=True,
            )
            for kind in ("collect", "score")
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

    def _schedule_loop(self, stopping):
        while not stopping.is_set():
            try:
                self.discovery.schedule_due(stopping)
            except Exception:
                LOG.exception("The scheduler could not complete this cycle.")
            stopping.wait(15)

    def _loop(self, owner, stopping, kind):
        while not stopping.is_set():
            acquired = False
            try:
                # Acquire before claiming: waiting for a finishing old request
                # must not consume the successor's task lease after a restart.
                if kind == "score":
                    acquired = self.inference_lock.acquire(timeout=0.5)
                    if not acquired:
                        continue
                if stopping.is_set():
                    break
                task = self.discovery.claim_task(owner, kind)
                if task:
                    self._run(task, owner, stopping)
                    continue
            except Exception:
                LOG.exception("The background worker could not complete this cycle.")
            finally:
                if acquired:
                    self.inference_lock.release()
            stopping.wait(1)
