"""One declaration per operation: its REST routes and its MCP tool.

An area module lists its ``Operation`` declarations. ``bind_rest`` and
``bind_mcp`` turn each declaration into a FastAPI route and an MCP tool that
call the same service code, and ``capability_entries`` lists them for
``GET /api/v1/capabilities``. Adding an operation means one declaration plus its
service method.

Parity runs one way: every dashboard action is a REST operation, and every
operation that is not owner-only is also an MCP tool. An owner-only operation
may be REST-only (``tool=None``). ``backend/tests/test_parity.py`` checks this.

A declaration names its parameters once (``Param``); a parameter that REST
reads differently, such as a query model, says so with ``rest``. A route or
tool marked ``custom`` is registered by hand next to the declarations (raw
bytes, streaming, browser sessions) and is still declared here.

The MCP tool is named ``<resource>_<verb>`` (``canonical_name``). Its arguments
are the identifiers a REST path names, ``expected_version`` of a delete, and one
``value`` object: a write's body, or a read's filters, paging and options (the
REST body or query string). Each operation has that one name and that one
shape: the earlier names and flat arguments of 0.21 were removed in 0.23.
"""

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query
from mcp.types import ToolAnnotations

REQUIRED = inspect.Parameter.empty
API_PREFIX = "/api/v1"


@dataclass(frozen=True)
class Param:
    """One input: its MCP annotation and default, and REST's when they differ."""

    name: str
    annotation: Any
    default: Any = REQUIRED
    # (annotation, default) REST uses instead, e.g. a query model or a bounded integer.
    rest: tuple[Any, Any] | None = None
    # The model of a ``value`` read from the query string (``query_model``).
    model: Any = None


def query_model(model):
    """A ``value`` model: optional on MCP, read from the query string on REST."""
    return Param(
        "value", model | None, None, rest=(Annotated[model, Query()], REQUIRED), model=model
    )


@dataclass(frozen=True)
class Route:
    """A REST route of an operation. ``name`` gives FastAPI's operation id and summary."""

    method: str
    path: str
    name: str
    status_code: int | None = None
    # Replace the operation's parameters or call for this route only.
    params: tuple[Param, ...] | None = None
    call: Callable | None = None
    custom: bool = False
    # A path outside the API prefix (/health, /mcp/).
    absolute: bool = False


@dataclass(frozen=True)
class Tool:
    """The MCP tool of an operation, named by the operation's ``canonical_name``."""

    annotations: ToolAnnotations
    description: str | None = None
    # The service method that is the tool itself (its signature and docstring).
    method: str | None = None
    # Run the call in a worker thread from an async tool, off the event loop.
    offload: bool = False
    params: tuple[Param, ...] | None = None
    call: Callable | None = None
    custom: bool = False


@dataclass(frozen=True)
class Operation:
    """A logical operation: identity, inputs, service call and interfaces.

    ``access`` is ``"owner"`` for an operation an agent token may not perform.
    """

    id: str
    resource: str
    verb: str
    group: str
    label: str
    params: tuple[Param, ...] = ()
    call: Callable | None = None
    rest: tuple[Route, ...] = ()
    tool: Tool | None = None
    access: str | None = None

    @property
    def canonical_name(self):
        """The ``<resource>_<verb>`` name of the operation's MCP tool."""
        return f"{self.resource}_{self.verb}"


@dataclass(frozen=True)
class Exemption:
    """A documented transport difference: routes without an operation, with a one-line reason."""

    id: str
    reason: str
    rest: tuple[Route, ...] = ()


@dataclass(frozen=True)
class Surface:
    """An MCP resource template or prompt family, registered by hand next to its area."""

    kind: str
    name: str


def _function(name, params, call, service, *, offload=False, returns=REQUIRED, doc=None):
    """A function with the given name and signature that calls ``call(service, **kwargs)``."""
    if offload:

        async def function(**kwargs):
            return await asyncio.to_thread(call, service, **kwargs)

    elif inspect.iscoroutinefunction(call):

        async def function(**kwargs):
            return await call(service, **kwargs)

    else:

        def function(**kwargs):
            return call(service, **kwargs)

    parameters = [
        inspect.Parameter(
            name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default, annotation=annotation
        )
        for name, annotation, default in params
    ]
    function.__name__ = function.__qualname__ = name
    function.__doc__ = doc
    function.__signature__ = inspect.Signature(parameters, return_annotation=returns)
    function.__annotations__ = {name: annotation for name, annotation, _ in params}
    if returns is not REQUIRED:
        function.__annotations__["return"] = returns
    return function


def _rest_params(params):
    return [(p.name, *(p.rest or (p.annotation, p.default))) for p in params]


def _mcp_params(params):
    return [(p.name, p.annotation, p.default) for p in params]


def bind_rest(router, operations, service):
    """Add the REST routes of the operations, in declaration order, to the router."""
    for operation in operations:
        for route in operation.rest:
            if route.custom:
                continue
            params = route.params if route.params is not None else operation.params
            endpoint = _function(
                route.name, _rest_params(params), route.call or operation.call, service
            )
            options = {} if route.status_code is None else {"status_code": route.status_code}
            router.add_api_route(
                route.path, endpoint, methods=[route.method], name=route.name, **options
            )


def bind_mcp(mcp, operations, service):
    """Add the MCP tool of each operation, in declaration order."""
    for operation in operations:
        tool = operation.tool
        if tool is None or tool.custom:
            continue
        name = operation.canonical_name
        if tool.method:
            function = getattr(service, tool.method)
        else:
            params = tool.params if tool.params is not None else operation.params
            function = _function(
                name,
                _mcp_params(params),
                tool.call or operation.call,
                service,
                offload=tool.offload,
                returns=dict,
                doc=tool.description,
            )
        mcp.add_tool(function, name=name, annotations=tool.annotations)


def capability_entries(operations):
    """One ``{name, method, path}`` entry per operation, plus ``access: owner`` when owner-only.

    ``name`` is the operation's MCP name; ``method`` and ``path`` are its main REST
    route, relative to ``/api/v1``. An entry without ``access`` is open to any token.
    """
    entries = []
    for operation in operations:
        if not operation.rest:
            continue
        route = operation.rest[0]
        entry = {
            "name": operation.canonical_name,
            "method": route.method,
            "path": route.path.replace(":path", ""),
        }
        if operation.access:
            entry["access"] = operation.access
        entries.append(entry)
    return entries
