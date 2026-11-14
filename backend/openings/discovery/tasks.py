"""Collection tasks: listing, leases, cancellation, retry and running one collection."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from .. import events
from ..collectors.policy import ProviderDeferred
from ..common import decode_record, encode, missing, now
from ..errors import DomainError
from ..job_signals import unlist_missing
from ..posting import matches_filters, posting_complete, posting_complete_sql
from .feeds import fetch_postings, normalize_posting
from .network import HTTP_BUDGET

LOG = logging.getLogger(__name__)


class TaskOperations:
    """Persisted provider tasks of DiscoveryService and the collection they run."""

    def list_tasks(self, limit=50, offset=0, state=None, kind=None, source_id=None, job_id=None):
        limit, offset = min(max(limit, 1), 200), max(offset, 0)
        clauses, params = [], []
        for key, value in (
            ("state", state),
            ("kind", kind),
            ("source_id", source_id),
            ("job_id", job_id),
        ):
            if value is not None:
                if key == "state" and value not in (
                    "queued",
                    "running",
                    "succeeded",
                    "failed",
                    "cancelled",
                ):
                    raise DomainError(422, "task_state", "Use a supported task state.")
                if key == "kind" and value != "collect":
                    raise DomainError(422, "task_kind", "Use collect.")
                clauses.append("t." + key + "=?")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.all(
            "SELECT t.*,s.name AS source_name,j.title AS job_title FROM tasks t LEFT JOIN sources s ON s.id=t.source_id LEFT JOIN jobs j ON j.id=t.job_id"
            + where
            + " ORDER BY t.created_at DESC,t.id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": [self._task_record(row) for row in rows],
            "total": self.db.one("SELECT COUNT(*) AS n FROM tasks t" + where, params)["n"],
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    def _task_record(row, include_checkpoint=False):
        task = decode_record(row, ("payload", "result"))
        if not include_checkpoint:
            task["payload"] = {
                key: value
                for key, value in task["payload"].items()
                if key not in ("checkpoint", "observed_identities")
            }
        return task

    def get_task(self, task_id, *, include_checkpoint=False):
        row = self.db.one(
            "SELECT t.*,s.name AS source_name,j.title AS job_title FROM tasks t LEFT JOIN sources s ON s.id=t.source_id LEFT JOIN jobs j ON j.id=t.job_id WHERE t.id=?",
            (task_id,),
        )
        if row is None:
            missing("Task")
        return self._task_record(row, include_checkpoint)

    def cancel_task(self, task_id):
        task = self.get_task(task_id)
        with self.db.transaction() as connection:
            changed = connection.execute(
                "UPDATE tasks SET state='cancelled',error=NULL,lease_until=NULL,lease_owner=NULL,updated_at=? WHERE id=? AND state IN ('queued','running')",
                (now(), task_id),
            ).rowcount
            if changed:
                events.record(
                    connection,
                    "task_cancelled",
                    ("task", task_id),
                    {"source_id": task["source_id"], "run_id": task.get("run_id")},
                )
        return self.get_task(task_id)

    def retry_task(self, task_id):
        task = self.get_task(task_id, include_checkpoint=True)
        if task["state"] not in ("failed", "cancelled"):
            raise DomainError(409, "task_state", "Only a failed or cancelled task can be retried.")
        if task["source_id"] is None:
            raise DomainError(
                409, "source_removed", "Create a source before starting another collection."
            )
        payload = {**task["payload"], "manual": True}
        active = self.db.one(
            "SELECT id FROM tasks WHERE id<>? AND kind=? AND state IN ('queued','running') AND (job_id=? OR (source_id=? AND json_extract(payload,'$.provider')=?)) LIMIT 1",
            (task_id, task["kind"], task["job_id"], task["source_id"], payload.get("provider")),
        )
        if active:
            raise DomainError(409, "task_active", "Equivalent work is already queued or running.")
        with self.db.transaction() as connection:
            changed = connection.execute(
                "UPDATE tasks SET state='queued',payload=?,result=?,next_run_at=?,lease_until=NULL,lease_owner=NULL,error=NULL,updated_at=? WHERE id=? AND state IN ('failed','cancelled')",
                (
                    encode(payload),
                    encode({**task["result"], "failure_attempts": 0}),
                    now(),
                    now(),
                    task_id,
                ),
            ).rowcount
            if changed:
                events.record(
                    connection,
                    "task_retried",
                    ("task", task_id),
                    {"source_id": task["source_id"], "run_id": task.get("run_id")},
                )
        return self.get_task(task_id)

    def claim_task(self, owner, kind=None):
        stamp = now()
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE tasks SET state='queued',lease_until=NULL,lease_owner=NULL,updated_at=? WHERE state='running' AND lease_until<?",
                (stamp, stamp),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE state='queued' AND next_run_at<=?"
                + (" AND kind=?" if kind else "")
                + " ORDER BY next_run_at,created_at,id LIMIT 1",
                (stamp, kind) if kind else (stamp,),
            ).fetchone()
            if row is None:
                return None
            expiry = (datetime.now(UTC) + timedelta(seconds=90)).isoformat(timespec="microseconds")
            connection.execute(
                "UPDATE tasks SET state='running',attempts=attempts+1,lease_owner=?,lease_until=?,updated_at=? WHERE id=?",
                (owner, expiry, stamp, row["id"]),
            )
        return self.get_task(row["id"], include_checkpoint=True)

    def heartbeat(self, task_id, owner):
        expiry = (datetime.now(UTC) + timedelta(seconds=90)).isoformat(timespec="microseconds")
        return bool(
            self.db.execute(
                "UPDATE tasks SET lease_until=? WHERE id=? AND state='running' AND lease_owner=?",
                (expiry, task_id, owner),
            )
        )

    def _active(self, task_id, owner):
        return (
            self.db.one(
                "SELECT id FROM tasks WHERE id=? AND state='running' AND lease_owner=?",
                (task_id, owner),
            )
            is not None
        )

    def _collect(self, task, owner):
        current_source = self.db.one("SELECT id FROM sources WHERE id=?", (task["source_id"],))
        if current_source is None:
            return {"cancelled": True}
        run = self.db.one(
            "SELECT source_snapshot FROM collection_runs WHERE id=?", (task["run_id"],)
        )
        if run is None:
            raise DomainError(409, "collection_run", "The collection invocation is missing.")
        source = json.loads(run["source_snapshot"])
        provider = task["payload"]["provider"]
        source["provider"] = provider
        prefix = (
            provider + ":"
            if source["kind"] == "jobspy"
            else f"{source['kind']}:{source['config'].get('board', '')}:"
        )
        known_rows = self.db.all(
            "SELECT i.identity,j.metadata,j.posting,d.checked_at,"
            + posting_complete_sql()
            + " AS complete "
            "FROM job_identities i JOIN jobs j ON j.id=i.job_id "
            "LEFT JOIN posting_details d ON d.identity=i.identity AND d.job_id=j.id "
            "WHERE i.identity>=? AND i.identity<?",
            (prefix, prefix + "\uffff"),
        )
        source["known"] = {
            row["identity"]: json.loads(row["metadata"]) for row in known_rows if row["complete"]
        }
        source["known_postings"] = {
            row["identity"]: row["posting"] for row in known_rows if row["complete"]
        }
        source["detail_checked"] = {
            row["identity"]: row["checked_at"] for row in known_rows if row["checked_at"]
        }
        source["checkpoint"] = dict(task["payload"].get("checkpoint") or {})
        budget = self.http_budget(
            provider,
            active=lambda: self._active(task["id"], owner),
        )
        task["budget"] = budget
        result = dict(task["result"])
        for key in ("received", "created", "existing", "invalid"):
            result.setdefault(key, 0)
        result.setdefault("started_at", now())
        task["partial_result"] = result
        observed = set(task["payload"].get("observed_identities") or [])

        def persist():
            self.db.execute(
                "UPDATE tasks SET payload=?,result=?,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
                (encode(task["payload"]), encode(result), now(), task["id"], owner),
            )

        def checkpoint(value):
            if not self._active(task["id"], owner):
                raise DomainError(409, "task_cancelled", "Collection was cancelled.")
            source["checkpoint"] = value
            task["payload"]["checkpoint"] = value
            for key, target in (
                ("pending_details", "pending_descriptions"),
                ("unavailable_descriptions", "unavailable_descriptions"),
            ):
                count = value.get(key, 0)
                result[target] = len(count) if isinstance(count, (list, dict)) else int(count or 0)
            persist()

        def store(posting):
            created = store_locked(posting)
            if created:
                # The duplicate signal, outside the lock (see ingest_job).
                try:
                    self.workspace.signals.after_ingest(created)
                except Exception:  # a signal never fails the collection
                    LOG.exception("Ingest signals failed for a collected job.")

        def store_locked(posting):
            if not matches_filters(posting, source["config"].get("filters") or {}):
                return None
            created = None
            with self.db.lock:
                if not self._active(task["id"], owner):
                    raise DomainError(409, "task_cancelled", "Collection was cancelled.")
                posting = normalize_posting({**posting, "source_id": source["id"]})
                if not posting_complete(posting.get("posting"), posting.get("metadata"), {}):
                    # Incomplete candidates remain in the adapter checkpoint, outside the archive.
                    return None
                identity = (
                    posting.get("source_key")
                    or posting.get("url")
                    or hashlib.sha256(encode(posting).encode()).hexdigest()
                )
                first_observation = identity not in observed
                try:
                    saved = self.workspace.ingest_job(posting, defer_signals=True)
                except (ValidationError, DomainError) as error:
                    if (
                        isinstance(error, DomainError)
                        and error.status != 422
                        and error.code != "identity_conflict"
                    ):
                        raise
                    if first_observation:
                        result["received"] += 1
                        result["invalid"] += 1
                        observed.add(identity)
                    if isinstance(error, DomainError) and error.code == "identity_conflict":
                        result["conflict_count"] = result.get("conflict_count", 0) + 1
                        conflicts = result.setdefault("identity_conflicts", [])
                        if len(conflicts) < 20:
                            conflicts.append(
                                {"source_key": posting.get("source_key"), **error.details}
                            )
                else:
                    checked_at = (source.get("detail_checks") or {}).get(posting.get("source_key"))
                    if checked_at:
                        self.db.execute(
                            "INSERT INTO posting_details(identity,job_id,checked_at) VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET job_id=excluded.job_id,checked_at=excluded.checked_at",
                            (posting["source_key"], saved["id"], checked_at),
                        )
                    if first_observation:
                        result["received"] += 1
                        result["created"] += int(bool(saved.get("created")))
                        result["existing"] += int(not saved.get("created", False))
                        observed.add(identity)
                    if saved.get("created"):
                        created = saved["id"]
                task["payload"]["observed_identities"] = sorted(observed)
                persist()
            return created

        source["on_item"] = store
        source["on_checkpoint"] = checkpoint
        if not self._active(task["id"], owner):
            return {"cancelled": True}
        self.db.execute(
            "UPDATE sources SET last_run_at=?,last_error=NULL WHERE id=?",
            (result["started_at"], source["id"]),
        )
        token = HTTP_BUDGET.set(budget)
        try:
            postings = fetch_postings(source)
        finally:
            HTTP_BUDGET.reset(token)
        if len(postings) > 2000:
            raise DomainError(
                422,
                "collection_limit",
                "This feed has more than 2000 matching postings. Narrow the source filters.",
            )
        if not source.get("streamed"):
            result["unavailable_descriptions"] = sum(
                not posting_complete(posting.get("posting"), posting.get("metadata"), {})
                for posting in postings
                if matches_filters(posting, source["config"].get("filters") or {})
            )
            for posting in postings:
                store(posting)
        diagnostic = source.get("diagnostic") or budget.diagnostics()
        for key, message in (
            (
                "candidate_capped",
                "Only a bounded part of this board was inspected; additional matching jobs may exist.",
            ),
            (
                "result_capped",
                "More jobs match than this source's result limit. Increase the result limit or narrow its filters.",
            ),
        ):
            if source.get(key):
                result[key] = True
                diagnostic.setdefault("warnings", []).append(message)
        result["diagnostics"] = [diagnostic]
        if budget.blocked:
            raise budget.blocked
        if source.get("collection_error"):
            raise source["collection_error"]
        if result.get("identity_conflicts"):
            raise DomainError(
                409,
                "identity_conflict",
                "Some postings have conflicting archived identities. Other results were retained; merge the verified duplicates before retrying.",
            )
        if source["checkpoint"].get("complete") is False:
            result["continuing"] = True
        else:
            result.pop("continuing", None)
            if not source.get("candidate_capped") and not source.get("result_capped"):
                # The whole board was read: what it no longer lists is gone.
                with self.db.transaction() as connection:
                    unlisted = unlist_missing(connection, source, result["started_at"], now())
                if unlisted:
                    result["unlisted"] = result.get("unlisted", 0) + len(unlisted)
        return result

    def run_task(self, task, owner):
        if not self._active(task["id"], owner):
            return
        started = time.monotonic()
        result = task.get("result", {})
        state, message, next_run = "failed", None, now()
        error_code = None
        try:
            result = self._collect(task, owner)
            state = (
                "cancelled"
                if result.get("skipped") or result.get("cancelled") or result.get("discarded")
                else "queued"
                if result.pop("continuing", False)
                else "succeeded"
            )
            if state == "queued":
                next_run = (datetime.now(UTC) + timedelta(seconds=1)).isoformat(
                    timespec="microseconds"
                )
        except Exception as error:  # noqa: BLE001 - task boundary records any failure
            message = (
                error.message
                if isinstance(error, DomainError)
                else "The background task failed. Review the settings and retry."
            )
            error_code = getattr(error, "code", type(error).__name__)
            deferred = isinstance(error, ProviderDeferred)
            retryable = not isinstance(error, DomainError) or error.status >= 500
            # Quota waits do not consume the transient error retry allowance.
            failures = task.get("result", {}).get("failure_attempts", 0) + int(not deferred)
            retry = deferred or (retryable and failures < 3)
            state = "queued" if retry else "failed"
            delay = min(3600, 15 * 4 ** min(max(failures - 1, 0), 8))
            if deferred and error.code == "collection_batch":
                delay = 1
            next_run = getattr(error, "next_run_at", None) or (
                datetime.now(UTC) + timedelta(seconds=delay)
            ).isoformat(timespec="microseconds")
            result = task.get("partial_result", dict(task.get("result", {})))
            result["failure_attempts"] = failures
            if task.get("budget"):
                result["diagnostics"] = [task["budget"].diagnostics()]
            LOG.warning("Background task %s paused or failed (%s).", task["id"], error_code)
        if task["kind"] == "collect":
            result["processing_seconds"] = round(
                result.get("processing_seconds", 0) + time.monotonic() - started, 3
            )
            result["http_requests"] = result.get("http_requests", 0) + (
                task["budget"].requests if task.get("budget") else 0
            )
            history = result.setdefault("attempt_history", [])
            history.append(
                {
                    "attempt": task["attempts"],
                    "finished_at": now(),
                    "state": state,
                    "reason": error_code,
                    "requests": task["budget"].requests if task.get("budget") else 0,
                }
            )
            result["attempt_history"] = history[-50:]
        with self.db.transaction() as connection:
            changed = connection.execute(
                "UPDATE tasks SET state=?,result=?,error=?,next_run_at=?,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
                (
                    state,
                    encode(result),
                    message[:1000] if message else None,
                    next_run,
                    now(),
                    task["id"],
                    owner,
                ),
            )
            if changed.rowcount and task["source_id"]:
                connection.execute(
                    "UPDATE sources SET last_error=? WHERE id=?",
                    (message[:1000] if state == "failed" and message else None, task["source_id"]),
                )
