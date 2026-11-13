"""HTTP host for shared workspace REST, MCP and the compiled dashboard."""

import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings

from . import __version__
from .activity import ActivityService
from .actors import SYSTEM, acting_as
from .agent_requests import RequestService
from .auth import Auth, LoginGuard
from .career import CareerService
from .discovery import DiscoveryService
from .documents import DocumentService
from .errors import DomainError
from .insights import InsightsService
from .interfaces.activity import (
    register_api as register_activity_api,
    register_mcp as register_activity_mcp,
)
from .interfaces.agent_requests import (
    register_api as register_request_api,
    register_mcp as register_request_mcp,
)
from .interfaces.career import (
    register_api as register_career_api,
    register_mcp as register_career_mcp,
)
from .interfaces.core import register_core, register_core_mcp
from .interfaces.discovery import (
    register_api as register_discovery_api,
    register_mcp as register_discovery_mcp,
)
from .interfaces.documents import (
    register_api as register_document_api,
    register_mcp as register_document_mcp,
)
from .interfaces.insights import (
    register_api as register_insights_api,
    register_mcp as register_insights_mcp,
)
from .interfaces.outcomes import (
    register_api as register_response_api,
    register_mcp as register_response_mcp,
)
from .interfaces.policy import (
    register_api as register_policy_api,
    register_mcp as register_policy_mcp,
)
from .interfaces.skills import (
    register_api as register_skills_api,
    register_mcp as register_skills_mcp,
)
from .interfaces.source_yield import (
    register_api as register_yield_api,
    register_mcp as register_yield_mcp,
)
from .interfaces.system import register_system
from .limits import REQUEST_LIMIT, BodyLimit
from .mcp_server import OpeningsMCP
from .outcomes import ResponseService
from .policy import PolicyService
from .skill_notes import SkillNotesService
from .skills import SkillLibrary
from .source_yield import YieldService
from .worker import Worker
from .workspace import Workspace


def error_response(error):
    retry = error.details.get("retry_after_seconds") if isinstance(error.details, dict) else None
    return JSONResponse(
        {"error": {"code": error.code, "message": error.message, "details": error.details}},
        status_code=error.status,
        headers={"Retry-After": str(retry)} if retry else None,
    )


def create_app(database=None, start_worker=True):
    workspace = Workspace(database or os.environ.get("OPENINGS_DATABASE", "data/openings.sqlite"))
    workspace.maintenance = False
    auth = Auth(workspace)
    career = CareerService(workspace)
    documents = DocumentService(workspace)
    discovery = DiscoveryService(workspace)
    activity = ActivityService(workspace)
    requests = RequestService(workspace)
    policy = PolicyService(workspace)
    responses = ResponseService(workspace)
    insights = InsightsService(workspace)
    source_yield = YieldService(workspace)
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
    mcp = OpeningsMCP("Openings", version=__version__, subscriptions=False)
    register_core_mcp(mcp, workspace, requests)
    register_career_mcp(mcp, career)
    register_document_mcp(mcp, documents)
    register_discovery_mcp(mcp, discovery)
    register_activity_mcp(mcp, activity)
    register_request_mcp(mcp, requests)
    register_policy_mcp(mcp, policy)
    register_response_mcp(mcp, responses)
    register_insights_mcp(mcp, insights)
    register_yield_mcp(mcp, source_yield)
    skills = SkillLibrary()
    skill_notes = SkillNotesService(workspace, skills)
    register_skills_mcp(mcp, skills, skill_notes)

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
    app.state.activity, app.state.requests = activity, requests
    app.state.policy = policy
    app.state.skill_notes = skill_notes
    app.state.responses, app.state.insights = responses, insights
    app.state.source_yield = source_yield
    app.add_middleware(BodyLimit)
    # The client address is the real one only when uvicorn trusts the proxy
    # (OPENINGS_TRUSTED_PROXIES); otherwise every proxied client shares one bucket.
    login_guard = app.state.login_guard = LoginGuard()
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
            actor = SYSTEM
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
            with acting_as(actor):
                async with semaphore:
                    response = await call_next(request)
            if sign_in:
                if response.status_code == 401:
                    login_guard.failed()
                elif response.status_code == 200:
                    login_guard.succeeded()
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

    register_system(router, mcp, workspace, auth, public_url)

    register_core(router, workspace, requests)
    register_skills_api(router, skills, skill_notes)
    register_career_api(router, career)
    register_document_api(router, documents)
    register_discovery_api(router, discovery)
    register_activity_api(router, activity)
    register_request_api(router, requests)
    register_policy_api(router, policy)
    register_response_api(router, responses)
    register_insights_api(router, insights)
    register_yield_api(router, source_yield)
    app.include_router(router)
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
