"""REST routes and MCP tools of outcomes."""

from ..outcomes import ResponseInput, ResponsePatch, ResponseService


def register_api(router, responses: ResponseService):
    @router.get("/applications/{application_id}/responses")
    def responses_list(application_id: str):
        return responses.list_responses(application_id)

    @router.post("/applications/{application_id}/responses", status_code=201)
    def responses_add(application_id: str, value: ResponseInput):
        return responses.add_response(application_id, value)

    @router.patch("/responses/{response_id}")
    def responses_update(response_id: str, value: ResponsePatch):
        return responses.update_response(response_id, value)

    @router.delete("/responses/{response_id}")
    def responses_remove(response_id: str, expected_version: int):
        return responses.remove_response(response_id, expected_version)


def register_mcp(mcp, responses: ResponseService):
    from mcp.types import ToolAnnotations

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)
    remove = ToolAnnotations(destructiveHint=True, openWorldHint=False)

    @mcp.tool(annotations=read)
    def responses_list(application_id: str) -> dict:
        """Read the employer responses of one application (rejection, interview, offer, other), newest day first, with who recorded each and whether its day is estimated."""
        return responses.list_responses(application_id)

    @mcp.tool(annotations=write)
    def responses_add(application_id: str, value: ResponseInput) -> dict:
        """Record an employer response the owner reported, with the day it arrived. Only for a sent application (409 application_not_sent otherwise); one response of a kind per day (409 response_exists). Never moves the stage: to record an interview, offer or rejection together with the stage, use application_update with response_date. Never invent a response."""
        return responses.add_response(application_id, value)

    @mcp.tool(annotations=write)
    def responses_update(response_id: str, value: ResponsePatch) -> dict:
        """Correct a response's kind, day or note with its current version. A corrected day clears estimated."""
        return responses.update_response(response_id, value)

    @mcp.tool(annotations=remove)
    def responses_remove(response_id: str, expected_version: int) -> dict:
        """Delete a response recorded by mistake, with its current version. The application's stage does not change."""
        return responses.remove_response(response_id, expected_version)
