"""One typed function per operation: its REST route and, unless owner-only, its MCP tool.

    @operation("PATCH /jobs/{job_id}", access=WRITE, tags=["jobs"])
    def jobs_update(ws: WS, job_id: str, body: JobPatch) -> JobSummary:
        '''Correct a job's fields.

        With the version jobs_get returned; returns the compact summary.
        '''
        return ws.update_job(job_id, body)

REST: FastAPI reads the function itself. ``ws`` (``WS``) is the workspace with its
services, a model parameter is the JSON body (``Q[Model]``: the query string),
the return annotation is the response model and the function name the
``operationId``. The docstring's first line is the summary, the rest the
description.

MCP: the tool has the function's name and description and takes the other
parameters, a model's fields flattened beside them, so a call names the same
fields as the REST path and body. Its input schema is compacted (``compact_schema``)
and its result is compact JSON without empty fields (``compact_result``).

Owner-only operations (``OWNER``) are REST only. So is an operation declared with
``mcp="<tool>"``: a REST route kept for the dashboard or scripts whose work the
named MCP tool does (a batch tool covering a one-record route, for example). A
route whose actions several tools cover names them all (``mcp=("a", "b")``).
"""

import functools
import inspect
import json
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_origin

from fastapi import Depends, Query, Request
from mcp.server.mcpserver.tools.base import Tool
from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, create_model
from pydantic.fields import FieldInfo

from ..actors import require_owner
from ..workspace import Workspace

API_PREFIX = "/api/v1"
READ, WRITE, DESTRUCTIVE, OWNER = "read", "write", "destructive", "owner"
# The origin of the current REST request or MCP call, set at the HTTP boundary.
request_origin: ContextVar[str | None] = ContextVar("openings_origin", default=None)


def _workspace(request: Request) -> Workspace:
    return request.app.state.workspace


WS = Annotated[Workspace, Depends(_workspace)]


class Q:
    """``Q[Model]``: a model read from the query string on REST."""

    def __class_getitem__(cls, model):
        return Annotated[model, Query()]


@dataclass
class Operation:
    name: str
    routes: list[tuple[str, str]]
    fn: Any
    access: str
    tags: list[str]
    status: int | None
    open_world: bool
    summary: str
    description: str
    covered_by: tuple[str, ...] = ()  # REST only: the MCP tools that do this work
    tool: Any = None  # (Tool, split), built once and shared by every application

    @property
    def on_mcp(self):
        return self.access != OWNER and not self.covered_by

    @property
    def method(self):
        return self.routes[0][0]

    @property
    def path(self):
        return self.routes[0][1]


OPERATIONS: list[Operation] = []


def operation(*routes, access=READ, tags=(), status=None, open_world=False, mcp=None):
    """Declare an operation on ``"METHOD /path"`` (a second route is a REST alias).

    ``mcp`` names the MCP tool (or tools) that do this operation's work: the
    operation is then REST only.
    """
    covered = (mcp,) if isinstance(mcp, str) else tuple(mcp or ())

    def register(fn):
        summary, _, rest = inspect.getdoc(fn).partition("\n")
        pairs = [tuple(route.split(" ", 1)) for route in routes]
        flags = (access, list(tags), status, open_world)
        description = " ".join(rest.split())
        OPERATIONS.append(Operation(fn.__name__, pairs, fn, *flags, summary, description, covered))
        return fn

    return register


def _owner_only(action):
    """A dependency that refuses an agent token."""

    def owner_only():
        require_owner(action)

    return Depends(owner_only)


def _endpoint(fn, path):
    """``fn`` for one route of an operation with several: identifiers that the
    route's path does not name (``application_id`` on ``/jobs/{job_id}/...``) are
    left out rather than read from the query string."""
    signature = inspect.signature(fn)
    kept = [
        p for n, p in signature.parameters.items() if not n.endswith("_id") or f"{{{n}}}" in path
    ]
    assert not inspect.iscoroutinefunction(fn), "an operation with REST aliases is sync"
    endpoint = functools.wraps(fn)(lambda *args, **kwargs: fn(*args, **kwargs))
    endpoint.__signature__ = signature.replace(parameters=kept)
    return endpoint


def bind_rest(router, errors):
    """Add every operation's routes under ``API_PREFIX``; ``errors(op, path)`` gives
    its documented errors."""
    for op in OPERATIONS:
        action = op.summary[0].lower() + op.summary[1:].rstrip(".")
        for index, (method, path) in enumerate(op.routes):
            name = op.name if index == 0 else f"{op.name}_{index}"
            router.add_api_route(
                API_PREFIX + path,
                _endpoint(op.fn, path) if len(op.routes) > 1 else op.fn,
                methods=[method],
                name=name,
                operation_id=name,
                summary=op.summary,
                description=op.description,
                tags=op.tags,
                responses=errors(op, path),
                response_model_exclude_unset=True,
                dependencies=[_owner_only(action)] if op.access == OWNER else None,
                openapi_extra={"x-openings-access": op.access}
                | ({"x-openings-mcp": ", ".join(op.covered_by)} if op.covered_by else {}),
                **({"status_code": op.status} if op.status else {}),
            )


class _Arguments(ArgModelBase):
    """The validated arguments of a tool call, handed to the tool function whole."""

    model_config = ConfigDict(extra="forbid")

    def model_dump_one_level(self):
        return {"arguments": self}


def _plain(annotation):
    """A parameter's type for MCP and its bare type: FastAPI markers dropped, constraints kept."""
    if get_origin(annotation) is not Annotated:
        return annotation, annotation
    base, *extras = get_args(annotation)
    constraints = [m for extra in extras if isinstance(extra, FieldInfo) for m in extra.metadata]
    return (Annotated[base, *constraints] if constraints else base), base


# Defaults that say no more than leaving the argument out.
def _empty_default(value):
    return value is None or value is False or value in ("", [], {})


def compact_schema(schema):
    """A tool's input schema without what an agent does not need to call it.

    No ``title``; ``$defs`` inlined; a nullable ``anyOf`` becomes its other type
    (leaving the argument out means null); defaults that equal leaving it out, text
    lengths and patterns, the description of an array's items and nested ``additionalProperties``
    are dropped. The server still
    validates every argument and names the limit an argument broke.
    """
    definitions = schema.get("$defs", {})

    def visit(node, top=False):
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = definitions[node["$ref"].rsplit("/", 1)[-1]]
            extra = {key: value for key, value in node.items() if key != "$ref"}
            return visit({**target, **extra})
        result = {}
        for key, value in node.items():
            if key in ("title", "$defs", "discriminator", "minLength", "maxLength", "pattern"):
                continue
            if key == "additionalProperties" and (value is True or not top):
                continue
            if key == "default" and _empty_default(value):
                continue
            if key == "properties":
                result[key] = {name: visit(item) for name, item in value.items()}
                continue
            if key == "items" and isinstance(value, dict):
                # An array's description says what its items are.
                result[key] = {k: v for k, v in visit(value).items() if k != "description"}
                continue
            result[key] = visit(value)
        options = result.get("anyOf")
        if options and {"type": "null"} in options:
            options = [option for option in options if option != {"type": "null"}]
            del result["anyOf"]
            result = {**options[0], **result} if len(options) == 1 else {"anyOf": options, **result}
        return result

    return visit(schema, top=True)


def _dropped(value):
    return value is None or (isinstance(value, (str, list, dict)) and not value)


def without_empty(value):
    """``value`` without null, empty text, empty lists and empty objects, at every depth."""
    if isinstance(value, dict):
        kept = {key: without_empty(item) for key, item in value.items()}
        return {key: item for key, item in kept.items() if not _dropped(item)}
    if isinstance(value, list):
        return [without_empty(item) for item in value]
    return value


def compact_result(value):
    """A tool result as compact JSON text: null, empty text, lists and objects left out."""
    from pydantic_core import to_jsonable_python

    plain = without_empty(to_jsonable_python(value, fallback=str))
    return json.dumps(plain, separators=(",", ":"), ensure_ascii=False)


def _tool(op):
    """The MCP tool of an operation: flat arguments, and how to split them into parameters."""
    scalars, model = {}, None
    for parameter in list(inspect.signature(op.fn, eval_str=True).parameters.values())[1:]:
        annotation, base = _plain(parameter.annotation)
        if isinstance(base, type) and issubclass(base, BaseModel):
            model = (parameter.name, base)
        else:
            empty = parameter.default is inspect.Parameter.empty
            scalars[parameter.name] = (annotation, ... if empty else parameter.default)
    arguments = create_model(
        f"{op.name}Arguments", __base__=(model[1], _Arguments) if model else _Arguments, **scalars
    )

    def split(values):
        kwargs = {name: getattr(values, name) for name in scalars}
        if model:
            name, cls = model
            fields = values.model_fields_set & cls.model_fields.keys()
            kwargs[name] = cls.model_construct(
                fields, **{key: getattr(values, key) for key in cls.model_fields}
            )
        return kwargs

    schema = compact_schema(arguments.model_json_schema())
    # Path identifiers first, then the fields of the body or query.
    order = [*scalars, *(name for name in schema["properties"] if name not in scalars)]
    schema["properties"] = {name: schema["properties"][name] for name in order}
    # Only the hints that differ from MCP's defaults (not read-only, destructive, open world).
    hints = ToolAnnotations(
        readOnlyHint=op.access == READ or None,
        destructiveHint=False if op.access == WRITE else None,
        openWorldHint=False if not op.open_world else None,
    )
    tool = Tool(
        fn=print,
        name=op.name,
        description=f"{op.summary} {op.description}".strip(),
        parameters=schema,
        fn_metadata=FuncMetadata(arg_model=arguments),
        is_async=inspect.iscoroutinefunction(op.fn),
        annotations=hints,
    )
    return tool, split


def bind_mcp(mcp, workspace):
    """Add the tool of every operation on MCP; ``ws`` is ``workspace``.

    An owner-only or REST-only operation is remembered with its route (and the
    tools that cover it), so a call by its name is answered with where to go.
    """
    mcp.owner_only, mcp.rest_only = {}, {}
    for op in OPERATIONS:
        if op.access == OWNER:
            mcp.owner_only[op.name] = f"{op.method} {API_PREFIX}{op.path}"
            continue
        if op.covered_by:
            mcp.rest_only[op.name] = op.covered_by
            continue
        op.tool = op.tool or _tool(op)
        tool, split = op.tool
        if tool.is_async:

            async def call(arguments, fn=op.fn, split=split):
                return compact_result(await fn(workspace, **split(arguments)))

        else:

            def call(arguments, fn=op.fn, split=split):
                return compact_result(fn(workspace, **split(arguments)))

        mcp.add_built_tool(tool.model_copy(update={"fn": call}))


def capability_entries():
    """One ``{name, method, path, access}`` entry per operation, relative to ``/api/v1``;
    a REST-only operation names the MCP tools that do its work (``mcp``)."""
    return [
        {"name": op.name, "method": op.method, "path": op.path, "access": op.access}
        | ({"mcp": ", ".join(op.covered_by)} if op.covered_by else {})
        for op in OPERATIONS
    ]
