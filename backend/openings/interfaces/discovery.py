"""REST routes and MCP tools of discovery."""

import asyncio

from fastapi import Query
from mcp.types import ToolAnnotations

from ..collectors.policy import ProviderPatch
from ..discovery import (
    CollectionWrite,
    DiscoveryService,
    SourceBulk,
    SourceCreate,
    SourcePatch,
    SourcePreview,
    SourceRun,
)


def register_api(router, service: DiscoveryService):
    @router.get("/collection")
    def collection_get():
        return service.get_collection()

    @router.patch("/collection")
    def collection_update(value: CollectionWrite):
        return service.update_collection(value)

    @router.get("/providers")
    def providers_list():
        return service.list_providers()

    @router.patch("/providers/{provider_id}")
    def providers_update(provider_id: str, value: ProviderPatch):
        return service.update_provider(provider_id, value)

    @router.get("/collection/runs")
    def collection_runs_list(
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
        state: str | None = None,
        summary: bool = True,
    ):
        return service.list_runs(limit, offset, source_id, state, summary)

    @router.get("/collection/runs/{run_id}")
    def collection_runs_get(run_id: str):
        return service.get_run(run_id)

    @router.post("/collection/runs/{run_id}/cancel")
    def collection_runs_cancel(run_id: str):
        return service.cancel_run(run_id)

    @router.get("/sources/schemas")
    def sources_schemas():
        return service.source_schemas()

    @router.get("/sources")
    def sources_list(limit: int = 100, offset: int = 0, summary: bool = True):
        return service.list_sources(limit, offset, summary)

    @router.post("/sources/preview")
    def sources_preview(value: SourcePreview):
        return service.preview_source(value)

    @router.post("/sources", status_code=201)
    def sources_create(value: SourceCreate):
        return service.create_source(value)

    @router.post("/sources/bulk")
    def sources_bulk(value: SourceBulk):
        return service.bulk_sources(value)

    @router.get("/sources/{source_id}")
    def sources_get(source_id: str):
        return service.get_source(source_id)

    @router.patch("/sources/{source_id}")
    def sources_update(source_id: str, value: SourcePatch):
        return service.update_source(source_id, value)

    @router.delete("/sources/{source_id}")
    def sources_delete(source_id: str, expected_version: int = Query(ge=1)):
        return service.delete_source(source_id, expected_version)

    @router.post("/sources/{source_id}/run")
    def sources_run(source_id: str, value: SourceRun):
        return service.queue_collection(
            source_id, expected_version=value.expected_version, overrides=value.overrides
        )

    @router.get("/tasks")
    def tasks_list(
        limit: int = 50,
        offset: int = 0,
        state: str | None = None,
        kind: str | None = None,
        source_id: str | None = None,
        job_id: str | None = None,
    ):
        return service.list_tasks(limit, offset, state, kind, source_id, job_id)

    @router.get("/tasks/{task_id}")
    def tasks_get(task_id: str):
        return service.get_task(task_id)

    @router.post("/tasks/{task_id}/cancel")
    def tasks_cancel(task_id: str):
        return service.cancel_task(task_id)

    @router.post("/tasks/{task_id}/retry")
    def tasks_retry(task_id: str):
        return service.retry_task(task_id)


def register_mcp(mcp, service: DiscoveryService):
    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def sources_schemas() -> dict:
        """Discover supported source fields/defaults, schedule variants and temporary run options."""
        return service.source_schemas()

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_runs_list(
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
        state: str | None = None,
        summary: bool = True,
    ) -> dict:
        """List logical collections with cumulative provider counts, waiting and processing time. summary=false adds frozen source snapshots and full task payloads/results."""
        return service.list_runs(limit, offset, source_id, state, summary)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_runs_get(run_id: str) -> dict:
        """Read frozen acquisition settings and provider tasks for one collection invocation."""
        return service.get_run(run_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def collection_runs_cancel(run_id: str) -> dict:
        """Stop current collection work while retaining jobs already archived."""
        return service.cancel_run(run_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_get() -> dict:
        """Read the global automatic collection switch, counts and next queued run."""
        return service.get_collection()

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def collection_update(value: CollectionWrite) -> dict:
        """Pause/resume automatic collection with version protection; manual run remains available."""
        return service.update_collection(value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def providers_list() -> dict:
        """Read supported providers, editable HTTP safeguards and persisted window/cooldown diagnostics."""
        return service.list_providers()

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def providers_update(provider_id: str, value: ProviderPatch) -> dict:
        """Edit a provider policy using its version. Runtime/cooldown are read-only and shared by all runs."""
        return service.update_provider(provider_id, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
    )
    def sources_bulk(value: SourceBulk) -> dict:
        """Enable, pause, run, configure or delete selected versioned sources; inspect each result/error."""
        return service.bulk_sources(value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def sources_list(limit: int = 100, offset: int = 0, summary: bool = True) -> dict:
        """List saved portal searches and selected company/feed sources, schedules and outcomes. summary=false adds last-run diagnostics and full task records."""
        return service.list_sources(limit, offset, summary)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def sources_get(source_id: str) -> dict:
        """Read a source's complete editable configuration and version."""
        return service.get_source(source_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
    )
    async def sources_preview(value: SourcePreview) -> dict:
        """Preview a saved-search/company/feed configuration without saving jobs; shared request spacing and cooldowns apply."""
        return await asyncio.to_thread(service.preview_source, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    async def sources_create(value: SourceCreate) -> dict:
        """Create one explicit saved query/location or company/feed source; individually paused by default."""
        return await asyncio.to_thread(service.create_source, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    async def sources_update(source_id: str, value: SourcePatch) -> dict:
        """Update or pause a source with optimistic version protection."""
        return await asyncio.to_thread(service.update_source, source_id, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)
    )
    def sources_delete(source_id: str, expected_version: int) -> dict:
        """Remove a versioned source while retaining archived jobs and collection history."""
        return service.delete_source(source_id, expected_version)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def sources_run(source_id: str, value: SourceRun) -> dict:
        """Run a versioned source with frozen optional overrides; shared request spacing and cooldowns apply."""
        return service.queue_collection(
            source_id, expected_version=value.expected_version, overrides=value.overrides
        )

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def tasks_list(
        limit: int = 50,
        offset: int = 0,
        state: str | None = None,
        kind: str | None = None,
        source_id: str | None = None,
        job_id: str | None = None,
    ) -> dict:
        """Filter collection work by state/kind/source/job, with readable labels and diagnostics."""
        return service.list_tasks(limit, offset, state, kind, source_id, job_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def tasks_get(task_id: str) -> dict:
        """Read one task's inputs, result, HTTP diagnostics, lease and next run time."""
        return service.get_task(task_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def tasks_cancel(task_id: str) -> dict:
        """Cancel queued/running work; already stored jobs and documents are kept."""
        return service.cancel_task(task_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def tasks_retry(task_id: str) -> dict:
        """Retry failed/cancelled work; collection keeps its frozen inputs and saved progress."""
        return service.retry_task(task_id)
