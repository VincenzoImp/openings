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

UNKNOWN_LABEL = "unknown (before 0.17)"


@dataclass(frozen=True)
class Actor:
    """``kind`` is ``owner``, ``token`` or ``system``.

    A token actor carries the token id and its name at the time of the change, so
    the record stays readable after the token is renamed or revoked. A token kind
    (owner or agent, #161) can be added here and stored next to the name.
    """

    kind: str
    id: str | None = None
    name: str | None = None

    def columns(self):
        return (self.kind, self.id, self.name)

    def describe(self):
        return describe(self.kind, self.id, self.name)


SYSTEM = Actor("system")
OWNER = Actor("owner")
_current: ContextVar[Actor] = ContextVar("openings_actor", default=SYSTEM)


def current_actor() -> Actor:
    return _current.get()


def token_actor(token_id, name) -> Actor:
    return Actor("token", token_id, name)


@contextmanager
def acting_as(actor: Actor):
    """Attribute every change made inside the block to this actor."""
    marker = _current.set(actor)
    try:
        yield actor
    finally:
        _current.reset(marker)


def describe(kind, actor_id=None, name=None) -> dict:
    """The actor shape returned by reads. Rows written before attribution have no kind."""
    if kind is None:
        return {"kind": "unknown", "id": None, "name": None, "label": UNKNOWN_LABEL}
    label = {"owner": "Owner (dashboard)", "system": "System"}.get(kind) or name or "API token"
    return {"kind": kind, "id": actor_id, "name": name, "label": label}


def describe_row(row, prefix="actor") -> dict:
    return describe(row[prefix + "_kind"], row[prefix + "_id"], row[prefix + "_name"])


def from_columns(kind, actor_id, name) -> Actor:
    return Actor(kind, actor_id, name) if kind else SYSTEM
