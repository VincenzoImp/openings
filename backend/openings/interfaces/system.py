"""Installation routes and tools: sign-in, tokens, inventory, backup, restore and export."""

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

from .. import __version__
from ..actors import current_actor, require_owner
from ..auth import COOKIE, MAX_AGE
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


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=1024)


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["owner", "agent"] = Field(
        default="owner",
        description="owner has full access; agent cannot change the owner password, manage tokens, restore a backup, answer questions for the owner or write requests for the agent.",
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
        path = Path(__file__).parent.with_name("operation-inventory.json")
        return {**json.loads(path.read_text()), "version": __version__}

    router.add_api_route("/capabilities", capabilities, methods=["GET"])

    mcp.tool(
        name="capabilities_get",
        description="Read the logical operation matrix, REST routes, MCP tools and dashboard locations.",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    )(capabilities)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def tokens_list() -> dict:
        """List installation API/MCP token metadata with each token's kind; stored token secrets are never returned. Owner only: an agent token is refused with forbidden."""
        return auth.list_tokens()

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def token_create(value: TokenInput) -> dict:
        """Create a named API/MCP token of kind owner (full access, the default) or agent (scoped). Save its secret; it is returned only once. Owner only: an agent token is refused with forbidden."""
        return auth.create_token(value.name, value.kind)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def token_revoke(token_id: str) -> dict:
        """Revoke an API/MCP token, including the current token if selected. Owner only: an agent token is refused with forbidden."""
        return auth.revoke_token(token_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def owner_password_update(value: PasswordInput) -> dict:
        """Change the owner password and invalidate all browser sessions; API/MCP tokens remain valid. Owner only: an agent token is refused with forbidden."""
        return auth.change_password(value.password)

    @router.get("/tokens")
    def tokens():
        return auth.list_tokens()

    @router.post("/tokens")
    def token(value: TokenInput):
        return auth.create_token(value.name, value.kind)

    @router.delete("/tokens/{token_id}")
    def revoke(token_id: str):
        return auth.revoke_token(token_id)

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

    @router.get("/examples")
    def examples():
        names = ["career.json", "policy.json", "resume.tex", "cover-letter.tex"]
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
        if name not in {"career.json", "policy.json", "resume.tex", "cover-letter.tex"}:
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
                "job_signals": ["required", "welcome", "distinct_from", "rules"],
                "postings": ["payload"],
                "applications": ["questions", "answers", "requirements"],
                "events": ["payload"],
                "runs": ["report", "change_counts"],
                "questions": ["choices"],
                "knowledge": ["metadata", "dates", "skills"],
                "claims": ["metadata"],
                "policy_items": ["value", "rule"],
                "templates": ["rules"],
                "documents": ["content"],
                "sources": ["config", "schedule"],
                "providers": ["policy", "runtime"],
            }
            tables = [
                "jobs",
                "job_signals",
                "postings",
                "applications",
                "responses",
                "notes",
                "events",
                "runs",
                "questions",
                "requests",
                "knowledge",
                "claims",
                "templates",
                "policy_sections",
                "policy_items",
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
                    "SELECT key,data FROM settings WHERE key IN ('profile','instructions','collection')"
                ):
                    data = json.loads(row["data"])
                    settings[row["key"]] = redact_secrets(data)
                yield ',"settings":' + json.dumps(settings, ensure_ascii=False) + "}"

        return RecordsResponse(records())

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def workspace_export() -> dict:
        """Reserve a redacted JSON records export. File bytes and installation authentication are excluded; use backup for a full snapshot."""
        return {
            "url": "/api/v1/export",
            "method": "GET",
            "headers": {"X-Operational-Token": auth.operation_ticket("export")},
            "expires_in": 120,
        }

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def workspace_backup() -> dict:
        """Reserve a scoped HTTP download of a consistent SQLite backup, including file bytes. A backup taken with an agent token omits the owner password hash, session secret and API tokens; it still restores completely."""
        return {
            "url": "/api/v1/backup",
            "method": "GET",
            "headers": {"X-Operational-Token": auth.operation_ticket("backup")},
            "expires_in": 120,
        }

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def workspace_restore_upload() -> dict:
        """Reserve a scoped raw SQLite upload that replaces workspace data; installation authentication stays unchanged. Owner only: an agent token is refused with forbidden."""
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
