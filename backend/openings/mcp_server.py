"""MCP server that matches REST threading and error contracts."""

import json
import sqlite3

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import (
    ResourceError,
    ResourceNotFoundError,
    ToolError,
    UnexpectedResourceError,
)
from pydantic import ValidationError

from .errors import DomainError


def validation_details(error: ValidationError):
    return [
        {"field": list(e["loc"]), "message": e["msg"], "type": e["type"]}
        for e in error.errors(include_url=False, include_context=False)
    ]


def structured_error(error: BaseException) -> DomainError | None:
    if isinstance(error, DomainError):
        return error
    if isinstance(error, ValidationError):
        return DomainError(
            422, "validation", "Some fields need attention.", validation_details(error)
        )
    if isinstance(error, sqlite3.IntegrityError):
        return DomainError(409, "constraint", "This change conflicts with existing workspace data.")
    return None


def error_text(domain: DomainError) -> str:
    body = {
        "code": domain.code,
        "status": domain.status,
        "message": domain.message,
        "details": domain.details,
    }
    return json.dumps({"error": body}, default=str)


# Tools removed in 0.24, with what replaces each, for an agent that still calls them.
_PREFERENCES = "Removed in 0.24: the policy became Preferences. Use preferences_get and preferences_update (one whole section at a time); the no-reply period and spoken languages are settings_update."
REMOVED_TOOLS = {
    "policy_get": _PREFERENCES,
    "policy_add": _PREFERENCES,
    "policy_update": _PREFERENCES,
    "policy_move": _PREFERENCES,
    "policy_remove": _PREFERENCES,
    "policy_reorder": _PREFERENCES,
    "policy_confirm": _PREFERENCES,
    "policy_rule_preview": "Removed in 0.24 with the automatic rules: nothing is dismissed automatically. Filter jobs_list (signal, requires, hide_unspoken_required) and dismiss with jobs_bulk.",
    "instructions_get": "Removed in 0.24: general instructions are Writing rules in Preferences (preferences_get, section writing).",
    "instructions_update": "Removed in 0.24: general instructions are Writing rules in Preferences (preferences_update, section writing).",
}
# #215: frozen contexts and staleness.
_CONTEXTS = "Removed in 0.24 with frozen contexts: read the live records instead (applications_get, jobs_get, profile_get, knowledge_list, claims_list, templates_list, preferences_get) and cite claim_ids and knowledge_ids in documents_create."
REMOVED_TOOLS |= {
    "contexts_create": _CONTEXTS,
    "contexts_get": _CONTEXTS,
    "contexts_list": _CONTEXTS,
    "staleness_get": "Removed in 0.24: documents are no longer compared with changed inputs. Read the application's revisions with documents_list and replace one with documents_create (previous_id).",
    "staleness_list": "Removed in 0.24: documents are no longer compared with changed inputs. List applications with applications_list and their revisions with documents_list.",
}


class OpeningsMCP(MCPServer):
    """Return REST-shaped error bodies; the SDK runs sync tools in worker threads."""

    async def call_tool(self, name, arguments, context=None):
        try:
            if name in REMOVED_TOOLS and self._tool_manager.get_tool(name) is None:
                raise DomainError(404, "tool_removed", REMOVED_TOOLS[name], {"tool": name})
            self._refuse_unknown_arguments(name, arguments)
            return await super().call_tool(name, arguments, context)
        except DomainError as error:
            raise ToolError(error_text(error)) from error
        except ToolError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            raise ToolError(error_text(domain)) from error.__cause__

    def _refuse_unknown_arguments(self, name, arguments):
        """An argument the tool does not take is refused, never ignored.

        Lists take their filters inside ``value``; a filter passed beside it would
        otherwise be dropped silently and the list returned unfiltered.
        """
        tool = self._tool_manager.get_tool(name)
        if tool is None or not arguments:
            return
        unknown = sorted(set(arguments) - set(tool.parameters.get("properties", {})))
        if unknown:
            raise DomainError(
                422,
                "validation",
                "Some fields need attention.",
                [
                    {
                        "field": [field],
                        "message": "This tool takes no such argument; pass filters, "
                        "options and a write's fields inside value.",
                        "type": "extra_forbidden",
                    }
                    for field in unknown
                ],
            )

    async def read_resource(self, uri, context=None):
        try:
            return await super().read_resource(uri, context)
        except UnexpectedResourceError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            kind = ResourceNotFoundError if domain.status == 404 else ResourceError
            raise kind(domain.message) from error.__cause__
