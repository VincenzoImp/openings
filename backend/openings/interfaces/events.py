"""REST route and MCP tool of the change log (an API-only read for scripts)."""

from mcp.types import ToolAnnotations

from ..events import EventLog, EventQuery
from .registry import Operation, Route, Tool, bind_mcp, bind_rest, query_model

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

OPERATIONS = (
    Operation(
        "events.list",
        "events",
        "list",
        "Changes",
        "List recorded changes with their actor label, batch and subject",
        params=(query_model(EventQuery),),
        call=lambda s, value: s.list_events(value),
        rest=(Route("GET", "/events", "events_list"),),
        tool=Tool(
            READ,
            "List recorded changes, newest first, each with its actor label (owner, agent:<token name>, system; null before 0.17), batch_id (one per REST request or MCP tool call that writes) and subject. Filter by actor (owner, agent, agent:<name>, system, unknown), batch_id, since, until, job_id, application_id, subject, subject_types or kind. Changes by the system are left out unless actor=system or include_system=true.",
        ),
    ),
)


def register_api(router, log: EventLog):
    bind_rest(router, OPERATIONS, log)


def register_mcp(mcp, log: EventLog):
    bind_mcp(mcp, OPERATIONS, log)
