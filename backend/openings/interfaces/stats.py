"""REST route and MCP tool of Stats."""

from mcp.types import ToolAnnotations

from ..stats import StatsQuery, StatsService
from .registry import Operation, Route, Tool, bind_mcp, bind_rest, query_model

OPERATIONS = (
    Operation(
        "stats.read",
        "stats",
        "get",
        "Applications and documents",
        "Read how employers answered the sent applications in a period",
        params=(query_model(StatsQuery),),
        call=lambda s, value: s.stats(value or StatsQuery()),
        rest=(Route("GET", "/stats", "stats_get"),),
        tool=Tool(
            ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
            "Read the applications sent in a period (90d, 12m or all): applied, replied and reply_rate, interviews and interview_rate, the median days from applied to the first reply, the funnel (applied, replied, interview, offer) and by_source (replies per source that first found the job, only when at least 2 sources have 5 or more sent applications each, else null).",
        ),
    ),
)


def register_api(router, stats: StatsService):
    bind_rest(router, OPERATIONS, stats)


def register_mcp(mcp, stats: StatsService):
    bind_mcp(mcp, OPERATIONS, stats)
