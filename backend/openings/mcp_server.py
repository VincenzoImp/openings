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


class OpeningsMCP(MCPServer):
    """Return REST-shaped error bodies; the SDK runs sync tools in worker threads."""

    async def call_tool(self, name, arguments, context=None):
        try:
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
