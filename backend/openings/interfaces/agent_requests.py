"""REST routes and MCP tools of agent_requests."""

from mcp.types import ToolAnnotations

from ..agent_requests import (
    RequestComplete,
    RequestCreate,
    RequestDecline,
    RequestQuery,
    RequestService,
    RequestVersion,
)
from .registry import Operation, Param, Route, Tool, bind_mcp, bind_rest, query_model

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)

OPERATIONS = (
    Operation(
        "requests.list",
        "requests",
        "list",
        "Agent activity",
        "List requests for the agent by state, subject, run or change time",
        params=(query_model(RequestQuery),),
        call=lambda s, value: s.list_requests(value),
        rest=(Route("GET", "/requests", "requests_list"),),
        tool=Tool(
            READ,
            "List the owner's requests for the agent by state (open, taken, done, declined, withdrawn), subject or run. Read state=open at the start of every run. updated_since returns the requests written or changed at or after a time, oldest first.",
        ),
    ),
    Operation(
        "requests.create",
        "requests",
        "create",
        "Agent activity",
        "Write a request for the agent tied to a job, application, Career entry or nothing",
        access="owner",
        params=(Param("value", RequestCreate),),
        call=lambda s, value: s.create_request(value),
        rest=(Route("POST", "/requests", "requests_create", status_code=201),),
        tool=Tool(
            WRITE,
            "Write a request for the agent, tied to a job, an application, a Career entry (knowledge) or nothing. Owner only: an agent token is refused with forbidden and never writes requests for itself. Use an idempotency key for retries.",
        ),
    ),
    Operation(
        "requests.read",
        "requests",
        "get",
        "Agent activity",
        "Read one request for the agent",
        params=(Param("request_id", str),),
        call=lambda s, request_id: s.get_request(request_id),
        rest=(Route("GET", "/requests/{request_id}", "requests_get"),),
        tool=Tool(
            READ,
            "Read one request for the agent with its state, who wrote it, the run that handled it and the result or reason.",
        ),
    ),
    Operation(
        "requests.take",
        "requests",
        "take",
        "Agent activity",
        "Take an open request for the calling token's run",
        params=(Param("request_id", str), Param("value", RequestVersion)),
        call=lambda s, request_id, value: s.take_request(request_id, value),
        rest=(Route("POST", "/requests/{request_id}/take", "requests_take"),),
        tool=Tool(
            WRITE,
            "Take an open request in this workflow's scope, using its current version; this token's open run is recorded as the run that handles it. A request never authorises submitting an application, contacting an employer or recording Applied.",
        ),
    ),
    Operation(
        "requests.complete",
        "requests",
        "complete",
        "Agent activity",
        "Complete a request with its result",
        params=(Param("request_id", str), Param("value", RequestComplete)),
        call=lambda s, request_id, value: s.complete_request(request_id, value),
        rest=(Route("POST", "/requests/{request_id}/complete", "requests_complete"),),
        tool=Tool(
            WRITE,
            "Complete an open or taken request with a short result the owner will read, using its current version.",
        ),
    ),
    Operation(
        "requests.decline",
        "requests",
        "decline",
        "Agent activity",
        "Decline a request with a reason",
        params=(Param("request_id", str), Param("value", RequestDecline)),
        call=lambda s, request_id, value: s.decline_request(request_id, value),
        rest=(Route("POST", "/requests/{request_id}/decline", "requests_decline"),),
        tool=Tool(
            WRITE,
            "Decline an open or taken request with the reason, for example that it asks for something the operating mandate forbids, using its current version.",
        ),
    ),
    Operation(
        "requests.withdraw",
        "requests",
        "withdraw",
        "Agent activity",
        "Withdraw an open or taken request",
        access="owner",
        params=(Param("request_id", str), Param("value", RequestVersion)),
        call=lambda s, request_id, value: s.withdraw_request(request_id, value),
        rest=(Route("POST", "/requests/{request_id}/withdraw", "requests_withdraw"),),
        tool=Tool(
            WRITE,
            "Withdraw an open or taken request, using its current version. Owner only: an agent token is refused with forbidden. The record stays readable.",
        ),
    ),
)


def register_api(router, requests: RequestService):
    bind_rest(router, OPERATIONS, requests)


def register_mcp(mcp, requests: RequestService):
    bind_mcp(mcp, OPERATIONS, requests)
