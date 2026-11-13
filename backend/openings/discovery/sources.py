"""Collection sources: schemas, preview, create, update, delete and bulk changes."""

from __future__ import annotations

from ..collectors import company as company_collectors, jobspy as jobspy_collector
from ..collectors.catalog import COMPANY_ADAPTERS
from ..collectors.policy import ProviderDeferred
from ..common import check_version, decode_record, encode, missing, new_id, now
from ..errors import DomainError
from ..idempotency import fingerprint, remember, replay
from ..scheduling import next_due, schedule_adapter
from .feeds import fetch_postings
from .models import (
    RSSConfig,
    RunOverrides,
    SourceBulk,
    SourceCreate,
    SourceKind,
    SourcePatch,
    SourcePreview,
)
from .network import HTTP_BUDGET
from .resolution import automatic_collection_supported, require_automatic_collection, resolve_source


class SourceOperations:
    """Saved searches and company/feed sources of DiscoveryService."""

    def _resolve_source(self, value):
        token = HTTP_BUDGET.set(self.http_budget("manual"))
        try:
            return resolve_source(value)
        finally:
            HTTP_BUDGET.reset(token)

    def bulk_sources(self, value: SourceBulk):
        items = []
        for selected in value.items:
            try:
                if value.action in ("enable", "pause"):
                    result = self.update_source(
                        selected.id,
                        SourcePatch(
                            expected_version=selected.expected_version,
                            enabled=value.action == "enable",
                        ),
                    )
                elif value.action == "configure":
                    result = self.update_source(
                        selected.id,
                        SourcePatch(
                            expected_version=selected.expected_version,
                            **value.patch.model_dump(exclude_unset=True),
                        ),
                    )
                else:
                    with self.db.lock:
                        source = self._source(selected.id)
                        check_version(source, selected.expected_version)
                        result = (
                            self.delete_source(selected.id, selected.expected_version)
                            if value.action == "delete"
                            else self.queue_collection(
                                selected.id,
                                expected_version=selected.expected_version,
                                overrides=value.overrides,
                            )
                        )
                items.append({"id": selected.id, "result": result})
            except DomainError as error:
                items.append(
                    {
                        "id": selected.id,
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "status": error.status,
                            "details": error.details,
                        },
                    }
                )
        failed = sum("error" in item for item in items)
        return {
            "items": items,
            "total": len(items),
            "succeeded": len(items) - failed,
            "failed": failed,
        }

    def _source(self, source_id):
        row = self.db.one("SELECT * FROM sources WHERE id=?", (source_id,))
        if row is None:
            missing("Source")
        return self._source_records([row])[0]

    def _source_records(self, rows, summary=False):
        if not rows:
            return []
        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        runs = self.db.all(
            "SELECT * FROM (SELECT *,ROW_NUMBER() OVER (PARTITION BY source_id ORDER BY created_at DESC,id DESC) AS position FROM collection_runs WHERE source_id IN ("
            + placeholders
            + ")) WHERE position=1",
            ids,
        )
        run_ids = [row["id"] for row in runs]
        tasks = (
            self.db.all(
                "SELECT * FROM tasks WHERE run_id IN (" + ",".join("?" for _ in run_ids) + ")",
                run_ids,
            )
            if run_ids
            else []
        )
        grouped = {run_id: [] for run_id in run_ids}
        for task in tasks:
            grouped[task["run_id"]].append(task)
        latest = {row["source_id"]: self._run_record(row, grouped[row["id"]]) for row in runs}
        enabled = (self.workspace.get_settings("collection", {"enabled": True})["data"] or {}).get(
            "enabled", True
        )
        result = []
        for raw in rows:
            row = decode_record(raw, ("config", "schedule"))
            row["enabled"] = bool(row["enabled"])
            row["automatic_collection"] = automatic_collection_supported(row["kind"])
            row["url"] = row["config"].get("url", "")
            row["filters"] = {
                "titles": [],
                "locations": [],
                "exclude_titles": [],
                **row["config"].get("filters", {}),
            }
            run = latest.get(row["id"])
            row["last_run"] = run
            row["last_outcome"] = run["state"] if run else None
            row["last_task_id"] = run["task_ids"][0] if run and run["task_ids"] else None
            row["last_counts"] = run["counts"] if run else {}
            diagnostics = (
                [diag for task in run["tasks"] for diag in task["result"].get("diagnostics", [])]
                if run
                else []
            )
            if summary:
                row["last_diagnostic_count"] = len(diagnostics)
            else:
                row["last_diagnostics"] = diagnostics
            row["last_error"] = (
                "; ".join(
                    task["error"]
                    for task in run["tasks"]
                    if task["error"] and task["state"] == "failed"
                )[:1000]
                or None
                if run
                else None
            )
            row["next_run_at"] = (
                run["next_run_at"]
                if run and run["state"] in ("queued", "running")
                else (
                    next_due(
                        row["schedule"], row["last_scheduled_at"] or row["created_at"]
                    ).isoformat(timespec="microseconds")
                    if row["enabled"] and enabled
                    else None
                )
            )
            if summary and run:
                row["last_run"] = self._run_summary(run)
            result.append(row)
        return result

    def source_schemas(self):
        items = []
        for kind in SourceKind.__args__:
            if kind == "auto":
                continue
            cls = (
                jobspy_collector.JobSpyConfig
                if kind == "jobspy"
                else RSSConfig
                if kind == "rss"
                else company_collectors.config_model(kind)
            )
            items.append(
                {
                    "kind": kind,
                    "label": "Saved portal search"
                    if kind == "jobspy"
                    else "RSS / Atom feed"
                    if kind == "rss"
                    else kind.title(),
                    "config_schema": cls.model_json_schema(),
                    "capabilities": {
                        "automatic_collection": automatic_collection_supported(kind),
                        "search": kind == "jobspy",
                        "lookback": kind == "jobspy",
                        "details": kind == "jobspy"
                        or (
                            kind in COMPANY_ADAPTERS
                            and COMPANY_ADAPTERS[kind].description_mode == "separate"
                        ),
                        "description_mode": "portal"
                        if kind == "jobspy"
                        else "inline"
                        if kind == "rss"
                        else COMPANY_ADAPTERS[kind].description_mode,
                    },
                }
            )
        return {
            "items": items,
            "schedule_schema": schedule_adapter.json_schema(),
            "run_overrides_schema": RunOverrides.model_json_schema(),
        }

    def list_sources(self, limit=100, offset=0, summary=True):
        """List sources; summary=true returns a compact last run and a diagnostic count instead of diagnostics."""
        limit, offset = min(max(limit, 1), 500), max(offset, 0)
        rows = self.db.all(
            "SELECT * FROM sources ORDER BY name,id LIMIT ? OFFSET ?", (limit, offset)
        )
        return {
            "items": self._source_records(rows, summary=summary),
            "total": self.db.one("SELECT COUNT(*) AS n FROM sources")["n"],
            "limit": limit,
            "offset": offset,
        }

    def get_source(self, source_id):
        return self._source(source_id)

    def preview_source(self, value: SourcePreview):
        resolved = self._resolve_source(value.model_dump())
        source = {**resolved, "name": value.name or resolved["config"].get("board", "RSS source")}
        config = {
            key: val for key, val in source["config"].items() if key not in ("url", "filters")
        }
        providers = (
            source["config"]["providers"] if source["kind"] == "jobspy" else [source["kind"]]
        )

        def estimate(preview):
            if source["kind"] == "jobspy":
                return jobspy_collector.request_estimate(config, preview=preview)
            adapter = COMPANY_ADAPTERS.get(source["kind"])
            count = source["config"].get("max_results", 100)
            count = min(count, 3) if preview else count
            requests = 1 + (count if adapter and adapter.description_mode == "separate" else 0)
            return {
                "total": requests,
                "providers": [{"id": providers[0], "min": 1, "max": requests}],
                "note": "Listing pagination, redirects and retries may add requests; cached text can reduce detail fetches.",
            }

        items, diagnostics = [], []
        for provider in providers:
            budget = self.http_budget(provider)
            token = HTTP_BUDGET.set(budget)
            attempt = {**source, "provider": provider, "preview": True}
            try:
                items.extend(fetch_postings(attempt))
                diagnostics.append(attempt.get("diagnostic") or budget.diagnostics())
            except DomainError as error:
                diagnostic = budget.diagnostics()
                diagnostic.update(
                    state="deferred" if isinstance(error, ProviderDeferred) else "error",
                    message=error.message,
                )
                diagnostics.append(diagnostic)
            finally:
                HTTP_BUDGET.reset(token)
        return {
            **resolved,
            "items": [
                {key: val for key, val in item.items() if key != "raw"} for item in items[:20]
            ],
            "total": len(items),
            "preview_limit": 20,
            "request_estimate": estimate(True),
            "full_request_estimate": estimate(False),
            "automatic_collection": automatic_collection_supported(source["kind"]),
            "diagnostics": diagnostics,
        }

    def create_source(self, value: SourceCreate):
        if not value.name.strip():
            raise DomainError(422, "source_name", "Give the company or feed a name.")
        # A retry with the key returns the source before resolving its board again.
        digest = fingerprint(value)
        if value.idempotency_key:
            with self.db.transaction() as connection:
                replayed = replay(connection, "sources", value.idempotency_key, digest)
            if replayed:
                return self._source(replayed)
        resolved = self._resolve_source(value.model_dump(exclude={"idempotency_key"}))
        require_automatic_collection(resolved["kind"])
        record_id, stamp = new_id(), now()
        with self.db.transaction() as connection:
            # Another request with the key may have created it in the meantime.
            replayed = replay(connection, "sources", value.idempotency_key, digest)
            if replayed is None:
                connection.execute(
                    "INSERT INTO sources(id,name,kind,config,enabled,schedule,last_scheduled_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        value.name.strip(),
                        resolved["kind"],
                        encode(resolved["config"]),
                        int(value.enabled),
                        encode(value.schedule.model_dump()),
                        stamp,
                        stamp,
                        stamp,
                    ),
                )
                self._record(
                    connection, "source_created", "source", record_id, kind=resolved["kind"]
                )
                remember(connection, "sources", value.idempotency_key, digest, record_id)
        return self._source(replayed or record_id)

    def update_source(self, source_id, value: SourcePatch):
        old = self._source(source_id)
        check_version(old, value.expected_version)
        updates = value.model_dump(exclude_unset=True)
        merged = {
            **old,
            **{
                key: val
                for key, val in updates.items()
                if key != "expected_version" and val is not None
            },
        }
        if "kind" in updates and updates["kind"] != old["kind"]:
            raise DomainError(
                422, "source_kind_immutable", "Create a new source to use a different service."
            )
        if "config" in updates:
            merged["config"] = {**old["config"], **updates["config"]}
        if "filters" in updates:
            merged["filters"] = {**old["filters"], **updates["filters"]}
        if not merged["name"].strip():
            raise DomainError(422, "source_name", "Give the company or feed a name.")
        if any(key in updates for key in ("url", "kind", "config", "filters")):
            resolved = self._resolve_source(merged)
        else:
            resolved = old
        if merged["enabled"]:
            require_automatic_collection(resolved["kind"])
        schedule = schedule_adapter.validate_python(merged["schedule"]).model_dump()
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            check_version(row, value.expected_version)
            connection.execute(
                "UPDATE sources SET name=?,kind=?,config=?,enabled=?,schedule=?,last_scheduled_at=?,version=version+1,updated_at=? WHERE id=?",
                (
                    merged["name"].strip(),
                    resolved["kind"],
                    encode(resolved["config"]),
                    int(merged["enabled"]),
                    encode(schedule),
                    now()
                    if "schedule" in updates or (merged["enabled"] and not old["enabled"])
                    else old["last_scheduled_at"],
                    now(),
                    source_id,
                ),
            )
            self._record(
                connection,
                "source_updated",
                "source",
                source_id,
                fields=sorted(key for key in updates if key != "expected_version"),
                version=row["version"] + 1,
            )
        return self._source(source_id)

    def delete_source(self, source_id, expected_version=None):
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if row is None:
                missing("Source")
            check_version(row, expected_version)
            connection.execute(
                "UPDATE tasks SET state='cancelled',error=NULL,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE source_id=? AND state IN ('queued','running')",
                (now(), source_id),
            )
            connection.execute("DELETE FROM sources WHERE id=?", (source_id,))
            self._record(connection, "source_deleted", "source", source_id)
        return {"deleted": True, "id": source_id}
