"""HTTP host for shared workspace REST, MCP and the compiled dashboard."""

import asyncio
import base64
import hashlib
import os
import re
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings

from . import __version__
from .actors import SYSTEM, acting_as, batch
from .auth import Auth, LoginGuard
from .career import CareerService
from .context import ContextService
from .discovery import DiscoveryService
from .documents import DocumentService
from .errors import DomainError
from .events import EventLog
from .interfaces import bind_mcp, bind_rest, register_prompts, register_transport
from .interfaces.operation import request_origin
from .limits import REQUEST_LIMIT, BodyLimit
from .mcp_server import INSTRUCTIONS, OpeningsMCP
from .openapi import build as build_openapi, errors
from .preferences import PreferencesService
from .skills import SkillLibrary
from .stats import StatsService
from .worker import Worker
from .workspace import Workspace

# The dashboard runs only its own scripts, styles, fonts and frames; the inline
# style elements of index.html are allowed by their hashes (``dashboard_policy``).
DASHBOARD_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'{styles}; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
)
# API answers are data: nothing in them may run or be framed. A file's content sets
# its own sandboxed policy, which the dashboard's preview may frame.
API_POLICY = "default-src 'none'; frame-ancestors 'none'"
STYLE = re.compile(r"<style>(.*?)</style>", re.DOTALL)


def dashboard_policy(index):
    """The dashboard's Content-Security-Policy, with the hash of each inline style."""
    text = index.read_text(encoding="utf-8") if index.is_file() else ""
    hashes = "".join(
        " 'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
        for body in STYLE.findall(text)
    )
    return DASHBOARD_POLICY.format(styles=hashes)


def protect(response, path, dashboard):
    """The security headers of every answer, an early refusal included."""
    api = path.startswith(("/api", "/mcp"))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store" if api else "no-cache"
    # The interactive API reference (/api/docs) loads its own scripts.
    if path.startswith(("/api/v1", "/mcp")):
        response.headers.setdefault("Content-Security-Policy", API_POLICY)
    elif not api:
        response.headers.setdefault("Content-Security-Policy", dashboard)
    return response


def error_response(error):
    retry = error.details.get("retry_after_seconds") if isinstance(error.details, dict) else None
    body = {
        "code": error.code,
        "status": error.status,
        "message": error.message,
        "details": error.details,
    }
    return JSONResponse(
        {"error": body},
        status_code=error.status,
        headers={"Retry-After": str(retry)} if retry else None,
    )


def create_app(database=None, start_worker=True, demo=False):
    """The application of one workspace.

    ``demo`` (``openings demo``) serves a disposable demo workspace: its provider gate
    is closed, its printed link signs in once, and the session, ``/health``,
    ``workspace_context`` and the workspace info say ``demo``.
    """
    workspace = Workspace(database or os.environ.get("OPENINGS_DATABASE", "data/openings.sqlite"))
    workspace.maintenance = False
    workspace.demo = demo
    auth = Auth(workspace)
    career = CareerService(workspace)
    documents = DocumentService(workspace)
    discovery = DiscoveryService(workspace)
    discovery.providers.closed = demo
    events = EventLog(workspace)
    preferences = PreferencesService(workspace)
    stats = StatsService(workspace)
    workspace.discovery = discovery
    workspace.worker = Worker(workspace, discovery) if start_worker else None
    allowed_hosts = ["localhost:*", "127.0.0.1:*", "[::1]:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*"]
    public_url = os.environ.get("OPENINGS_PUBLIC_URL", "").rstrip("/")
    if public_url:
        allowed_hosts.append(urlsplit(public_url).netloc)
        origins.append(public_url)
    # Tools, prompts and resources never change at runtime, so no notification
    # stream is offered: every exchange stays one request and one JSON response.
    mcp = OpeningsMCP(
        "Openings", version=__version__, instructions=INSTRUCTIONS, subscriptions=False
    )
    skills = SkillLibrary()
    # Operations receive the workspace with its services (interfaces/operation.py).
    workspace.auth, workspace.career, workspace.documents = auth, career, documents
    workspace.events, workspace.preferences, workspace.stats = events, preferences, stats
    workspace.skills = skills
    workspace.context = ContextService(workspace)
    bind_mcp(mcp, workspace)
    register_prompts(mcp, skills)

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            if workspace.worker:
                workspace.worker.start()
                # After the health check has had time to pass.
                workspace.warm_duplicates(delay=5)
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
    app.state.events, app.state.preferences, app.state.stats = events, preferences, stats
    app.state.skills = skills
    app.openapi = lambda: build_openapi(app)
    app.add_middleware(BodyLimit)
    # The client address is the real one only when uvicorn trusts the proxy
    # (OPENINGS_TRUSTED_PROXIES); otherwise every proxied client shares one bucket.
    login_guard = app.state.login_guard = LoginGuard()
    semaphore = asyncio.Semaphore(24)
    static = Path(
        os.environ.get(
            "OPENINGS_FRONTEND", Path(__file__).resolve().parents[2] / "frontend" / "dist"
        )
    )
    dashboard_csp = dashboard_policy(static / "index.html")

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        path = request.url.path.rstrip("/")
        try:
            if workspace.maintenance and path.startswith(("/api/v1", "/mcp")):
                raise DomainError(
                    503, "restoring", "A workspace restore is in progress. Retry shortly."
                )
            public = {
                "/api/v1/auth/session",
                "/api/v1/auth/setup",
                "/api/v1/auth/login",
                "/api/v1/auth/demo",
                "/api/v1/transfers",
            }
            actor = SYSTEM
            if path.startswith("/api/v1/") and path not in public:
                if path in {"/api/v1/backup", "/api/v1/export"} and request.headers.get(
                    "x-operational-token"
                ):
                    # A grant of workspace_backup or workspace_export, for one GET.
                    operation = path.removeprefix("/api/v1/") if request.method == "GET" else ""
                    actor = auth.authorize_operation(
                        request.headers["x-operational-token"], operation
                    )
                else:
                    actor = auth.authorize(request)
            if path.startswith("/mcp"):
                actor = auth.authorize(request, mcp=True)
            sign_in = path == "/api/v1/auth/login" and request.method == "POST"
            if path.startswith("/api/v1/auth/") and request.method == "POST" and path in public:
                if not request.headers.get("content-type", "").startswith("application/json"):
                    raise DomainError(415, "content_type", "Send JSON request data.")
                ip = request.client.host if request.client else "unknown"
                wait = login_guard.admit(ip, login=sign_in)
                if wait:
                    await asyncio.sleep(wait)
            if int(
                request.headers.get("content-length", 0) or 0
            ) > REQUEST_LIMIT and not path.endswith("/restore"):
                raise DomainError(413, "request_size", "This request exceeds the upload limit.")
            # Route the advertised URL directly to the mounted transport without a redirect.
            if request.scope["path"] == "/mcp":
                request.scope["path"] = "/mcp/"
                request.scope["raw_path"] = request.scope.get("raw_path", b"/mcp") + b"/"
            # Handlers, offloaded threads and MCP tools inherit the actor from this context.
            # Every change of one request shares one batch id.
            origin = request_origin.set(str(request.base_url).rstrip("/"))
            try:
                with acting_as(actor), batch():
                    async with semaphore:
                        response = await call_next(request)
            finally:
                request_origin.reset(origin)
            if sign_in:
                if response.status_code == 401:
                    login_guard.failed()
                elif response.status_code == 200:
                    login_guard.succeeded()
            return protect(response, path, dashboard_csp)
        except DomainError as error:
            return protect(error_response(error), path, dashboard_csp)

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

    # Routes go on the application's own router: an included router would build
    # every route a second time on the first request.
    register_transport(app, app.router, public_url)
    bind_rest(app.router, errors)
    # Building the transport also creates the session manager the lifespan runs.
    app.mount(
        "/mcp",
        mcp.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                allowed_hosts=allowed_hosts, allowed_origins=origins
            ),
        ),
    )

    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
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
