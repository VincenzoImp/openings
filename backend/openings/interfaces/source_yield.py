"""REST routes and MCP tools of source_yield."""

from mcp.types import ToolAnnotations

from ..source_yield import YieldQuery, YieldService
from .registry import Operation, Route, Tool, bind_mcp, bind_rest, query_model

OPERATIONS = (
    Operation(
        "collection.yield",
        "sources",
        "yield",
        "Collection",
        "Read what each source and search yielded: collected, shortlisted, applied, responses, dismissed",
        params=(query_model(YieldQuery),),
        call=lambda s, value: s.source_yield(value or YieldQuery()),
        rest=(Route("GET", "/collection/yield", "collection_yield"),),
        tool=Tool(
            "collection_yield",
            ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
            "Read what each collection source (saved search or company board) yielded for the jobs it first collected in the period: collected, still to review, shortlisted (kept), applied, employer responses (responded, interviews, offers), dismissed by a policy rule, an agent, the owner or other and by rule, likely duplicates and postings no longer listed; searches are also split by job board. kept_rate is null below min_sample collected jobs (default 10). Use it to narrow, pause or remove sources that collect much and keep little.",
        ),
    ),
)


def register_api(router, service: YieldService):
    bind_rest(router, OPERATIONS, service)


def register_mcp(mcp, service: YieldService):
    bind_mcp(mcp, OPERATIONS, service)
