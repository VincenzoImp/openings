"""Who is making the current change: the owner's dashboard session, a named API token or the system.

REST and MCP authenticate at the HTTP boundary and set the actor for the rest of
the request. A context variable carries it to the shared services, so service
methods need no actor argument. Thread offloading used for sync REST handlers and
sync MCP tools copies the context; threads started by the worker never had one
and therefore record the system.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from .errors import DomainError

UNKNOWN_LABEL = "unknown (before 0.17)"
TOKEN_KINDS = ("owner", "agent")


@dataclass(frozen=True)
class Actor:
    """``kind`` is ``owner``, ``token`` or ``system``.

    A token actor carries the token id, its name and its kind (``owner`` for full
    access, ``agent`` for a scoped token) at the time of the change, so the record
    stays readable after the token is renamed or revoked.
    """

    kind: str
    id: str | None = None
    name: str | None = None
    token_kind: str | None = None

    def columns(self):
        return (self.kind, self.id, self.name, self.token_kind)

    def describe(self):
        return describe(*self.columns())

    @property
    def is_agent(self):
        """True for a scoped agent token, which has no owner authority."""
        return self.kind == "token" and self.token_kind == "agent"


SYSTEM = Actor("system")
OWNER = Actor("owner")
_current: ContextVar[Actor] = ContextVar("openings_actor", default=SYSTEM)


def current_actor() -> Actor:
    return _current.get()


def token_actor(token_id, name, token_kind="owner") -> Actor:
    return Actor("token", token_id, name, token_kind)


def require_owner(action):
    """Refuse an owner-only operation for a scoped agent token.

    The owner's dashboard session, an owner token and the system pass. Shared
    services call this, so REST and MCP refuse alike.
    """
    if current_actor().is_agent:
        raise DomainError(
            403,
            "forbidden",
            f"An agent token cannot {action}. Use the dashboard or an owner token.",
            {"token_kind": "agent", "required": "owner"},
        )


@contextmanager
def acting_as(actor: Actor):
    """Attribute every change made inside the block to this actor."""
    marker = _current.set(actor)
    try:
        yield actor
    finally:
        _current.reset(marker)


def describe(kind, actor_id=None, name=None, token_kind=None) -> dict:
    """The actor shape returned by reads. Rows written before attribution have no kind."""
    if kind is None:
        return {
            "kind": "unknown",
            "id": None,
            "name": None,
            "token_kind": None,
            "label": UNKNOWN_LABEL,
        }
    label = {"owner": "Owner (dashboard)", "system": "System"}.get(kind) or name or "API token"
    return {"kind": kind, "id": actor_id, "name": name, "token_kind": token_kind, "label": label}


COLUMN_SUFFIXES = ("kind", "id", "name", "token_kind")


def column_names(prefix="actor"):
    """The four stored columns of an actor, in the order of ``Actor.columns()``."""
    return [f"{prefix}_{suffix}" for suffix in COLUMN_SUFFIXES]


def pop_actor(row, prefix="actor") -> dict:
    """Describe an actor stored in a dict row and remove its columns from the row."""
    return describe(*(row.pop(name) for name in column_names(prefix)))


def from_columns(kind=None, actor_id=None, name=None, token_kind=None) -> Actor:
    return Actor(kind, actor_id, name, token_kind) if kind else SYSTEM
