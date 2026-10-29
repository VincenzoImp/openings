"""HTTP host for shared workspace REST, MCP and the compiled dashboard."""

import asyncio
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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.background import BackgroundTask

from . import __version__
from .api import register_core, register_core_mcp
from .auth import COOKIE, MAX_AGE, Auth
from .errors import DomainError
from .models import Input
from .workspace import Workspace


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=1024)


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=100)


def error_response(error):
    return JSONResponse(
        {"error": {"code": error.code, "message": error.message, "details": error.details}},
        status_code=error.status,
    )


def create_app(database=None, start_worker=True):
    workspace = Workspace(database or os.environ.get("OPENINGS_DATABASE", "data/openings.sqlite"))
    auth = Auth(workspace)
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

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="Openings",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.workspace, app.state.auth, app.state.mcp = workspace, auth, mcp
    login_attempts = defaultdict(deque)
    semaphore = asyncio.Semaphore(24)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            path = request.url.path.rstrip("/")
            public = {
                "/api/v1/auth/session",
                "/api/v1/auth/setup",
                "/api/v1/auth/login",
                "/api/v1/transfers",
            }
            if path.startswith("/api/v1/") and path not in public:
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
            secure=request.url.scheme == "https",
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

    @router.get("/export")
    def export():
        data = {
            "version": __version__,
            "jobs": workspace.list_jobs(limit=200),
            "applications": workspace.list_applications(limit=200),
        }
        return JSONResponse(
            data, headers={"Content-Disposition": 'attachment; filename="openings-export.json"'}
        )

    register_core(router, workspace)
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
