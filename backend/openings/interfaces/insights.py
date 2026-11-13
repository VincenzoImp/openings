"""REST routes and MCP tools of insights."""

from ..insights import InsightsQuery, InsightsService


def register_api(router, insights: InsightsService):
    from typing import Annotated

    from fastapi import Query

    @router.get("/insights")
    def insights_get(value: Annotated[InsightsQuery, Query()]):
        return insights.insights(value)


def register_mcp(mcp, insights: InsightsService):
    from mcp.types import ToolAnnotations

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def insights_get(value: InsightsQuery | None = None) -> dict:
        """Read how employers answered the owner's sent applications: counts and response, interview and offer rates with the median days to the first answer, overall and grouped by role family, seniority, location, source kind, named source and month applied. Only employer responses count; Drafts and attempts closed without being sent are counted under excluded. A rate is null with withheld when fewer than min_sample (default 5) applications were sent: do not read meaning into small groups. no_reply gives the no-reply period and how many Applied applications are past it."""
        return insights.insights(value or InsightsQuery())
