"""REST routes and MCP tools of insights."""

from mcp.types import ToolAnnotations

from ..insights import InsightsQuery, InsightsService
from .registry import Operation, Route, Tool, bind_mcp, bind_rest, query_model

OPERATIONS = (
    Operation(
        "insights.read",
        "insights",
        "get",
        "Applications and documents",
        "Read response, interview and offer rates of sent applications, overall and by group",
        params=(query_model(InsightsQuery),),
        call=lambda s, value: s.insights(value or InsightsQuery()),
        rest=(Route("GET", "/insights", "insights_get"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
            "Read how employers answered the owner's sent applications: counts and response, interview and offer rates with the median days to the first answer, overall and grouped by role family, seniority, location, source kind, named source and month applied. Only employer responses count; Drafts and attempts closed without being sent are counted under excluded. A rate is null with withheld when fewer than min_sample (default 5) applications were sent: do not read meaning into small groups. no_reply gives the no-reply period and how many Applied applications are past it.",
        ),
    ),
)


def register_api(router, insights: InsightsService):
    bind_rest(router, OPERATIONS, insights)


def register_mcp(mcp, insights: InsightsService):
    bind_mcp(mcp, OPERATIONS, insights)
