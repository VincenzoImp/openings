"""Who is making the current change, and which call it belongs to.

REST and MCP authenticate at the HTTP boundary and set the actor for the rest of
the request; each REST request and each MCP tool call also opens a batch. Context
variables carry both to the shared services, so service methods need no actor
argument. Thread offloading used for sync REST handlers and sync MCP tools copies
the context; threads started by the worker never had one and therefore record
the system, without a batch.

A change is attributed with one actor label (``Actor.label``): ``owner`` (the
dashboard session or an owner token), ``agent:<token name>`` (an agent token) or
``system``. Rows written before 0.17 have none.
"""

import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from .errors import DomainError

TOKEN_KINDS = ("owner", "agent")
AGENT_PREFIX = "agent:"


@dataclass(frozen=True)
class Actor:
    """``kind`` is ``owner``, ``token`` or ``system``.

    A token actor carries the token id, its name and its kind (``owner`` for full
    access, ``agent`` for a scoped token) at the time of the change, so the label
    stays readable after the token is renamed or revoked.
    """

    kind: str
    id: str | None = None
    name: str | None = None
    token_kind: str | None = None

    def columns(self):
        return (self.kind, self.id, self.name, self.token_kind)

    @property
    def is_agent(self):
        """True for a scoped agent token, which has no owner authority."""
        return self.kind == "token" and self.token_kind == "agent"

    @property
    def label(self):
        """One short attribution: ``owner``, ``agent:<token name>`` or ``system``.

        The owner's session and an owner token are the owner.
        """
        if self.is_agent:
            return f"{AGENT_PREFIX}{self.name or 'token'}"
        return "owner" if self.kind in ("owner", "token") else "system"


SYSTEM = Actor("system")
OWNER = Actor("owner")
_current: ContextVar[Actor] = ContextVar("openings_actor", default=SYSTEM)
# A mutable holder per REST request or MCP tool call; its id is made on first use.
_batch: ContextVar[list | None] = ContextVar("openings_batch", default=None)


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


@contextmanager
def batch():
    """Group every change made inside the block under one batch id.

    REST opens one per request and MCP one per tool call. The id (``b_`` and a
    ULID) is made when the first change is recorded, so a read makes none.
    """
    marker = _batch.set([None])
    try:
        yield
    finally:
        _batch.reset(marker)


def current_batch():
    """The batch id of the current call, or None outside a request (worker, startup)."""
    holder = _batch.get()
    if holder is None:
        return None
    if holder[0] is None:
        holder[0] = "b_" + ulid()
    return holder[0]


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid():
    """A ULID: 48 bits of milliseconds and 80 random bits in Crockford base 32."""
    value = (time.time_ns() // 1_000_000) << 80 | int.from_bytes(os.urandom(10), "big")
    return "".join(_CROCKFORD[(value >> shift) & 31] for shift in range(125, -1, -5))


def label_of(kind=None, name=None, token_kind=None):
    """The actor label of stored actor columns; None for rows written before 0.17."""
    return Actor(kind, None, name, token_kind).label if kind else None


def from_columns(kind=None, actor_id=None, name=None, token_kind=None) -> Actor:
    return Actor(kind, actor_id, name, token_kind) if kind else SYSTEM
