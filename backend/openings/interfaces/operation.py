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
fields as the REST path and body. Owner-only operations (``OWNER``) are REST only.
"""

import inspect
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
    tool: Any = None  # (Tool, split), built once and shared by every application

    @property
    def method(self):
        return self.routes[0][0]

    @property
    def path(self):
        return self.routes[0][1]


OPERATIONS: list[Operation] = []


def operation(*routes, access=READ, tags=(), status=None, open_world=False):
    """Declare an operation on ``"METHOD /path"`` (a second route is a REST alias)."""

    def register(fn):
        summary, _, rest = inspect.getdoc(fn).partition("\n")
        pairs = [tuple(route.split(" ", 1)) for route in routes]
        flags = (access, list(tags), status, open_world)
        OPERATIONS.append(
            Operation(fn.__name__, pairs, fn, *flags, summary, " ".join(rest.split()))
        )
        return fn

    return register


def bind_rest(router, errors):
    """Add every operation's routes; ``errors(op, path)`` gives its documented errors."""
    for op in OPERATIONS:
        action = op.summary[0].lower() + op.summary[1:].rstrip(".")
        for index, (method, path) in enumerate(op.routes):
            name = op.name if index == 0 else f"{op.name}_{index}"
            router.add_api_route(
                path,
                op.fn,
                methods=[method],
                name=name,
                operation_id=name,
                summary=op.summary,
                description=op.description,
                tags=op.tags,
                responses=errors(op, path),
                response_model_exclude_unset=True,
                dependencies=[Depends(lambda a=action: require_owner(a))]
                if op.access == OWNER
                else None,
                openapi_extra={"x-openings-access": op.access},
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

    schema = arguments.model_json_schema()
    # Path identifiers first, then the fields of the body or query.
    order = [*scalars, *(name for name in schema["properties"] if name not in scalars)]
    schema["properties"] = {name: schema["properties"][name] for name in order}
    hints = ToolAnnotations(
        readOnlyHint=op.access == READ,
        destructiveHint=op.access == DESTRUCTIVE,
        idempotentHint=op.access == READ or None,
        openWorldHint=op.open_world,
    )
    tool = Tool(
        fn=print,
        name=op.name,
        description=op.description or op.summary,
        parameters=schema,
        fn_metadata=FuncMetadata(arg_model=arguments),
        is_async=inspect.iscoroutinefunction(op.fn),
        annotations=hints,
    )
    return tool, split


def bind_mcp(mcp, workspace):
    """Add the tool of every operation that is not owner-only; ``ws`` is ``workspace``."""
    mcp.owner_only = {}
    for op in OPERATIONS:
        if op.access == OWNER:
            mcp.owner_only[op.name] = f"{op.method} {API_PREFIX}{op.path}"
            continue
        op.tool = op.tool or _tool(op)
        tool, split = op.tool
        if tool.is_async:

            async def call(arguments, fn=op.fn, split=split):
                return await fn(workspace, **split(arguments))

        else:

            def call(arguments, fn=op.fn, split=split):
                return fn(workspace, **split(arguments))

        mcp.add_built_tool(tool.model_copy(update={"fn": call}))


def capability_entries():
    """One ``{name, method, path, access}`` entry per operation, relative to ``/api/v1``."""
    return [
        {"name": op.name, "method": op.method, "path": op.path, "access": op.access}
        for op in OPERATIONS
    ]
