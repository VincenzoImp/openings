"""REST routes and MCP tools of agent_requests."""

from typing import Annotated

from fastapi import Query

from ..agent_requests import (
    RequestComplete,
    RequestCreate,
    RequestDecline,
    RequestQuery,
    RequestService,
    RequestVersion,
)


def register_api(router, requests: RequestService):
    @router.get("/requests")
    def requests_list(value: Annotated[RequestQuery, Query()]):
        return requests.list_requests(value)

    @router.post("/requests", status_code=201)
    def requests_create(value: RequestCreate):
        return requests.create_request(value)

    @router.get("/requests/{request_id}")
    def requests_get(request_id: str):
        return requests.get_request(request_id)

    @router.post("/requests/{request_id}/take")
    def requests_take(request_id: str, value: RequestVersion):
        return requests.take_request(request_id, value)

    @router.post("/requests/{request_id}/complete")
    def requests_complete(request_id: str, value: RequestComplete):
        return requests.complete_request(request_id, value)

    @router.post("/requests/{request_id}/decline")
    def requests_decline(request_id: str, value: RequestDecline):
        return requests.decline_request(request_id, value)

    @router.post("/requests/{request_id}/withdraw")
    def requests_withdraw(request_id: str, value: RequestVersion):
        return requests.withdraw_request(request_id, value)


def register_mcp(mcp, requests: RequestService):
    from mcp.types import ToolAnnotations

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)

    @mcp.tool(annotations=read)
    def requests_list(value: RequestQuery | None = None) -> dict:
        """List the owner's requests for the agent by state (open, taken, done, declined, withdrawn), subject or run. Read state=open at the start of every run. updated_since returns the requests written or changed at or after a time, oldest first."""
        return requests.list_requests(value)

    @mcp.tool(annotations=read)
    def requests_get(request_id: str) -> dict:
        """Read one request for the agent with its state, who wrote it, the run that handled it and the result or reason."""
        return requests.get_request(request_id)

    @mcp.tool(annotations=write)
    def requests_create(value: RequestCreate) -> dict:
        """Write a request for the agent, tied to a job, an application, a Career entry (knowledge) or nothing. Owner only: an agent token is refused with forbidden and never writes requests for itself. Use an idempotency key for retries."""
        return requests.create_request(value)

    @mcp.tool(annotations=write)
    def requests_take(request_id: str, value: RequestVersion) -> dict:
        """Take an open request in this workflow's scope, using its current version; this token's open run is recorded as the run that handles it. A request never authorises submitting an application, contacting an employer or recording Applied."""
        return requests.take_request(request_id, value)

    @mcp.tool(annotations=write)
    def requests_complete(request_id: str, value: RequestComplete) -> dict:
        """Complete an open or taken request with a short result the owner will read, using its current version."""
        return requests.complete_request(request_id, value)

    @mcp.tool(annotations=write)
    def requests_decline(request_id: str, value: RequestDecline) -> dict:
        """Decline an open or taken request with the reason, for example that it asks for something the operating mandate forbids, using its current version."""
        return requests.decline_request(request_id, value)

    @mcp.tool(annotations=write)
    def requests_withdraw(request_id: str, value: RequestVersion) -> dict:
        """Withdraw an open or taken request, using its current version. Owner only: an agent token is refused with forbidden. The record stays readable."""
        return requests.withdraw_request(request_id, value)
