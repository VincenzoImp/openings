"""Operations of collection: the global switch, providers, sources, runs and tasks."""

from ..collectors.policy import ProviderPatch
from ..discovery import (
    CollectionWrite,
    SourceBulk,
    SourceCreate,
    SourcePatch,
    SourcePreview,
    SourceRun,
)
from ..discovery.models import CollectionRunQuery, SourceQuery, TaskQuery
from ..responses import (
    BatchResult,
    Collection,
    CollectionRun,
    CollectionRunPage,
    Deleted,
    Provider,
    ProviderList,
    Source,
    SourcePage,
    SourcePreviewResult,
    SourceSchemas,
    Task,
    TaskPage,
)
from .core import Version
from .operation import DESTRUCTIVE, WRITE, WS, Q, operation


@operation("GET /collection", tags=["collection"])
def collection_get(ws: WS) -> Collection:
    """Read the collection switch, counts and next queued run."""
    return ws.discovery.get_collection()


@operation("PATCH /collection", access=WRITE, tags=["collection"])
def collection_update(ws: WS, body: CollectionWrite) -> Collection:
    """Pause or resume scheduled collection.

    With its version; running a source by hand stays available.
    """
    return ws.discovery.update_collection(body)


@operation("GET /providers", tags=["collection"])
def providers_list(ws: WS) -> ProviderList:
    """List providers.

    Supported providers, their editable HTTP safeguards and the shared window and cooldown.
    """
    return ws.discovery.list_providers()


@operation("PATCH /providers/{provider_id}", access=WRITE, tags=["collection"])
def providers_update(ws: WS, provider_id: str, body: ProviderPatch) -> Provider:
    """Edit a provider's HTTP policy.

    With its version. Runtime and cooldown are read-only and shared by all runs.
    """
    return ws.discovery.update_provider(provider_id, body)


@operation("GET /collection/runs", tags=["collection"])
def collection_runs_list(ws: WS, query: Q[CollectionRunQuery]) -> CollectionRunPage:
    """List collection runs.

    With provider counts and timing, by source_id or state. summary=false adds source
    snapshots and full task records.
    """
    return ws.discovery.list_runs(**query.model_dump())


@operation("GET /collection/runs/{run_id}", tags=["collection"])
def collection_runs_get(ws: WS, run_id: str) -> CollectionRun:
    """Read a collection run.

    Its frozen settings, progress and provider tasks.
    """
    return ws.discovery.get_run(run_id)


@operation("POST /collection/runs/{run_id}/cancel", access=WRITE, tags=["collection"])
def collection_runs_cancel(ws: WS, run_id: str) -> CollectionRun:
    """Stop a collection run.

    Jobs already archived stay.
    """
    return ws.discovery.cancel_run(run_id)


@operation("GET /sources/schemas", tags=["sources"])
def sources_schemas(ws: WS) -> SourceSchemas:
    """Describe source fields.

    Supported fields and defaults, schedule variants and run options of each kind.
    """
    return ws.discovery.source_schemas()


@operation("GET /sources", tags=["sources"])
def sources_list(ws: WS, query: Q[SourceQuery]) -> SourcePage:
    """List sources.

    Saved searches and company feeds with schedules, outcomes and counts of jobs found,
    shortlisted, applied and replied. summary=false adds run diagnostics.
    """
    return ws.discovery.list_sources(**query.model_dump())


@operation("POST /sources/preview", open_world=True, tags=["sources"])
def sources_preview(ws: WS, body: SourcePreview) -> SourcePreviewResult:
    """Preview a source without storing jobs.

    Requests go through the provider gate (spacing and cooldowns).
    """
    return ws.discovery.preview_source(body)


@operation("POST /sources", access=WRITE, status=201, open_world=True, tags=["sources"])
def sources_create(ws: WS, body: SourceCreate) -> Source:
    """Save a source.

    One saved search (query and location) or company feed; paused by default.
    """
    return ws.discovery.create_source(body)


@operation("POST /sources/bulk", access=DESTRUCTIVE, open_world=True, tags=["sources"])
def sources_bulk(ws: WS, body: SourceBulk) -> BatchResult:
    """Enable, pause, run, configure or delete selected sources.

    Ids with versions, one result or error each.
    """
    return ws.discovery.bulk_sources(body)


@operation("GET /sources/{source_id}", tags=["sources"])
def sources_get(ws: WS, source_id: str) -> Source:
    """Read a source's configuration and version."""
    return ws.discovery.get_source(source_id)


@operation("PATCH /sources/{source_id}", access=WRITE, open_world=True, tags=["sources"])
def sources_update(ws: WS, source_id: str, body: SourcePatch) -> Source:
    """Edit or pause a source.

    With its version.
    """
    return ws.discovery.update_source(source_id, body)


@operation("DELETE /sources/{source_id}", access=DESTRUCTIVE, tags=["sources"])
def sources_delete(ws: WS, source_id: str, expected_version: Version) -> Deleted:
    """Delete a source.

    Archived jobs and collection history stay.
    """
    return ws.discovery.delete_source(source_id, expected_version)


@operation("POST /sources/{source_id}/run", access=WRITE, open_world=True, tags=["sources"])
def sources_run(ws: WS, source_id: str, body: SourceRun) -> Task:
    """Run a source now.

    With its version and optional one-time overrides; the provider gate applies.
    """
    return ws.discovery.queue_collection(
        source_id, expected_version=body.expected_version, overrides=body.overrides
    )


@operation("GET /tasks", tags=["collection"])
def tasks_list(ws: WS, query: Q[TaskQuery]) -> TaskPage:
    """List collection tasks.

    By state, kind, source or job, with labels and diagnostics.
    """
    return ws.discovery.list_tasks(**query.model_dump())


@operation("GET /tasks/{task_id}", tags=["collection"])
def tasks_get(ws: WS, task_id: str) -> Task:
    """Read a task.

    Inputs, result, HTTP diagnostics, lease and next run time.
    """
    return ws.discovery.get_task(task_id)


@operation("POST /tasks/{task_id}/cancel", access=WRITE, tags=["collection"])
def tasks_cancel(ws: WS, task_id: str) -> Task:
    """Cancel a queued or running task.

    Jobs and documents already stored stay.
    """
    return ws.discovery.cancel_task(task_id)


@operation("POST /tasks/{task_id}/retry", access=WRITE, open_world=True, tags=["collection"])
def tasks_retry(ws: WS, task_id: str) -> Task:
    """Retry a failed or cancelled task.

    With its frozen inputs and saved progress.
    """
    return ws.discovery.retry_task(task_id)
