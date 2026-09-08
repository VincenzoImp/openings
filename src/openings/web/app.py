"""The web process: dashboard, REST API and MCP in one ASGI application."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.applications import Starlette
from starlette.types import ASGIApp, Receive, Scope, Send

from openings.logger import get_logger, setup_logging
from openings.project_meta import get_project_version
from openings.runtime import get_runtime
from openings.web.api import public_router, router as api_router, token_presented, api_token
from openings.web.mcp import create_mcp_app
from openings.web.static import dashboard_response, mount_frontend_assets

DEFAULT_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

logger = get_logger("web")


def get_cors_allowed_origins() -> list[str]:
    raw = os.environ.get("OPENINGS_WEB_ALLOWED_ORIGINS", "")
    return list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))


class TokenGate:
    """Require the API token on every request to the wrapped app."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            expected = api_token()
            if expected:
                headers = {
                    key.decode("latin-1").lower(): value.decode("latin-1")
                    for key, value in scope.get("headers", [])
                }
                if not token_presented(
                    expected, headers.get("authorization"), headers.get("x-openings-token")
                ):
                    body = json.dumps({"detail": "Invalid or missing API token"}).encode()
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 401,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()),
                            ],
                        }
                    )
                    await send({"type": "http.response.body", "body": body})
                    return
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(_app: FastAPI, mcp_app: Starlette) -> AsyncIterator[None]:
    runtime = get_runtime()
    setup_logging(runtime.config(), console_only=True)
    logger.info("Web server ready | %d jobs", runtime.db.count_jobs())
    try:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    finally:
        runtime.close()


def create_app() -> FastAPI:
    mcp_app = create_mcp_app()
    app = FastAPI(
        title="Openings",
        version=get_project_version(),
        lifespan=lambda fastapi_app: lifespan(fastapi_app, mcp_app),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allowed_origins(),
        allow_origin_regex=DEFAULT_CORS_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Openings-Token"],
    )
    app.include_router(public_router)
    app.include_router(api_router)
    app.mount("/mcp", TokenGate(mcp_app))
    mount_frontend_assets(app)

    @app.get("/health")
    def health() -> dict[str, object]:
        runtime = get_runtime()
        return {
            "status": "ok",
            "version": get_project_version(),
            "jobs_count": runtime.db.count_jobs(),
            "embeddings": runtime.embeddings_status,
        }

    @app.get("/")
    def index() -> HTMLResponse:
        return dashboard_response()

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("OPENINGS_WEB_LISTEN_PORT", "8501")))


if __name__ == "__main__":
    main()
