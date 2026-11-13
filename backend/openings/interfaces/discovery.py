"""REST routes and MCP tools of discovery."""

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
from ..discovery.models import CollectionRunQuery, SourceQuery, TaskQuery
from .registry import Operation, Param, Route, Tool, bind_mcp, bind_rest, query_model

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
CHANGE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

OPERATIONS = (
    Operation(
        "collection.read",
        "collection",
        "get",
        "Collection",
        "Read global collection state and status",
        params=(),
        call=lambda s: s.get_collection(),
        rest=(Route("GET", "/collection", "collection_get"),),
        tool=Tool(
            READ,
            "Read the global automatic collection switch, counts and next queued run.",
        ),
    ),
    Operation(
        "collection.update",
        "collection",
        "update",
        "Collection",
        "Enable or pause scheduled collection globally",
        params=(Param("value", CollectionWrite),),
        call=lambda s, value: s.update_collection(value),
        rest=(Route("PATCH", "/collection", "collection_update"),),
        tool=Tool(
            CHANGE,
            "Pause/resume automatic collection with version protection; manual run remains available.",
        ),
    ),
    Operation(
        "providers.list",
        "providers",
        "list",
        "Collection",
        "Read provider capabilities, policies and runtime",
        params=(),
        call=lambda s: s.list_providers(),
        rest=(Route("GET", "/providers", "providers_list"),),
        tool=Tool(
            READ,
            "Read supported providers, editable HTTP safeguards and persisted window/cooldown diagnostics.",
        ),
    ),
    Operation(
        "providers.update",
        "providers",
        "update",
        "Collection",
        "Edit versioned provider HTTP policy",
        params=(Param("provider_id", str), Param("value", ProviderPatch)),
        call=lambda s, provider_id, value: s.update_provider(provider_id, value),
        rest=(Route("PATCH", "/providers/{provider_id}", "providers_update"),),
        tool=Tool(
            CHANGE,
            "Edit a provider policy using its version. Runtime/cooldown are read-only and shared by all runs.",
        ),
    ),
    Operation(
        "collection.runs.list",
        "collection_runs",
        "list",
        "Collection",
        "List logical collection invocations",
        params=(query_model(CollectionRunQuery),),
        call=lambda s, value: s.list_runs(**(value or CollectionRunQuery()).model_dump()),
        rest=(Route("GET", "/collection/runs", "collection_runs_list"),),
        tool=Tool(
            READ,
            "List logical collections with cumulative provider counts, waiting and processing time, by source_id or state. summary=false adds frozen source snapshots and full task payloads/results.",
        ),
    ),
    Operation(
        "collection.runs.read",
        "collection_runs",
        "get",
        "Collection",
        "Read frozen collection settings, progress and results",
        params=(Param("run_id", str),),
        call=lambda s, run_id: s.get_run(run_id),
        rest=(Route("GET", "/collection/runs/{run_id}", "collection_runs_get"),),
        tool=Tool(
            READ,
            "Read frozen acquisition settings and provider tasks for one collection invocation.",
        ),
    ),
    Operation(
        "collection.runs.cancel",
        "collection_runs",
        "cancel",
        "Collection",
        "Stop current collection work",
        params=(Param("run_id", str),),
        call=lambda s, run_id: s.cancel_run(run_id),
        rest=(Route("POST", "/collection/runs/{run_id}/cancel", "collection_runs_cancel"),),
        tool=Tool(
            CHANGE,
            "Stop current collection work while retaining jobs already archived.",
        ),
    ),
    Operation(
        "sources.schemas",
        "sources",
        "schemas",
        "Collection",
        "Discover source fields, defaults and collection options",
        params=(),
        call=lambda s: s.source_schemas(),
        rest=(Route("GET", "/sources/schemas", "sources_schemas"),),
        tool=Tool(
            READ,
            "Discover supported source fields/defaults, schedule variants and temporary run options.",
        ),
    ),
    Operation(
        "sources.list",
        "sources",
        "list",
        "Collection",
        "List saved searches/company feeds and health",
        params=(query_model(SourceQuery),),
        call=lambda s, value: s.list_sources(**(value or SourceQuery()).model_dump()),
        rest=(Route("GET", "/sources", "sources_list"),),
        tool=Tool(
            READ,
            "List saved portal searches and selected company/feed sources, schedules and outcomes. summary=false adds last-run diagnostics and full task records.",
        ),
    ),
    Operation(
        "sources.preview",
        "sources",
        "preview",
        "Collection",
        "Preview a source without storing jobs",
        params=(Param("value", SourcePreview),),
        call=lambda s, value: s.preview_source(value),
        rest=(Route("POST", "/sources/preview", "sources_preview"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
            "Preview a saved-search/company/feed configuration without saving jobs; shared request spacing and cooldowns apply.",
            offload=True,
        ),
    ),
    Operation(
        "sources.create",
        "sources",
        "create",
        "Collection",
        "Save a typed search or company/feed source",
        params=(Param("value", SourceCreate),),
        call=lambda s, value: s.create_source(value),
        rest=(Route("POST", "/sources", "sources_create", status_code=201),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
            "Create one explicit saved query/location or company/feed source; individually paused by default.",
            offload=True,
        ),
    ),
    Operation(
        "sources.bulk",
        "sources",
        "bulk",
        "Collection",
        "Enable, pause, run, configure or delete selected sources",
        params=(Param("value", SourceBulk),),
        call=lambda s, value: s.bulk_sources(value),
        rest=(Route("POST", "/sources/bulk", "sources_bulk"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True),
            "Enable, pause, run, configure or delete selected versioned sources; inspect each result/error.",
        ),
    ),
    Operation(
        "sources.read",
        "sources",
        "get",
        "Collection",
        "Read full source configuration",
        params=(Param("source_id", str),),
        call=lambda s, source_id: s.get_source(source_id),
        rest=(Route("GET", "/sources/{source_id}", "sources_get"),),
        tool=Tool(READ, "Read a source's complete editable configuration and version."),
    ),
    Operation(
        "sources.update",
        "sources",
        "update",
        "Collection",
        "Edit source configuration, schedule or enabled state",
        params=(Param("source_id", str), Param("value", SourcePatch)),
        call=lambda s, source_id, value: s.update_source(source_id, value),
        rest=(Route("PATCH", "/sources/{source_id}", "sources_update"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
            "Update or pause a source with optimistic version protection.",
            offload=True,
        ),
    ),
    Operation(
        "sources.delete",
        "sources",
        "delete",
        "Collection",
        "Delete a source while retaining archived jobs",
        params=(Param("source_id", str), Param("expected_version", int, rest=(int, Query(ge=1)))),
        call=lambda s, source_id, expected_version: s.delete_source(source_id, expected_version),
        rest=(Route("DELETE", "/sources/{source_id}", "sources_delete"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False),
            "Remove a versioned source while retaining archived jobs and collection history.",
        ),
    ),
    Operation(
        "sources.run",
        "sources",
        "run",
        "Collection",
        "Queue one immediate collection",
        params=(Param("source_id", str), Param("value", SourceRun)),
        call=lambda s, source_id, value: s.queue_collection(
            source_id, expected_version=value.expected_version, overrides=value.overrides
        ),
        rest=(Route("POST", "/sources/{source_id}/run", "sources_run"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
            "Run a versioned source with frozen optional overrides; shared request spacing and cooldowns apply.",
        ),
    ),
    Operation(
        "tasks.list",
        "tasks",
        "list",
        "Collection",
        "List/filter paginated collection tasks",
        params=(query_model(TaskQuery),),
        call=lambda s, value: s.list_tasks(**(value or TaskQuery()).model_dump()),
        rest=(Route("GET", "/tasks", "tasks_list"),),
        tool=Tool(
            READ,
            "Filter collection work by state/kind/source/job, with readable labels and diagnostics.",
        ),
    ),
    Operation(
        "tasks.read",
        "tasks",
        "get",
        "Collection",
        "Read task progress, result and diagnostics",
        params=(Param("task_id", str),),
        call=lambda s, task_id: s.get_task(task_id),
        rest=(Route("GET", "/tasks/{task_id}", "tasks_get"),),
        tool=Tool(
            READ,
            "Read one task's inputs, result, HTTP diagnostics, lease and next run time.",
        ),
    ),
    Operation(
        "tasks.cancel",
        "tasks",
        "cancel",
        "Collection",
        "Cancel queued/running work",
        params=(Param("task_id", str),),
        call=lambda s, task_id: s.cancel_task(task_id),
        rest=(Route("POST", "/tasks/{task_id}/cancel", "tasks_cancel"),),
        tool=Tool(
            CHANGE,
            "Cancel queued/running work; already stored jobs and documents are kept.",
        ),
    ),
    Operation(
        "tasks.retry",
        "tasks",
        "retry",
        "Collection",
        "Explicitly retry failed/cancelled work",
        params=(Param("task_id", str),),
        call=lambda s, task_id: s.retry_task(task_id),
        rest=(Route("POST", "/tasks/{task_id}/retry", "tasks_retry"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
            "Retry failed/cancelled work; collection keeps its frozen inputs and saved progress.",
        ),
    ),
)


def register_api(router, service: DiscoveryService):
    bind_rest(router, OPERATIONS, service)


def register_mcp(mcp, service: DiscoveryService):
    bind_mcp(mcp, OPERATIONS, service)
