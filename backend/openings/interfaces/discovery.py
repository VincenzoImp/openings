"""Operations of collection: sources, the switch, providers, runs and fetches (tasks).

An agent uses sources_list/get/save/delete/run and collection_get/update; the
one-record and operator routes stay on REST for the dashboard and scripts.
"""

from ..collectors.policy import ProviderPatch
from ..discovery import (
    CollectionWrite,
    SourceBulk,
    SourceCreate,
    SourcePatch,
    SourcePreview,
    SourceRun,
)
from ..discovery.models import (
    CollectionQuery,
    CollectionRunQuery,
    SourceQuery,
    SourceRunInput,
    SourcesSave,
    TaskQuery,
)
from ..responses import (
    BatchResult,
    Collection,
    CollectionRun,
    CollectionRunPage,
    Deleted,
    Provider,
    ProviderList,
    Source,
    SourceDetail,
    SourcePage,
    SourcePreviewResult,
    SourceSchemas,
    Task,
    TaskPage,
)
from .core import Version
from .operation import DESTRUCTIVE, WRITE, WS, Q, operation


@operation("GET /collection", tags=["collection"])
def collection_get(ws: WS, query: Q[CollectionQuery]) -> Collection:
    """Read the collection switch, its version, counts and failing sources.

    include: kinds (source kinds and config fields), providers (limits, cooldowns), fetches
    (running, queued, failed).
    """
    return ws.discovery.read_collection(query)


@operation("PATCH /collection", access=WRITE, open_world=True, tags=["collection"])
def collection_update(ws: WS, body: CollectionWrite) -> Collection:
    """Turn scheduled collection on or off, change provider limits, stop or retry fetches.

    With the collection's version; results has one result per provider, cancel, retry.
    """
    return ws.discovery.update_collection(body)


@operation("GET /providers", tags=["collection"], mcp="collection_get")
def providers_list(ws: WS) -> ProviderList:
    """List providers with their HTTP limits and the shared window and cooldown."""
    return ws.discovery.list_providers()


@operation(
    "PATCH /providers/{provider_id}", access=WRITE, tags=["collection"], mcp="collection_update"
)
def providers_update(ws: WS, provider_id: str, body: ProviderPatch) -> Provider:
    """Edit a provider's HTTP policy, with its version."""
    return ws.discovery.update_provider(provider_id, body)


@operation("GET /collection/runs", tags=["collection"], mcp="sources_get")
def collection_runs_list(ws: WS, query: Q[CollectionRunQuery]) -> CollectionRunPage:
    """List collection runs by source or state."""
    return ws.discovery.list_runs(**query.model_dump())


@operation("GET /collection/runs/{run_id}", tags=["collection"], mcp="sources_get")
def collection_runs_get(ws: WS, run_id: str) -> CollectionRun:
    """Read a collection run with its frozen settings and fetches."""
    return ws.discovery.get_run(run_id)


@operation(
    "POST /collection/runs/{run_id}/cancel",
    access=WRITE,
    tags=["collection"],
    mcp="collection_update",
)
def collection_runs_cancel(ws: WS, run_id: str) -> CollectionRun:
    """Stop a collection run; jobs already archived stay."""
    return ws.discovery.cancel_run(run_id)


@operation("GET /sources/schemas", tags=["sources"], mcp="collection_get")
def sources_schemas(ws: WS) -> SourceSchemas:
    """Describe the fields, schedules and run options of each source kind."""
    return ws.discovery.source_schemas()


@operation("GET /sources", tags=["sources"])
def sources_list(ws: WS, query: Q[SourceQuery]) -> SourcePage:
    """List sources with schedule, last outcome and job counts.

    Counts: found, shortlisted, applied, replied. sources_get has a source's recent checks.
    """
    return ws.discovery.list_sources(**query.model_dump())


@operation("POST /sources/batch", access=WRITE, open_world=True, tags=["sources"])
def sources_save(ws: WS, body: SourcesSave) -> BatchResult:
    """Add or update up to 50 sources (saved searches, company boards, feeds).

    source_id with expected_version updates; enabled false pauses. Preview a new source
    with sources_run first.
    """
    return ws.discovery.save_sources(body)


@operation("POST /sources/run", access=WRITE, open_world=True, tags=["sources"])
def sources_run(ws: WS, body: SourceRunInput) -> SourcePreviewResult | Task:
    """Fetch a saved source now, or preview (preview true) what a source would collect.

    Preview a saved source (source_id) or an unsaved one (url, kind, config); nothing is
    stored. Through the provider gate.
    """
    return ws.discovery.run_source(body)


@operation("POST /sources/preview", open_world=True, tags=["sources"], mcp="sources_run")
def sources_preview(ws: WS, body: SourcePreview) -> SourcePreviewResult:
    """Preview a source without storing jobs, through the provider gate."""
    return ws.discovery.preview_source(body)


@operation(
    "POST /sources",
    access=WRITE,
    status=201,
    open_world=True,
    tags=["sources"],
    mcp="sources_save",
)
def sources_create(ws: WS, body: SourceCreate) -> Source:
    """Save a source; paused by default."""
    return ws.discovery.create_source(body)


@operation(
    "POST /sources/bulk",
    access=DESTRUCTIVE,
    open_world=True,
    tags=["sources"],
    mcp="sources_save",
)
def sources_bulk(ws: WS, body: SourceBulk) -> BatchResult:
    """Enable, pause, run, configure or delete selected sources, one result each."""
    return ws.discovery.bulk_sources(body)


@operation("GET /sources/{source_id}", tags=["sources"])
def sources_get(ws: WS, source_id: str) -> SourceDetail:
    """Read a source: its configuration, version and latest checks with their errors."""
    return ws.discovery.read_source(source_id)


@operation(
    "PATCH /sources/{source_id}",
    access=WRITE,
    open_world=True,
    tags=["sources"],
    mcp="sources_save",
)
def sources_update(ws: WS, source_id: str, body: SourcePatch) -> Source:
    """Edit or pause a source, with its version."""
    return ws.discovery.update_source(source_id, body)


@operation("DELETE /sources/{source_id}", access=DESTRUCTIVE, tags=["sources"])
def sources_delete(ws: WS, source_id: str, expected_version: Version) -> Deleted:
    """Delete a source permanently; archived jobs and their history stay."""
    return ws.discovery.delete_source(source_id, expected_version)


@operation(
    "POST /sources/{source_id}/run",
    access=WRITE,
    open_world=True,
    tags=["sources"],
    mcp="sources_run",
)
def sources_run_one(ws: WS, source_id: str, body: SourceRun) -> Task:
    """Run a source now, with its version and optional one-time overrides."""
    return ws.discovery.queue_collection(
        source_id, expected_version=body.expected_version, overrides=body.overrides
    )


@operation("GET /tasks", tags=["collection"], mcp="collection_get")
def tasks_list(ws: WS, query: Q[TaskQuery]) -> TaskPage:
    """List collection fetches (tasks) by state, kind, source or job."""
    return ws.discovery.list_tasks(**query.model_dump())


@operation("GET /tasks/{task_id}", tags=["collection"], mcp="collection_get")
def tasks_get(ws: WS, task_id: str) -> Task:
    """Read a fetch: inputs, result, HTTP diagnostics and next run time."""
    return ws.discovery.get_task(task_id)


@operation(
    "POST /tasks/{task_id}/cancel", access=WRITE, tags=["collection"], mcp="collection_update"
)
def tasks_cancel(ws: WS, task_id: str) -> Task:
    """Cancel a queued or running fetch."""
    return ws.discovery.cancel_task(task_id)


@operation(
    "POST /tasks/{task_id}/retry",
    access=WRITE,
    open_world=True,
    tags=["collection"],
    mcp="collection_update",
)
def tasks_retry(ws: WS, task_id: str) -> Task:
    """Retry a failed or cancelled fetch with its frozen inputs."""
    return ws.discovery.retry_task(task_id)
