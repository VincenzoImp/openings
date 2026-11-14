"""Collection runs: the global switch, provider policies, queueing, scheduling and run records."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from .. import events
from ..collectors import jobspy as jobspy_collector
from ..collectors.policy import ProviderPatch
from ..common import check_version, decode_record, encode, missing, new_id, now
from ..errors import DomainError, conflict
from ..scheduling import next_due
from .models import RunOverrides
from .resolution import require_automatic_collection


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class RunOperations:
    """Collection settings, provider policies and logical runs of DiscoveryService."""

    def get_collection(self):
        stored = self.workspace.get_settings("collection", {"enabled": True})
        enabled = bool((stored["data"] or {}).get("enabled", True))
        counts = self.db.one(
            "SELECT COUNT(*) AS source_count,COALESCE(SUM(enabled),0) AS enabled_sources FROM sources"
        )
        tasks = self.db.one(
            "SELECT SUM(state='queued') AS queued_tasks,SUM(state='running') AS running_tasks,MIN(CASE WHEN state='queued' THEN next_run_at END) AS next_run_at FROM tasks WHERE kind='collect'"
        )
        upcoming = [tasks["next_run_at"]] if tasks["next_run_at"] else []
        if enabled:
            upcoming.extend(
                next_due(
                    json.loads(row["schedule"]), row["last_scheduled_at"] or row["created_at"]
                ).isoformat(timespec="microseconds")
                for row in self.db.all(
                    "SELECT schedule,last_scheduled_at,created_at FROM sources WHERE enabled=1 AND NOT EXISTS(SELECT 1 FROM tasks WHERE source_id=sources.id AND kind='collect' AND state IN ('queued','running'))"
                )
            )
        return {
            "enabled": enabled,
            "version": stored["version"],
            **counts,
            "queued_tasks": tasks["queued_tasks"] or 0,
            "running_tasks": tasks["running_tasks"] or 0,
            "next_run_at": min(upcoming) if upcoming else None,
        }

    def set_collection_switch(self, expected_version, enabled):
        """Check the collection's version and, when ``enabled`` is given, turn it on or off."""
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM settings WHERE key='collection'").fetchone()
            current = row["version"] if row else 0
            if current != expected_version:
                conflict(
                    "Collection settings changed. Reload before saving.",
                    details={"current_version": current, "id": "collection"},
                )
            if enabled is None:
                return
            stamp = now()
            connection.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES('collection',?,1,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=settings.version+1,updated_at=excluded.updated_at",
                (encode({"enabled": enabled}), stamp),
            )
            events.record(
                connection,
                "collection_updated",
                ("collection", "collection"),
                {"enabled": enabled, "version": current + 1},
            )

    def list_providers(self):
        return self.providers.list()

    def update_provider(self, provider_id, value: ProviderPatch):
        result = self.providers.update(provider_id, value)
        with self.db.transaction() as connection:
            events.record(
                connection,
                "provider_updated",
                ("provider", provider_id),
                {
                    "fields": sorted(
                        value.model_dump(exclude_unset=True, exclude={"expected_version"})
                    ),
                    "version": result["version"],
                },
            )
        if result["policy"]["enabled"]:
            # Policy changes may make a previously deferred queued request eligible.
            self.db.execute(
                "UPDATE tasks SET next_run_at=?,updated_at=? WHERE kind='collect' AND state='queued' AND json_extract(payload,'$.provider')=? AND error LIKE '%provider paused%'",
                (now(), now(), provider_id),
            )
        return result

    @staticmethod
    def _run_summary(record):
        """Drop the frozen source snapshot and task payload/result bodies from a run record."""
        summary = {key: value for key, value in record.items() if key != "source_snapshot"}
        summary["tasks"] = [
            {
                "id": task["id"],
                "kind": task["kind"],
                "provider": task["payload"].get("provider"),
                "state": task["state"],
                "attempts": task["attempts"],
                "error": task["error"],
                "next_run_at": task["next_run_at"],
                "updated_at": task["updated_at"],
            }
            for task in record["tasks"]
        ]
        return summary

    def _run_record(self, row, tasks):
        record = decode_record(row, ("source_snapshot", "overrides"))
        record.pop("position", None)
        decoded = [decode_record(task, ("payload", "result")) for task in tasks]
        states = {task["state"] for task in decoded}
        record["state"] = next(
            (
                state
                for state in ("running", "queued", "failed", "cancelled", "succeeded")
                if state in states
            ),
            "cancelled",
        )
        record["counts"] = {
            key: sum(task["result"].get(key, 0) for task in decoded)
            for key in (
                "received",
                "created",
                "existing",
                "invalid",
                "pending_descriptions",
                "unavailable_descriptions",
            )
        }
        record["task_ids"] = [task["id"] for task in decoded]
        record["started_at"] = min(
            (task["result"]["started_at"] for task in decoded if task["result"].get("started_at")),
            default=None,
        )
        record["finished_at"] = (
            max((task["updated_at"] for task in decoded), default=None)
            if not states.intersection(("queued", "running"))
            else None
        )
        ending = parse_time(record["finished_at"]) or datetime.now(UTC)
        record["total_seconds"] = max(
            0, round((ending - parse_time(record["created_at"])).total_seconds(), 3)
        )
        record["processing_seconds"] = round(
            sum(task["result"].get("processing_seconds", 0) for task in decoded), 3
        )
        record["waiting_seconds"] = max(
            0, round(record["total_seconds"] - record["processing_seconds"], 3)
        )
        record["http_requests"] = sum(task["result"].get("http_requests", 0) for task in decoded)
        record["next_run_at"] = min(
            (task["next_run_at"] for task in decoded if task["state"] == "queued"), default=None
        )
        record["partial"] = any(
            task["result"].get("candidate_capped")
            or task["result"].get("result_capped")
            or task["result"].get("unavailable_descriptions")
            for task in decoded
        )
        record["tasks"] = [
            {key: value for key, value in task.items() if key not in ("lease_owner", "lease_until")}
            for task in decoded
        ]
        for task in record["tasks"]:
            task["payload"] = {
                key: value
                for key, value in task["payload"].items()
                if key not in ("checkpoint", "observed_identities")
            }
        return record

    def list_runs(self, limit=50, offset=0, source_id=None, state=None, summary=True):
        """List collection runs; summary=true omits frozen source snapshots and task payload/result bodies."""
        if state not in (None, "queued", "running", "succeeded", "failed", "cancelled"):
            raise DomainError(422, "run_state", "Use a supported collection run state.")
        states_sql = (
            "CASE "
            + " ".join(
                "WHEN EXISTS(SELECT 1 FROM tasks t WHERE t.run_id=r.id AND t.state='"
                + item
                + "') THEN '"
                + item
                + "'"
                for item in ("running", "queued", "failed", "cancelled", "succeeded")
            )
            + " ELSE 'cancelled' END"
        )
        clauses, params = [], []
        if source_id:
            clauses.append("source_id=?")
            params.append(source_id)
        if state:
            clauses.append("state=?")
            params.append(state)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        query = "SELECT r.*," + states_sql + " AS state FROM collection_runs r"
        limit, offset = min(max(limit, 1), 200), max(offset, 0)
        rows = self.db.all(
            "SELECT * FROM ("
            + query
            + ")"
            + where
            + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        ids = [row["id"] for row in rows]
        tasks = (
            self.db.all(
                "SELECT * FROM tasks WHERE run_id IN ("
                + ",".join("?" for _ in ids)
                + ") ORDER BY created_at,id",
                ids,
            )
            if ids
            else []
        )
        grouped = {run_id: [] for run_id in ids}
        for task in tasks:
            grouped[task["run_id"]].append(task)
        records = [self._run_record(row, grouped[row["id"]]) for row in rows]
        return {
            "items": [self._run_summary(record) for record in records] if summary else records,
            "total": self.db.one("SELECT COUNT(*) AS n FROM (" + query + ")" + where, params)["n"],
            "limit": limit,
            "offset": offset,
        }

    def get_run(self, run_id):
        row = self.db.one("SELECT * FROM collection_runs WHERE id=?", (run_id,))
        if row is None:
            missing("Collection run")
        return self._run_record(
            row, self.db.all("SELECT * FROM tasks WHERE run_id=? ORDER BY created_at,id", (run_id,))
        )

    def cancel_run(self, run_id):
        run = self.get_run(run_id)
        with self.db.transaction() as connection:
            changed = connection.execute(
                "UPDATE tasks SET state='cancelled',error=NULL,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE run_id=? AND state IN ('queued','running')",
                (now(), run_id),
            ).rowcount
            if changed:
                events.record(
                    connection,
                    "collection_run_cancelled",
                    ("collection_run", run_id),
                    {"source_id": run.get("source_id")},
                )
        return self.get_run(run_id)

    def queue_collection(
        self,
        source_id,
        *,
        manual=True,
        _stopping=None,
        expected_version=None,
        overrides=None,
        planned_at=None,
    ):
        options = (
            overrides
            if isinstance(overrides, RunOverrides)
            else RunOverrides.model_validate(overrides or {})
        ).model_dump(exclude_none=True)
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if row is None:
                missing("Source")
            check_version(row, expected_version)
            if _stopping is not None and _stopping.is_set():
                return None
            setting = connection.execute(
                "SELECT data FROM settings WHERE key='collection'"
            ).fetchone()
            if not manual and (
                not row["enabled"]
                or (setting and not json.loads(setting["data"]).get("enabled", True))
            ):
                return None
            source = decode_record(row, ("config", "schedule"))
            require_automatic_collection(source["kind"])
            allowed_overrides = (
                {"hours_old", "results_wanted"} if source["kind"] == "jobspy" else {"max_results"}
            )
            if set(options) - allowed_overrides:
                raise DomainError(
                    422, "run_options", "These run options do not apply to this source service."
                )
            active = connection.execute(
                "SELECT * FROM tasks WHERE source_id=? AND kind='collect' AND state IN ('queued','running') ORDER BY created_at,id",
                (source_id,),
            ).fetchall()
            if active:
                if not manual:
                    connection.execute(
                        "UPDATE sources SET last_scheduled_at=? WHERE id=?",
                        (planned_at or now(), source_id),
                    )
                active_run = connection.execute(
                    "SELECT overrides FROM collection_runs WHERE id=?", (active[0]["run_id"],)
                ).fetchone()
                if options and (not active_run or json.loads(active_run["overrides"]) != options):
                    raise DomainError(
                        409,
                        "collection_active",
                        "A collection is already active. Wait or stop it before running different options.",
                    )
                if manual:
                    connection.execute(
                        "UPDATE tasks SET payload=json_set(payload,'$.manual',json('true')),updated_at=? WHERE source_id=? AND kind='collect' AND state IN ('queued','running')",
                        (now(), source_id),
                    )
                task_ids = [task["id"] for task in active]
                task = self._task_record(active[0])
                task["payload"]["manual"] = manual or task["payload"].get("manual", False)
                return {**task, "task_ids": task_ids, "run_id": active[0]["run_id"]}
            source["config"] = {**source["config"], **options}
            # Validate the frozen effective configuration, not a temporary edit of the saved source.
            if source["kind"] == "jobspy":
                jobspy_collector.JobSpyConfig.model_validate(
                    {k: v for k, v in source["config"].items() if k not in ("url", "filters")}
                )
            providers = (
                source["config"]["providers"] if source["kind"] == "jobspy" else [source["kind"]]
            )
            run_id, stamp = new_id(), now()
            snapshot = {
                key: source[key] for key in ("id", "name", "kind", "config", "version", "schedule")
            }
            connection.execute(
                "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,overrides,planned_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    source_id,
                    source["name"],
                    source["version"],
                    encode(snapshot),
                    encode(options),
                    planned_at,
                    stamp,
                ),
            )
            task_ids = []
            for provider in providers:
                task_id = new_id()
                connection.execute(
                    "INSERT INTO tasks(id,kind,source_id,run_id,payload,dedupe_key,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        task_id,
                        "collect",
                        source_id,
                        run_id,
                        encode(
                            {
                                "manual": manual,
                                "source_version": source["version"],
                                "provider": provider,
                                "run_id": run_id,
                            }
                        ),
                        "collect:" + source_id + ":" + provider + ":" + task_id,
                        stamp,
                        stamp,
                        stamp,
                    ),
                )
                task_ids.append(task_id)
            if not manual:
                connection.execute(
                    "UPDATE sources SET last_scheduled_at=? WHERE id=?",
                    (planned_at or stamp, source_id),
                )
            else:
                # Scheduled runs are routine; only a requested run is a recorded change.
                events.record(
                    connection,
                    "collection_queued",
                    ("collection_run", run_id),
                    {"source_id": source_id, "overrides": sorted(options)},
                )
        task_ids.sort()
        return {**self.get_task(task_ids[0]), "task_ids": task_ids, "run_id": run_id}

    def schedule_due(self, stopping=None):
        moment = datetime.now(UTC)
        for row in (
            self.db.all("SELECT * FROM sources WHERE enabled=1 ORDER BY created_at LIMIT 2000")
            if (self.workspace.get_settings("collection", {"enabled": True})["data"] or {}).get(
                "enabled", True
            )
            else []
        ):
            if stopping is not None and stopping.is_set():
                return
            source = decode_record(row, ("schedule", "config"))
            due = next_due(
                source["schedule"], source["last_scheduled_at"] or source["created_at"], moment
            )
            if due <= moment:
                self.queue_collection(
                    source["id"],
                    manual=False,
                    _stopping=stopping,
                    planned_at=(
                        moment if source["schedule"]["kind"] == "interval" else due
                    ).isoformat(timespec="microseconds"),
                )
