"""Sources in batches, one run-or-preview, and the collection read and update an agent uses.

``save_sources`` creates (no ``source_id``) or updates (``source_id`` with
``expected_version``) each item on its own; ``enabled: false`` pauses a source.
``run_source`` fetches a saved source now or, with ``preview``, shows what a saved
or unsaved source would collect without storing anything; both go through the
shared provider gate. ``read_collection`` adds source kinds, provider limits and
fetches on request; ``update_collection`` also changes provider limits and stops
or retries fetches, each item with its own result.
"""

from __future__ import annotations

from pydantic import ValidationError

from ..collectors.policy import ProviderPatch
from ..common import run_items
from ..errors import DomainError, invalid
from .models import (
    CollectionQuery,
    CollectionWrite,
    SourceCreate,
    SourceItem,
    SourcePatch,
    SourcePreview,
    SourceRunInput,
    SourcesSave,
)

FETCH_LIMIT = 20


def _missing(field, message):
    return DomainError(
        422,
        "validation",
        "Some fields need attention.",
        [{"field": [field], "message": message, "type": "missing"}],
    )


class SourceBatches:
    """sources_get, sources_save, sources_run, collection_get and collection_update."""

    def read_source(self, source_id):
        """A source with its configuration and its latest checks (runs with their errors)."""
        source = self.get_source(source_id)
        source["recent_runs"] = self.list_runs(source_id=source_id, limit=5)["items"]
        return source

    def save_sources(self, value: SourcesSave):
        def apply(item: SourceItem):
            data = item.model_dump(exclude_unset=True, exclude={"source_id"})
            if item.source_id is None:
                data.pop("expected_version", None)
                record = self.create_source(SourceCreate.model_validate(data, strict=False))
            else:
                if item.expected_version is None:
                    raise _missing("expected_version", "Updating a source needs its version.")
                if "idempotency_key" in data:
                    raise DomainError(
                        422, "idempotency_key", "An idempotency_key goes with a new source only."
                    )
                patch = SourcePatch.model_validate(data, strict=False)
                record = self.update_source(item.source_id, patch)
            keys = ("id", "version", "name", "kind", "enabled", "next_run_at")
            return {key: record.get(key) for key in keys}

        return run_items(self.db, value.items, lambda item: item.source_id, apply)

    def run_source(self, value: SourceRunInput):
        if not value.preview:
            if value.source_id is None or value.expected_version is None:
                raise _missing(
                    "source_id", "Fetching needs source_id and expected_version (or preview)."
                )
            return self.queue_collection(
                value.source_id, expected_version=value.expected_version, overrides=value.overrides
            )
        given = value.model_dump(
            exclude_unset=True, include={"name", "url", "kind", "config", "filters"}
        )
        if value.source_id is not None:
            source = self.get_source(value.source_id)
            saved = {
                "name": source["name"],
                "url": source["url"],
                "kind": source["kind"],
                "config": {
                    key: item
                    for key, item in source["config"].items()
                    if key not in ("url", "filters")
                },
                "filters": source["filters"],
            }
            given = {**saved, **given}
        elif not given.get("url") and not given.get("config"):
            raise _missing("url", "Preview a saved source (source_id) or give url or config.")
        try:
            preview = SourcePreview.model_validate(given, strict=False)
        except ValidationError as error:
            raise invalid(error) from error
        return {"preview": True, **self.preview_source(preview)}

    def read_collection(self, value: CollectionQuery | None = None):
        include = set(value.include) if value else set()
        collection = self.get_collection()
        collection["sources_failing"] = self.db.one(
            "SELECT count(*) AS n FROM sources s WHERE (SELECT t.state FROM tasks t WHERE "
            "t.source_id=s.id AND t.kind='collect' ORDER BY t.created_at DESC,t.id DESC LIMIT 1)"
            "='failed'"
        )["n"]
        if "kinds" in include:
            collection["kinds"] = self.source_schemas()
        if "providers" in include:
            collection["providers"] = self.list_providers()["items"]
        if "fetches" in include:
            collection["fetches"] = {
                state: self.list_tasks(state=state, limit=FETCH_LIMIT)["items"]
                for state in ("running", "queued", "failed")
            }
        return collection

    def update_collection(self, value: CollectionWrite):
        """The switch (with the collection's version), then provider limits, stops and retries."""
        self.set_collection_switch(value.expected_version, value.enabled)
        work = [
            *((change.provider_id, "provider", change) for change in value.providers),
            *((identifier, "cancel", None) for identifier in value.cancel),
            *((identifier, "retry", None) for identifier in value.retry),
        ]

        def apply(entry):
            identifier, action, change = entry
            if action == "provider":
                patch = change.model_dump(exclude_unset=True, exclude={"provider_id"})
                result = self.update_provider(identifier, ProviderPatch(**patch))
                return {"id": identifier, "version": result["version"]}
            if action == "retry":
                task = self.retry_task(identifier)
                return {"id": identifier, "state": task["state"]}
            if self.db.one("SELECT 1 FROM tasks WHERE id=?", (identifier,)):
                task = self.cancel_task(identifier)
                return {"id": identifier, "state": task["state"]}
            run = self.cancel_run(identifier)
            return {"id": identifier, "state": run["state"]}

        collection = self.read_collection()
        if work:
            collection["results"] = run_items(self.db, work, lambda entry: entry[0], apply)
        return collection
