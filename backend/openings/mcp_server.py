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


class OpeningsMCP(MCPServer):
    """Return REST-shaped error bodies; the SDK runs sync tools in worker threads."""

    async def call_tool(self, name, arguments, context=None):
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            body = {
                "code": domain.code,
                "status": domain.status,
                "message": domain.message,
                "details": domain.details,
            }
            raise ToolError(json.dumps({"error": body}, default=str)) from error.__cause__

    async def read_resource(self, uri, context=None):
        try:
            return await super().read_resource(uri, context)
        except UnexpectedResourceError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            kind = ResourceNotFoundError if domain.status == 404 else ResourceError
            raise kind(domain.message) from error.__cause__
