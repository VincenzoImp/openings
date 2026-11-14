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

from .actors import batch
from .errors import DomainError
from .removed import REMOVED_TOOLS


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

    # Owner-only operation name -> its REST route, for an agent that calls it.
    owner_only: dict[str, str] = {}  # noqa: RUF012 - replaced per instance by bind_mcp

    async def call_tool(self, name, arguments, context=None):
        try:
            if name in REMOVED_TOOLS and self._tool_manager.get_tool(name) is None:
                raise DomainError(404, "tool_removed", REMOVED_TOOLS[name], {"tool": name})
            if name in self.owner_only:
                raise DomainError(
                    404,
                    "owner_only",
                    f"{name} is owner-only and not an MCP tool: the owner uses the dashboard "
                    f"or {self.owner_only[name]} with an owner token.",
                    {"tool": name},
                )
            self._refuse_unknown_arguments(name, arguments)
            # Every change of one tool call shares one batch id.
            with batch():
                return await super().call_tool(name, arguments, context)
        except DomainError as error:
            raise ToolError(error_text(error)) from error
        except ToolError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            raise ToolError(error_text(domain)) from error.__cause__

    def _refuse_unknown_arguments(self, name, arguments):
        """An argument the tool does not take is refused, never ignored: a misspelt
        filter would otherwise return the list unfiltered."""
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
                        "message": "This tool takes no such argument; tools/list "
                        "gives its arguments.",
                        "type": "extra_forbidden",
                    }
                    for field in unknown
                ],
            )

    def add_built_tool(self, tool):
        """Register a tool built from an operation declaration (interfaces/operation.py)."""
        self._tool_manager._tools[tool.name] = tool

    async def read_resource(self, uri, context=None):
        try:
            return await super().read_resource(uri, context)
        except UnexpectedResourceError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            kind = ResourceNotFoundError if domain.status == 404 else ResourceError
            raise kind(domain.message) from error.__cause__
