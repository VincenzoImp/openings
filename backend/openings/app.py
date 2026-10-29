"""HTTP host for shared workspace REST, MCP and the compiled dashboard."""

import asyncio
import json
import os
import sqlite3
import tempfile
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.background import BackgroundTask

from . import __version__
from .api import register_core, register_core_mcp
from .auth import COOKIE, MAX_AGE, Auth
from .career import (
    CareerService,
    register_api as register_career_api,
    register_mcp as register_career_mcp,
)
from .documents import (
    DocumentService,
    register_api as register_document_api,
    register_mcp as register_document_mcp,
)
from .errors import DomainError
from .discovery import (
    DiscoveryService,
    register_api as register_discovery_api,
    register_mcp as register_discovery_mcp,
)
from .worker import Worker
from .models import Input
from .operations import restore_database
from .workspace import Workspace


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=1024)


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=100)


def redact_secrets(value):
    if isinstance(value, dict):
        return {
            key: redact_secrets(item)
            for key, item in value.items()
            if key.lower().replace("-", "_")
            not in {"api_key", "apikey", "password", "token", "secret", "authorization", "cookie"}
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def error_response(error):
    return JSONResponse(
        {"error": {"code": error.code, "message": error.message, "details": error.details}},
        status_code=error.status,
    )


def create_app(database=None, start_worker=True):
    workspace = Workspace(database or os.environ.get("OPENINGS_DATABASE", "data/openings.sqlite"))
    workspace.maintenance = False
    auth = Auth(workspace)
    career = CareerService(workspace)
    documents = DocumentService(workspace)
    discovery = DiscoveryService(workspace)
    workspace.discovery = discovery
    workspace.worker = Worker(workspace, discovery) if start_worker else None
    allowed_hosts = ["localhost:*", "127.0.0.1:*", "[::1]:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*"]
    public_url = os.environ.get("OPENINGS_PUBLIC_URL", "").rstrip("/")
    if public_url:
        allowed_hosts.append(urlsplit(public_url).netloc)
        origins.append(public_url)
    mcp = FastMCP(
        "Openings",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            allowed_hosts=allowed_hosts, allowed_origins=origins
        ),
    )
    register_core_mcp(mcp, workspace)
    register_career_mcp(mcp, career)
    register_document_mcp(mcp, documents)
    register_discovery_mcp(mcp, discovery)

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            if workspace.worker:
                workspace.worker.start()
            try:
                yield
            finally:
                if workspace.worker:
                    workspace.worker.stop()

    app = FastAPI(
        title="Openings",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.workspace, app.state.auth, app.state.mcp = workspace, auth, mcp
    app.state.career, app.state.documents, app.state.discovery = career, documents, discovery
    login_attempts = defaultdict(deque)
    semaphore = asyncio.Semaphore(24)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            path = request.url.path.rstrip("/")
            if workspace.maintenance and path.startswith(("/api/v1", "/mcp")):
                raise DomainError(
                    503, "restoring", "A workspace restore is in progress. Retry shortly."
                )
            public = {
                "/api/v1/auth/session",
                "/api/v1/auth/setup",
                "/api/v1/auth/login",
                "/api/v1/transfers",
            }
            if path.startswith("/api/v1/") and path not in public:
                if path in {
                    "/api/v1/backup",
                    "/api/v1/backup/restore",
                    "/api/v1/export",
                } and request.headers.get("x-operational-token"):
                    operation = (
                        "export"
                        if path == "/api/v1/export" and request.method == "GET"
                        else "backup"
                        if path == "/api/v1/backup" and request.method == "GET"
                        else "restore"
                        if path.endswith("/restore") and request.method == "POST"
                        else "invalid"
                    )
                    auth.authorize_operation(request.headers["x-operational-token"], operation)
                else:
                    auth.authorize(request)
            if path.startswith("/mcp"):
                auth.authorize(request, mcp=True)
            if path.startswith("/api/v1/auth/") and request.method == "POST" and path in public:
                if not request.headers.get("content-type", "").startswith("application/json"):
                    raise DomainError(415, "content_type", "Send JSON request data.")
                ip = request.client.host if request.client else "unknown"
                attempts = login_attempts[ip]
                stamp = time.monotonic()
                while attempts and attempts[0] < stamp - 60:
                    attempts.popleft()
                if len(attempts) >= 10:
                    raise DomainError(
                        429, "login_rate", "Too many attempts. Try again in a minute."
                    )
                attempts.append(stamp)
                if len(login_attempts) > 1024:
                    login_attempts.clear()
            if int(
                request.headers.get("content-length", 0) or 0
            ) > 40 * 1024**2 and not path.endswith("/restore"):
                raise DomainError(413, "request_size", "This request exceeds the upload limit.")
            async with semaphore:
                response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Cache-Control"] = (
                "no-store" if path.startswith(("/api", "/mcp")) else "no-cache"
            )
            return response
        except DomainError as error:
            return error_response(error)

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = [
            {"field": list(e["loc"]), "message": e["msg"], "type": e["type"]}
            for e in error.errors()
        ]
        return error_response(
            DomainError(422, "validation", "Some fields need attention.", details)
        )

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, error):
        return error_response(
            DomainError(409, "constraint", "This change conflicts with existing workspace data.")
        )

    @app.get("/health")
    def health():
        workspace.db.one("SELECT 1")
        return {"status": "ok", "version": __version__}

    router = APIRouter(prefix="/api/v1")

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
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/")
        return response

    @router.post("/auth/password")
    def change_password(value: PasswordInput):
        response = JSONResponse(auth.change_password(value.password))
        response.delete_cookie(COOKIE, path="/")
        return response

    def capabilities():
        path = Path(__file__).with_name("operation-inventory.json")
        if not path.is_file():
            path = Path(__file__).resolve().parents[2] / "docs/next/operation-inventory.json"
        return json.loads(path.read_text())

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
        """List installation API/MCP token metadata; stored token secrets are never returned."""
        return auth.list_tokens()

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    def token_create(value: TokenInput) -> dict:
        """Create a named API/MCP token. Save its secret; it is returned only once."""
        return auth.create_token(value.name)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def token_revoke(token_id: str) -> dict:
        """Revoke an API/MCP token, including the current token if selected."""
        return auth.revoke_token(token_id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def owner_password_update(value: PasswordInput) -> dict:
        """Change the owner password and invalidate all browser sessions; API/MCP tokens remain valid."""
        return auth.change_password(value.password)

    @router.get("/tokens")
    def tokens():
        return auth.list_tokens()

    @router.post("/tokens")
    def token(value: TokenInput):
        return auth.create_token(value.name)

    @router.delete("/tokens/{token_id}")
    def revoke(token_id: str):
        return auth.revoke_token(token_id)

    @router.get("/backup")
    def backup():
        handle, name = tempfile.mkstemp(suffix=".sqlite", prefix="openings-backup-")
        os.close(handle)
        workspace.db.backup(name)
        return FileResponse(
            name,
            media_type="application/vnd.sqlite3",
            filename="openings-backup.sqlite",
            background=BackgroundTask(Path(name).unlink, missing_ok=True),
        )

    @router.post("/backup/restore")
    async def restore(request: Request):
        handle, name = tempfile.mkstemp(suffix=".sqlite", prefix="openings-restore-")
        count = 0
        try:
            with os.fdopen(handle, "wb") as upload:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > int(os.environ.get("OPENINGS_MAX_RESTORE_MB", "512")) * 1024**2:
                        raise DomainError(
                            413,
                            "backup_size",
                            "The backup exceeds this installation's restore limit.",
                        )
                    upload.write(chunk)
            with open(name, "rb") as check_file:
                header = check_file.read(16)
            if header != b"SQLite format 3\x00":
                raise DomainError(422, "backup_format", "Select a SQLite database backup.")
            workspace.maintenance = True
            try:
                return await asyncio.to_thread(restore_database, workspace, name)
            except sqlite3.DatabaseError:
                raise DomainError(422, "backup_format", "This database backup could not be read.")
        finally:
            workspace.maintenance = False
            Path(name).unlink(missing_ok=True)

    @router.get("/examples")
    def examples():
        names = ["career.json", "resume.tex", "cover-letter.tex"]
        directory = Path(
            os.environ.get("OPENINGS_EXAMPLES", Path(__file__).resolve().parents[2] / "examples")
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
        if name not in {"career.json", "resume.tex", "cover-letter.tex"}:
            raise DomainError(404, "not_found", "Example not found.")
        path = (
            Path(
                os.environ.get(
                    "OPENINGS_EXAMPLES", Path(__file__).resolve().parents[2] / "examples"
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
                "postings": ["payload"],
                "applications": ["questions", "answers"],
                "events": ["payload"],
                "knowledge": ["metadata"],
                "claims": ["metadata"],
                "templates": ["rules"],
                "contexts": ["payload"],
                "documents": ["content"],
                "sources": ["config", "schedule"],
                "assessments": ["payload"],
                "providers": ["policy", "runtime"],
            }
            tables = [
                "jobs",
                "postings",
                "applications",
                "notes",
                "events",
                "knowledge",
                "claims",
                "templates",
                "contexts",
                "documents",
                "files",
                "sources",
                "assessments",
                "providers",
            ]
            yield '{"format":"openings-records-v1","files_include_bytes":false'
            with workspace.db.connect() as conn:
                conn.execute("BEGIN")
                for table in tables:
                    yield ',"' + table + '":['
                    first = True
                    for row in conn.execute("SELECT * FROM " + table):
                        item = dict(row)
                        for key in json_fields.get(table, []):
                            item[key] = json.loads(item[key])
                        if table == "sources":
                            item["config"] = redact_secrets(item["config"])
                        yield ("" if first else ",") + json.dumps(item, ensure_ascii=False)
                        first = False
                    yield "]"
                settings = {}
                for row in conn.execute(
                    "SELECT key,data FROM settings WHERE key IN ('profile','instructions','scoring','collection')"
                ):
                    data = json.loads(row["data"])
                    settings[row["key"]] = redact_secrets(data)
                yield ',"settings":' + json.dumps(settings, ensure_ascii=False) + "}"

        return StreamingResponse(
            records(),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="openings-export.json"'},
        )

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
        """Reserve a scoped HTTP download of a consistent SQLite backup, including file bytes."""
        return {
            "url": "/api/v1/backup",
            "method": "GET",
            "headers": {"X-Operational-Token": auth.operation_ticket("backup")},
            "expires_in": 120,
        }

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    def workspace_restore_upload() -> dict:
        """Reserve a scoped raw SQLite upload that replaces workspace data; installation authentication stays unchanged."""
        return {
            "url": "/api/v1/backup/restore",
            "method": "POST",
            "headers": {
                "X-Operational-Token": auth.operation_ticket("restore"),
                "Content-Type": "application/vnd.sqlite3",
            },
            "expires_in": 120,
        }

    register_core(router, workspace)
    register_career_api(router, career)
    register_document_api(router, documents)
    register_discovery_api(router, discovery)
    app.include_router(router)
    app.mount("/mcp", mcp.streamable_http_app())

    static = Path(
        os.environ.get(
            "OPENINGS_FRONTEND", Path(__file__).resolve().parents[2] / "frontend" / "dist"
        )
    )
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}")
    def dashboard(path: str):
        if path.startswith(("api/", "mcp", "health")):
            raise DomainError(404, "not_found", "This endpoint does not exist.")
        if (static / "index.html").is_file():
            return FileResponse(static / "index.html")
        return JSONResponse(
            {
                "name": "Openings",
                "version": __version__,
                "message": "The API is running. Build the frontend or use the development server.",
                "docs": "/api/docs",
            }
        )

    return app
