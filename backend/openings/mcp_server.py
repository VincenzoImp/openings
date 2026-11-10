"""FastMCP server that matches REST threading and error contracts."""

import functools
import json
import sqlite3

import anyio.to_thread
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
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


class OpeningsMCP(FastMCP):
    """Run sync tools off the event loop and return REST-shaped error bodies."""

    def add_tool(self, fn, *args, **kwargs):
        super().add_tool(fn, *args, **kwargs)
        tool = self._tool_manager.get_tool(kwargs.get("name") or fn.__name__)
        if tool is not None and not tool.is_async:
            sync = tool.fn

            @functools.wraps(sync)
            async def threaded(**arguments):
                return await anyio.to_thread.run_sync(functools.partial(sync, **arguments))

            tool.fn, tool.is_async = threaded, True

    async def call_tool(self, name, arguments):
        try:
            return await super().call_tool(name, arguments)
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
