"""Operations of the installation: owner-only tokens, password and kept backups (REST only),
and the backup and export grants an agent may reserve. The streamed bytes are transport."""

from typing import Literal

from fastapi import Response
from pydantic import Field

from .. import backups
from ..auth import COOKIE
from ..models import Input
from ..responses import BackupList, Deleted, OperationGrant, PasswordChanged, Token, TokenList
from .core import absolute, with_curl
from .operation import OWNER, WS, operation


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=1024)


class PasswordChange(PasswordInput):
    current_password: str = Field(min_length=1, max_length=1024)


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["owner", "agent"] = Field(
        default="agent",
        description="agent (the default) is scoped: it cannot change the owner password, manage tokens or restore a backup; owner has full access.",
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the token without its secret, which is shown only once.",
    )


def grant(ws, operation):
    """A two-minute grant for one streamed download (GET /backup or GET /export)."""
    return {
        "url": "/api/v1/" + operation,
        "method": "GET",
        "headers": {"X-Operational-Token": ws.auth.operation_ticket(operation)},
        "expires_in": 120,
    }


@operation("POST /backup/grant", tags=["workspace"])
def workspace_backup(ws: WS) -> OperationGrant:
    """Reserve a backup download; take one before any permanent bulk clean-up.

    A two-minute GET grant (curl line given). An agent's copy holds no credentials.
    """
    return with_curl(grant(ws, "backup"), "openings-backup.sqlite")


@operation("POST /export/grant", access=OWNER, tags=["owner"])
def workspace_export(ws: WS) -> OperationGrant:
    """Reserve a records export (owner only).

    A two-minute GET grant for the JSON records, without file bytes or credentials.
    """
    return absolute(grant(ws, "export"))


@operation("POST /auth/password", access=OWNER, tags=["owner"])
def owner_password_update(ws: WS, body: PasswordChange, response: Response) -> PasswordChanged:
    """Change the owner password, giving the current one.

    Signs out every browser session; API and MCP tokens stay valid.
    """
    result = ws.auth.change_password(body.current_password, body.password)
    response.delete_cookie(COOKIE, path="/")
    return result


@operation("GET /tokens", access=OWNER, tags=["owner"])
def tokens_list(ws: WS) -> TokenList:
    """List API tokens.

    Names, kinds and use; secrets are never returned.
    """
    return ws.auth.list_tokens()


@operation("POST /tokens", access=OWNER, tags=["owner"])
def tokens_create(ws: WS, body: TokenInput) -> Token:
    """Create an API token.

    A named agent (scoped, the default) or owner token. Its secret is returned only once.
    """
    return ws.auth.create_token(body.name, body.kind, body.idempotency_key)


@operation("DELETE /tokens/{token_id}", access=OWNER, tags=["owner"])
def tokens_revoke(ws: WS, token_id: str) -> Deleted:
    """Revoke an API token.

    Including the token making the request; an unknown id is 404.
    """
    return ws.auth.revoke_token(token_id)


@operation("GET /backups", access=OWNER, tags=["owner"])
def backups_list(ws: WS) -> BackupList:
    """List kept backups.

    Scheduled backups and pre-upgrade copies, with the schedule and its last result.
    """
    status = backups.status(ws.db)
    items = backups.listing(ws.db)
    keys = ("enabled", "keep", "last_at", "age_hours", "ok", "last_attempt")
    schedule = {key: status[key] for key in keys} | {"interval_hours": backups.INTERVAL_HOURS}
    return {"items": items, "total": len(items), "schedule": schedule}


@operation("DELETE /backups/{name}", access=OWNER, tags=["owner"])
def backups_delete(ws: WS, name: str) -> Deleted:
    """Delete a pre-upgrade copy.

    Scheduled backups rotate by themselves.
    """
    return backups.delete_pre_upgrade(ws.db, name)
