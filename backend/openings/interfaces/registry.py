"""One declaration per operation: its REST routes, its MCP tool and its inventory entry.

An area module lists its ``Operation`` declarations. ``bind_rest`` and
``bind_mcp`` turn each declaration into a FastAPI route and an MCP tool that
call the same service code, and ``inventory`` writes the operation inventory
from them (``scripts/inventory.py``). Adding an operation means one declaration
plus its service method.

A declaration names its parameters once (``Param``); a parameter that REST
reads differently, such as a query model, says so with ``rest``. A route or
tool marked ``custom`` is registered by hand next to the declarations (raw
bytes, streaming, browser sessions) and is still listed in the inventory.

The MCP tool is named ``<resource>_<verb>`` (``canonical_name``). Its arguments
are the identifiers a REST path names, ``expected_version`` of a delete, and one
``value`` object: a write's body, or a read's filters, paging and options (the
REST body or query string). Names and argument shapes from before 0.22 stay
until 0.23 as ``aliases`` and ``Tool.legacy`` (#167).
"""

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query
from mcp.types import ToolAnnotations
from pydantic import Field

from ..errors import DomainError

REQUIRED = inspect.Parameter.empty
API_PREFIX = "/api/v1"
# The release that removes the aliases and the deprecated flat arguments.
REMOVAL = "0.23"
LEGACY = f"Deprecated: pass it in value; removed in {REMOVAL}."


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
    # Fields of the ``value`` query model this tool also accepted as flat arguments
    # before 0.22; still accepted, deprecated, until REMOVAL.
    legacy: tuple[str, ...] = ()


@dataclass(frozen=True)
class Alias:
    """An earlier tool name kept until REMOVAL.

    Without ``params`` the alias is the tool itself. With them it keeps the
    arguments the earlier tool took, and ``call`` maps them to the operation.
    """

    name: str
    params: tuple[Param, ...] | None = None
    call: Callable | None = None


@dataclass(frozen=True)
class Operation:
    """A logical operation: inventory identity, inputs, service call and interfaces."""

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
    # Earlier tool names kept until REMOVAL (#167): a name, or an Alias with its old arguments.
    aliases: tuple[str | Alias, ...] = ()

    @property
    def canonical_name(self):
        """The ``<resource>_<verb>`` name of the operation's MCP tool."""
        return f"{self.resource}_{self.verb}"

    @property
    def alias_entries(self):
        return tuple(Alias(item) if isinstance(item, str) else item for item in self.aliases)


@dataclass(frozen=True)
class Exemption:
    """A documented transport difference: routes or tools without a logical twin."""

    id: str
    reason: str
    rest: tuple[Route, ...] = ()
    tools: tuple[str, ...] = ()


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


def _legacy(params, names, call):
    """Accept the deprecated flat arguments ``names`` and fold them into ``value``."""
    model = next(param.model for param in params if param.name == "value")
    extra = [
        (
            name,
            Annotated[model.model_fields[name].annotation | None, Field(description=LEGACY)],
            None,
        )
        for name in names
    ]

    def folded(service, **kwargs):
        given = {name: kwargs.pop(name) for name in names}
        given = {name: item for name, item in given.items() if item is not None}
        if given:
            if kwargs.get("value") is not None:
                raise DomainError(
                    422,
                    "validation",
                    "Pass these arguments inside value, not beside it.",
                    [{"field": [name], "message": LEGACY} for name in given],
                )
            kwargs["value"] = model.model_validate(given)
        return call(service, **kwargs)

    return folded, extra


def deprecation(name):
    """The start of an alias's description."""
    return f"Deprecated alias of {name}; removed in {REMOVAL}."


def bind_mcp(mcp, operations, service):
    """Add the MCP tool of each operation, then its aliases, in declaration order."""
    for operation in operations:
        tool = operation.tool
        if tool is None or tool.custom:
            continue
        name = operation.canonical_name
        if tool.method:
            function = getattr(service, tool.method)
        else:
            params = tool.params if tool.params is not None else operation.params
            call, arguments = tool.call or operation.call, _mcp_params(params)
            if tool.legacy:
                call, extra = _legacy(params, tool.legacy, call)
                arguments += extra
            function = _function(
                name,
                arguments,
                call,
                service,
                offload=tool.offload,
                returns=dict,
                doc=tool.description,
            )
        mcp.add_tool(function, name=name, annotations=tool.annotations)
        description = inspect.getdoc(function) or ""
        for alias in operation.alias_entries:
            # An earlier name of the same tool, with its earlier arguments when they differ.
            target = function
            if alias.params is not None:
                target = _function(
                    alias.name,
                    _mcp_params(alias.params),
                    alias.call,
                    service,
                    offload=tool.offload,
                    returns=dict,
                )
            mcp.add_tool(
                target,
                name=alias.name,
                description=f"{deprecation(name)} {description}".strip(),
                annotations=tool.annotations,
            )


def _routes(routes):
    return [
        {
            "method": route.method,
            "path": ("" if route.absolute else API_PREFIX) + route.path.replace(":path", ""),
        }
        for route in routes
    ]


def inventory(operations, exemptions, notes):
    """The operation inventory: declarations in the notes' order, with their remarks."""
    declared = {operation.id: operation for operation in operations}
    exempted = {exemption.id: exemption for exemption in exemptions}
    listed = [item["id"] for item in notes["operations"]]
    if sorted(listed) != sorted(declared):
        raise ValueError(
            f"Inventory notes and declarations differ: {sorted(set(listed) ^ set(declared))}"
        )
    if sorted(item["id"] for item in notes["exceptions"]) != sorted(exempted):
        raise ValueError("Inventory notes and exemptions differ.")
    document = {
        key: value for key, value in notes.items() if key not in ("operations", "exceptions")
    }
    document["operations"] = []
    for item in notes["operations"]:
        operation = declared[item["id"]]
        entry = {
            "id": operation.id,
            "group": operation.group,
            "operation": operation.label,
            "rest": _routes(operation.rest),
            "mcp": (
                [operation.canonical_name, *(alias.name for alias in operation.alias_entries)]
                if operation.tool
                else []
            ),
            "dashboard": item["dashboard"],
        }
        if "notes" in item:
            entry["notes"] = item["notes"]
        if operation.access:
            entry["access"] = operation.access
        document["operations"].append(entry)
    document["exceptions"] = [
        {
            "id": item["id"],
            "rest": _routes(exempted[item["id"]].rest),
            "mcp": list(exempted[item["id"]].tools),
            "dashboard": item["dashboard"],
            "reason": exempted[item["id"]].reason,
        }
        for item in notes["exceptions"]
    ]
    return document


def alias_rows(operations):
    """Each alias with its tool and whether it keeps the arguments it took before 0.22."""
    rows = []
    for operation in operations:
        for alias in operation.alias_entries:
            if alias.params is None:
                arguments = "the same arguments"
            else:
                arguments = "its earlier arguments: " + ", ".join(
                    f"`{param.name}`" for param in alias.params
                )
            rows.append((alias.name, operation.canonical_name, arguments))
    return sorted(rows)


def legacy_rows(operations):
    """Each tool that still accepts flat arguments it now takes inside ``value``."""
    return [
        (operation.canonical_name, operation.tool.legacy)
        for operation in operations
        if operation.tool and operation.tool.legacy
    ]
