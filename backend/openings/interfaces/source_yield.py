"""REST routes and MCP tools of source_yield."""

from typing import Annotated

from ..source_yield import YieldQuery, YieldService


def register_api(router, service: YieldService):
    from fastapi import Query

    @router.get("/collection/yield")
    def collection_yield(value: Annotated[YieldQuery, Query()]):
        return service.source_yield(value)


def register_mcp(mcp, service: YieldService):
    from mcp.types import ToolAnnotations

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_yield(value: YieldQuery | None = None) -> dict:
        """Read what each collection source (saved search or company board) yielded for the jobs it first collected in the period: collected, still to review, shortlisted (kept), applied, employer responses (responded, interviews, offers), dismissed by a policy rule, an agent, the owner or other and by rule, likely duplicates and postings no longer listed; searches are also split by job board. kept_rate is null below min_sample collected jobs (default 10). Use it to narrow, pause or remove sources that collect much and keep little."""
        return service.source_yield(value or YieldQuery())
