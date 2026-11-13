"""REST routes and MCP tools of outcomes."""

from mcp.types import ToolAnnotations

from ..outcomes import ResponseInput, ResponsePatch, ResponseService
from .registry import Operation, Param, Route, Tool, bind_mcp, bind_rest

GROUP = "Applications and documents"
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)
REMOVE = ToolAnnotations(destructiveHint=True, openWorldHint=False)

OPERATIONS = (
    Operation(
        "responses.list",
        "responses",
        "list",
        GROUP,
        "List the employer responses of an application",
        params=(Param("application_id", str),),
        call=lambda s, application_id: s.list_responses(application_id),
        rest=(Route("GET", "/applications/{application_id}/responses", "responses_list"),),
        tool=Tool(
            READ,
            "Read the employer responses of one application (rejection, interview, offer, other), newest day first, with who recorded each.",
        ),
    ),
    Operation(
        "responses.add",
        "responses",
        "create",
        GROUP,
        "Record an employer response to a sent application",
        params=(Param("application_id", str), Param("value", ResponseInput)),
        call=lambda s, application_id, value: s.add_response(application_id, value),
        rest=(
            Route(
                "POST",
                "/applications/{application_id}/responses",
                "responses_add",
                status_code=201,
            ),
        ),
        tool=Tool(
            WRITE,
            "Record an employer response the owner reported, with the day it arrived. Only for a sent application (409 application_not_sent otherwise); one response of a kind per day (409 response_exists). Never moves the stage: to record an interview, offer or rejection together with the stage, use applications_update with response_date. Never invent a response.",
        ),
    ),
    Operation(
        "responses.update",
        "responses",
        "update",
        GROUP,
        "Correct an employer response's kind, day or note",
        params=(Param("response_id", str), Param("value", ResponsePatch)),
        call=lambda s, response_id, value: s.update_response(response_id, value),
        rest=(Route("PATCH", "/responses/{response_id}", "responses_update"),),
        tool=Tool(
            WRITE,
            "Correct a response's kind, day or note with its current version.",
        ),
    ),
    Operation(
        "responses.remove",
        "responses",
        "delete",
        GROUP,
        "Delete an employer response recorded by mistake",
        params=(Param("response_id", str), Param("expected_version", int)),
        call=lambda s, response_id, expected_version: s.remove_response(
            response_id, expected_version
        ),
        rest=(Route("DELETE", "/responses/{response_id}", "responses_remove"),),
        tool=Tool(
            REMOVE,
            "Delete a response recorded by mistake, with its current version. The application's stage does not change.",
        ),
    ),
)


def register_api(router, responses: ResponseService):
    bind_rest(router, OPERATIONS, responses)


def register_mcp(mcp, responses: ResponseService):
    bind_mcp(mcp, OPERATIONS, responses)
