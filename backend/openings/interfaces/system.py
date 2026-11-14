"""Installation routes and tools: sign-in, tokens, capabilities, backup, restore and export."""

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.background import BackgroundTask

from .. import __version__, backups
from ..actors import current_actor, require_owner
from ..auth import COOKIE, MAX_AGE
from ..db import SCHEMA_VERSION
from ..documents import DocumentService
from ..errors import DomainError
from ..models import Input
from ..operations import (
    backup_too_large,
    remove_installation_credentials,
    restore_database,
    storage_status,
)
from ..transfers import SnapshotResponse
from .registry import (
    Exemption,
    Operation,
    Param,
    Route,
    Tool,
    bind_mcp,
    bind_rest,
    capability_entries,
    renamed,
)


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=1024)


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["owner", "agent"] = Field(
        default="agent",
        description="agent (the default) is scoped; owner has full access; agent cannot change the owner password, manage tokens, restore a backup, answer questions for the owner or write requests for the agent.",
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Retrying with the same key and request returns the token without its secret, which is shown only once.",
    )


def redact_secrets(value):
    if isinstance(value, dict):
        return {
            key: redact_secrets(item)
            for key, item in value.items()
            if key.lower().replace("-", "_")
            not in {
                "api_key",
                "apikey",
                "app_key",
                "access_token",
                "api_token",
                "client_secret",
                "password",
                "token",
                "secret",
                "authorization",
                "cookie",
            }
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


class RecordsResponse(SnapshotResponse):
    """Prepare the SQLite snapshot on one thread before streaming file bytes."""

    def __init__(self, records):
        super().__init__(
            (record.encode("utf-8") for record in records),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="openings-export.json"'},
        )


def export_grant(auth):
    return {
        "url": "/api/v1/export",
        "method": "GET",
        "headers": {"X-Operational-Token": auth.operation_ticket("export")},
        "expires_in": 120,
    }


def backup_grant(auth):
    return {
        "url": "/api/v1/backup",
        "method": "GET",
        "headers": {"X-Operational-Token": auth.operation_ticket("backup")},
        "expires_in": 120,
    }


def restore_grant(auth):
    require_owner("restore a backup")
    return {
        "url": "/api/v1/backup/restore",
        "method": "POST",
        "headers": {
            "X-Operational-Token": auth.operation_ticket("restore"),
            "Content-Type": "application/vnd.sqlite3",
        },
        "expires_in": 120,
    }


READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)
REMOVE = ToolAnnotations(destructiveHint=True, openWorldHint=False)
GROUP = "Workspace access and portability"

# Hand-written routes and tools (custom) are registered in register_system: browser
# sessions and cookies, the capabilities list, and streamed backup, restore and export.
OPERATIONS = (
    Operation(
        "password.update",
        "owner_password",
        "update",
        GROUP,
        "Change owner password and rotate owner sessions",
        access="owner",
        params=(Param("value", PasswordInput),),
        call=lambda s, value: s.change_password(value.password),
        rest=(Route("POST", "/auth/password", "change_password", custom=True),),
        tool=Tool(
            REMOVE,
            "Change the owner password and invalidate all browser sessions; API/MCP tokens remain valid. Owner only: an agent token is refused with forbidden.",
        ),
    ),
    Operation(
        "workspace.capabilities",
        "capabilities",
        "get",
        "Archive",
        "Read the version, schema and each operation's route, MCP name and access",
        rest=(Route("GET", "/capabilities", "capabilities", custom=True),),
        tool=Tool(READ, custom=True),
    ),
    Operation(
        "tokens.list",
        "tokens",
        "list",
        GROUP,
        "List API token metadata and kinds",
        access="owner",
        call=lambda s: s.list_tokens(),
        rest=(Route("GET", "/tokens", "tokens"),),
        tool=Tool(
            READ,
            "List installation API/MCP token metadata with each token's kind; stored token secrets are never returned. Owner only: an agent token is refused with forbidden.",
        ),
    ),
    Operation(
        "tokens.create",
        "tokens",
        "create",
        GROUP,
        "Create a named owner or agent API token",
        access="owner",
        params=(Param("value", TokenInput),),
        call=lambda s, value: s.create_token(value.name, value.kind, value.idempotency_key),
        rest=(Route("POST", "/tokens", "token"),),
        tool=Tool(
            WRITE,
            "Create a named API/MCP token of kind owner (full access, the default) or agent (scoped). Save its secret; it is returned only once. Owner only: an agent token is refused with forbidden.",
        ),
    ),
    Operation(
        "tokens.revoke",
        "tokens",
        "revoke",
        GROUP,
        "Revoke an API token",
        access="owner",
        params=(Param("token_id", str),),
        call=lambda s, token_id: s.revoke_token(token_id),
        rest=(Route("DELETE", "/tokens/{token_id}", "revoke"),),
        tool=Tool(
            REMOVE,
            "Revoke an API/MCP token, including the current token if selected. Owner only: an agent token is refused with forbidden.",
        ),
    ),
    Operation(
        "backup.download",
        "workspace",
        "backup",
        GROUP,
        "Download a consistent SQLite backup including bytes",
        call=backup_grant,
        rest=(Route("GET", "/backup", "backup", custom=True),),
        tool=Tool(
            READ,
            "Reserve a scoped HTTP download of a consistent SQLite backup, including file bytes. A backup taken with an agent token omits the owner password hash, session secret and API tokens; it still restores completely.",
        ),
    ),
    Operation(
        "backup.restore",
        "workspace",
        "restore",
        GROUP,
        "Replace workspace data from a SQLite backup",
        access="owner",
        call=restore_grant,
        rest=(Route("POST", "/backup/restore", "restore", custom=True),),
        tool=Tool(
            REMOVE,
            "Reserve a scoped raw SQLite upload that replaces workspace data; installation authentication stays unchanged. Owner only: an agent token is refused with forbidden.",
        ),
    ),
    # Kept copies hold the whole workspace, including the password hash, the session
    # secret and token hashes: owner-only REST, never an MCP tool.
    Operation(
        "backups.list",
        "backups",
        "list",
        GROUP,
        "List scheduled backups and pre-upgrade copies",
        access="owner",
        rest=(Route("GET", "/backups", "backups", custom=True),),
    ),
    Operation(
        "backups.download",
        "backups",
        "download",
        GROUP,
        "Download a scheduled backup or a pre-upgrade copy",
        access="owner",
        rest=(Route("GET", "/backups/{name}", "backup_file", custom=True),),
    ),
    Operation(
        "backups.delete",
        "backups",
        "delete",
        GROUP,
        "Delete a pre-upgrade copy",
        access="owner",
        rest=(Route("DELETE", "/backups/{name}", "delete_backup_file", custom=True),),
    ),
    Operation(
        "export.records",
        "workspace",
        "export",
        GROUP,
        "Download portable JSON records without file bytes",
        call=export_grant,
        rest=(Route("GET", "/export", "export", custom=True),),
        tool=Tool(
            READ,
            "Reserve a redacted JSON records export. File bytes and installation authentication are excluded; use backup for a full snapshot.",
        ),
    ),
)

EXEMPTIONS = (
    Exemption(
        "auth.bootstrap_session",
        "Credential bootstrap and browser session transport precede authenticated domain tools; MCP uses bearer authentication. Logout revokes every browser session; API/MCP tokens remain valid.",
        rest=(
            Route("GET", "/auth/session", "session", custom=True),
            Route("POST", "/auth/setup", "setup", custom=True),
            Route("POST", "/auth/login", "login", custom=True),
            Route("POST", "/auth/logout", "logout", custom=True),
        ),
    ),
    Exemption(
        "health.deployment",
        "Deployment liveness and service installation/startup are transport or operator concerns, not domain CRUD.",
        rest=(Route("GET", "/health", "health", custom=True, absolute=True),),
    ),
    Exemption(
        "mcp.transport",
        "MCP initialization/discovery/session/resource transport is protocol infrastructure; no simulated dashboard button or MCP wrapper is required.",
        rest=(
            Route("POST", "/mcp/", "mcp", custom=True, absolute=True),
            Route("GET", "/mcp/", "mcp", custom=True, absolute=True),
            Route("DELETE", "/mcp/", "mcp", custom=True, absolute=True),
        ),
    ),
    Exemption(
        "reference.examples",
        "Shipped static reference files are convenience downloads, not private workspace records; agents may use REST or repository examples.",
        rest=(
            Route("GET", "/examples", "examples", custom=True),
            Route("GET", "/examples/{name}", "example_file", custom=True),
        ),
    ),
)


def register_system(router, mcp, workspace, auth, public_url):
    def session_state(request):
        session = auth.session(request)
        return {
            "configured": auth.configured(),
            "authenticated": bool(session),
            "csrf_token": session["csrf"] if session else None,
        }

    @router.get("/auth/session")
    def session(request: Request):
        return session_state(request)

    def signed_in(request, password, setup=False):
        if setup:
            auth.setup(password)
        token, session = auth.login(password)
        response = JSONResponse(
            {"configured": True, "authenticated": True, "csrf_token": session["csrf"]}
        )
        response.set_cookie(
            COOKIE,
            token,
            max_age=MAX_AGE,
            httponly=True,
            secure=request.url.scheme == "https" or public_url.startswith("https://"),
            samesite="strict",
            path="/",
        )
        return response

    @router.post("/auth/setup")
    def setup(request: Request, value: PasswordInput):
        return signed_in(request, value.password, True)

    @router.post("/auth/login")
    def login(request: Request, value: PasswordInput):
        return signed_in(request, value.password)

    @router.post("/auth/logout")
    def logout():
        response = JSONResponse(auth.logout())
        response.delete_cookie(COOKIE, path="/")
        return response

    @router.post("/auth/password")
    def change_password(value: PasswordInput):
        response = JSONResponse(auth.change_password(value.password))
        response.delete_cookie(COOKIE, path="/")
        return response

    def capabilities() -> dict:
        from . import catalog  # The areas import this module.

        actor = current_actor()
        return {
            "version": __version__,
            "schema": SCHEMA_VERSION,
            "token_kind": actor.token_kind or ("session" if actor.kind == "owner" else None),
            "api_base": "/api/v1",
            "operations": capability_entries(catalog()[0]),
        }

    router.add_api_route("/capabilities", capabilities, methods=["GET"])

    mcp.tool(
        name="capabilities_get",
        description="Read the version, the schema, this token's kind and each operation's MCP name and main REST route; access is owner on owner-only operations. Use tools/list for tool schemas.",
        annotations=READ,
    )(renamed(capabilities, "capabilities_get"))

    bind_rest(router, OPERATIONS, auth)
    bind_mcp(mcp, OPERATIONS, auth)

    @router.get("/backup")
    def backup():
        name = workspace.db.temp_file("backup")
        try:
            workspace.db.backup(name)
            if current_actor().is_agent:
                # An agent may back up before broad changes, but never receives the
                # password hash, the session secret or the tokens of the installation.
                remove_installation_credentials(name)
        except BaseException:
            workspace.db.remove_temp(name)
            raise
        return FileResponse(
            name,
            media_type="application/vnd.sqlite3",
            filename="openings-backup.sqlite",
            background=BackgroundTask(workspace.db.remove_temp, name),
        )

    @router.post("/backup/restore")
    async def restore(request: Request):
        require_owner("restore a backup")
        # Refuse before writing anything when the declared size cannot fit.
        status = storage_status(workspace.db)
        limit = status["restore_limit_bytes"]
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise backup_too_large(int(declared), status)
        name = workspace.db.temp_file("restore")
        count = 0
        try:
            with open(name, "wb") as upload:  # noqa: ASYNC230 - local temp file, bounded chunks
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > limit:
                        raise backup_too_large(count, status)
                    upload.write(chunk)
            with open(name, "rb") as check_file:  # noqa: ASYNC230 - 16-byte local read
                header = check_file.read(16)
            if header != b"SQLite format 3\x00":
                raise DomainError(422, "backup_format", "Select a SQLite database backup.")
            workspace.maintenance = True
            try:
                result = await asyncio.to_thread(restore_database, workspace, name)
                workspace.event("workspace_restored", subject=("workspace", "backup"))
                # Other jobs now: build the duplicate index and missing signals again.
                workspace.reset_duplicates()
                workspace.warm_duplicates()
                return result
            except sqlite3.DatabaseError:
                raise DomainError(422, "backup_format", "This database backup could not be read.")
        finally:
            workspace.maintenance = False
            workspace.db.remove_temp(name)

    @router.get("/backups")
    def backup_files():
        require_owner("list the kept backups")
        status = backups.status(workspace.db)
        items = backups.listing(workspace.db)
        return {
            "items": items,
            "total": len(items),
            "schedule": {
                "enabled": status["enabled"],
                "keep": status["keep"],
                "interval_hours": backups.INTERVAL_HOURS,
                "last_at": status["last_at"],
                "age_hours": status["age_hours"],
                "ok": status["ok"],
                "last_attempt": status["last_attempt"],
            },
        }

    @router.get("/backups/{name}")
    def backup_file(name: str):
        require_owner("download a kept backup")
        _, path = backups.find(workspace.db, name)
        return FileResponse(path, media_type="application/vnd.sqlite3", filename=path.name)

    @router.delete("/backups/{name}")
    def delete_backup_file(name: str):
        require_owner("delete a pre-upgrade copy")
        return backups.delete_pre_upgrade(workspace.db, name)

    @router.get("/examples")
    def examples():
        names = ["career.json", "preferences.json", "cv.tex", "letter.tex"]
        directory = Path(
            os.environ.get("OPENINGS_EXAMPLES", Path(__file__).resolve().parents[3] / "examples")
        )
        return {
            "items": [
                {"name": name, "url": "/api/v1/examples/" + name}
                for name in names
                if (directory / name).is_file()
            ]
        }

    @router.get("/examples/{name}")
    def example_file(name: str):
        if name not in {"career.json", "preferences.json", "cv.tex", "letter.tex"}:
            raise DomainError(404, "not_found", "Example not found.")
        path = (
            Path(
                os.environ.get(
                    "OPENINGS_EXAMPLES", Path(__file__).resolve().parents[3] / "examples"
                )
            )
            / name
        )
        if not path.is_file():
            raise DomainError(404, "not_found", "Example not found.")
        return FileResponse(path, filename=name)

    @router.get("/export")
    def export():
        def records():
            json_fields = {
                "jobs": ["metadata", "overrides"],
                "job_signals": ["required", "welcome", "distinct_from"],
                "postings": ["payload"],
                "applications": ["questions", "answers", "requirements", "required_documents"],
                "events": ["payload"],
                "runs": ["report", "change_counts"],
                "questions": ["choices"],
                "knowledge": ["metadata", "dates", "skills"],
                "claims": ["metadata"],
                "preference_sections": ["items"],
                "templates": ["rules"],
                "documents": ["content", "legacy_content", "claim_ids", "knowledge_ids"],
                "sources": ["config", "schedule"],
                "providers": ["policy", "runtime"],
            }
            tables = [
                "jobs",
                "job_signals",
                "postings",
                "applications",
                "replies",
                "notes",
                "events",
                "runs",
                "questions",
                "requests",
                "knowledge",
                "claims",
                "templates",
                "preference_sections",
                "skill_notes",
                "contexts",
                "documents",
                "files",
                "sources",
                "providers",
            ]
            yield '{"format":"openings-records-v1","files_include_bytes":false'
            with workspace.db.connect() as conn:
                conn.execute("BEGIN")
                for table in tables:
                    yield ',"' + table + '":['
                    first = True
                    # Context files are served from snapshot parts; payloads are rebuilt.
                    source = "all_files" if table == "files" else table
                    for row in conn.execute("SELECT * FROM " + source):
                        item = dict(row)
                        if table == "contexts":
                            item = DocumentService.context_record(conn, row)
                            del item["resource_uri"]
                        for key in json_fields.get(table, []):
                            if item[key] is not None:
                                item[key] = json.loads(item[key])
                        if table == "sources":
                            item["config"] = redact_secrets(item["config"])
                        yield ("" if first else ",") + json.dumps(item, ensure_ascii=False)
                        first = False
                    yield "]"
                settings = {}
                for row in conn.execute(
                    "SELECT key,data FROM settings WHERE key IN ('profile','workspace','collection')"
                ):
                    data = json.loads(row["data"])
                    settings[row["key"]] = redact_secrets(data)
                yield ',"settings":' + json.dumps(settings, ensure_ascii=False) + "}"

        return RecordsResponse(records())
