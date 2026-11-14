"""REST routes and MCP tools: one typed function per operation (``operation.py``), by area,
and the hand-written transport routes (``transport.py``)."""

from . import career, core, discovery, documents, preferences, system
from .operation import OPERATIONS, bind_mcp, bind_rest
from .transport import TRANSPORT_ONLY, register_prompts, register_transport

AREAS = (core, career, documents, discovery, preferences, system)

__all__ = [
    "AREAS",
    "OPERATIONS",
    "TRANSPORT_ONLY",
    "bind_mcp",
    "bind_rest",
    "register_prompts",
    "register_transport",
]
